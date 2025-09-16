# app.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import shutil
import difflib
import re
import json
import requests

from fastapi.staticfiles import StaticFiles

from services.resume_ingest import process_resume_file
from services.jobs import list_jobs, get_job
from db.db import upsert_candidate, get_candidate_by_id, query_candidates
from chroma.chroma_store import add_or_update_candidate, search as vector_search
from config.config_loader import CONFIG, SKILLS_DICT

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

TMP_DIR = Path("uploads")
TMP_DIR.mkdir(exist_ok=True)
templates = Jinja2Templates(directory="templates")


# -------------------- Routes --------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("jobs.html", {"request": request})


@app.get("/recruiter", response_class=HTMLResponse)
async def recruiter(request: Request):
    return templates.TemplateResponse("recruiter.html", {"request": request})


@app.get("/jobs")
def jobs():
    return {"jobs": list_jobs()}


@app.post("/apply/{job_id}")
async def apply(job_id: str,
                file: UploadFile = File(...),
                name: str = Form(...),
                email: str = Form(...),
                location: str = Form(...),
                experience: int = Form(...)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")

    tmp = TMP_DIR / file.filename
    with open(tmp, "wb") as f:
        shutil.copyfileobj(file.file, f)

    candidate = process_resume_file(tmp, filename=file.filename)
    candidate.update({
        "name": name.strip(),
        "email": email.strip(),
        "location": location.strip(),
        "experience": experience
    })

    cid, is_new = upsert_candidate(candidate)
    add_or_update_candidate(cid, candidate["raw_text"],
                            metadata={"name": candidate["name"], "email": candidate["email"]})
    tmp.unlink(missing_ok=True)
    return {"job_applied": job, "resume": candidate, "candidate_id": cid, "is_new": is_new}


# -------------------- Helpers --------------------
def normalize_skill(skill):
    """Normalize skill using mapping and fuzzy matching (returns canonical or original)."""
    if not skill:
        return None
    skill_lower = str(skill).lower().strip()
    norm_map = SKILLS_DICT.get("normalization_map", {}) or {}
    # direct mapping
    if skill_lower in norm_map:
        return norm_map[skill_lower]
    # fuzzy matching against known skills
    known = [s.lower() for s in SKILLS_DICT.get("skills", [])]
    best = difflib.get_close_matches(skill_lower, known, n=1, cutoff=0.85)
    if best:
        idx = known.index(best[0])
        return SKILLS_DICT["skills"][idx]
    # if nothing found, return original-cased token
    return skill.strip()


def detect_explicit_years(nl: str):
    """
    Detect expressions like '2 years', '3 yrs', '5+ years' and return (min_years, max_years).
    For '5+' -> (5, 100). For single number -> (n, n).
    """
    if not nl:
        return None, None
    m = re.search(r'(\d{1,2})\s*\+\s*(?:years|yrs|year)?', nl)
    if m:
        n = int(m.group(1))
        return n, None  # treat as min=n
    m = re.search(r'(\d{1,2})\s*(?:years|yrs|year)', nl)
    if m:
        n = int(m.group(1))
        return n, n
    return None, None


def fallback_parser(nl: str):
    """
    Basic fallback parser: detect seniority, explicit years, skills tokens (normalized),
    title heuristics, and location using config.cities
    """
    nl_lower = (nl or "").lower()
    parsed = {
        "title": None,
        "seniority": None,
        "must_have": [],
        "any_of": [],
        "location": None,
        "min_years": None,
        "max_years": None,
        "raw_query": nl or ""
    }

    exp_map = CONFIG.get("experience_ranges", {})

    # seniority phrases
    if any(x in nl_lower for x in ["senior", "sr ", "sr.", "sr,", "Sr.", "Sr"]):
        parsed["seniority"] = "Senior"
        r = exp_map.get("Senior", {})
        parsed["min_years"], parsed["max_years"] = r.get("min"), r.get("max")
    elif any(x in nl_lower for x in ["junior", "jr ", "jr.", "jr,", "Jr.", "Jr"]):
        parsed["seniority"] = "Junior"
        r = exp_map.get("Junior", {})
        parsed["min_years"], parsed["max_years"] = r.get("min"), r.get("max")
    elif any(x in nl_lower for x in ["mid", "mid-level", "midlevel"]):
        parsed["seniority"] = "Mid"
        r = exp_map.get("Mid", {})
        parsed["min_years"], parsed["max_years"] = r.get("min"), r.get("max")

    # explicit numeric years
    ey_min, ey_max = detect_explicit_years(nl_lower)
    if ey_min is not None:
        parsed["min_years"] = ey_min
        parsed["max_years"] = ey_max

    # skills: token-level normalization (will catch exact tokens like 'java', 'spring', 'aws')
    words = re.split(r'[\s,/;|]+', nl_lower)
    seen = set()
    for w in words:
        if not w or len(w) < 2:
            continue
        norm = normalize_skill(w)
        if norm and norm not in seen:
            seen.add(norm)
            parsed["must_have"].append(norm)

    # title heuristics
    for t in ["developer", "engineer", "analyst", "manager", "architect"]:
        if t in nl_lower:
            parsed["title"] = t.title()
            break

    # location detection using configured cities (more robust than ad-hoc strings)
    for loc in CONFIG.get("cities", []) or []:
        if loc and loc.lower() in nl_lower:
            parsed["location"] = loc
            break

    # ensure lists/strings are not None
    parsed["must_have"] = parsed.get("must_have") or []
    parsed["any_of"] = parsed.get("any_of") or []
    parsed["title"] = parsed.get("title") or None
    parsed["location"] = parsed.get("location") or None
    parsed["raw_query"] = parsed.get("raw_query") or ""
    return parsed


# -------------------- Ollama parsing --------------------
def build_ollama_prompt(nl: str):
    return f"""
You are a strict JSON generator. Given a recruiter's natural language query, output a single JSON
object with keys: title, seniority, must_have (list), any_of (list), location, min_years (int or null), max_years (int or null), raw_query.
If a field is missing, use null or [].
Return ONLY the JSON object, nothing else.

Query: \"{nl}\"
"""


def parse_nl_with_ollama(nl: str):
    """
    Call Ollama configured in CONFIG. Return a sanitized dict or None.
    Handles streaming responses and non-stream responses; prints raw output for debug.
    """
    if not CONFIG.get("ollama", {}).get("enabled", False):
        raise RuntimeError("Ollama disabled in config")

    api_url = CONFIG["ollama"]["api_url"]
    payload = {
        "model": CONFIG["ollama"].get("model"),
        "prompt": build_ollama_prompt(nl),
        # use streaming when supported (some Ollama setups stream JSON chunks)
        "stream": True,
        "options": {"num_predict": 256}
    }

    try:
        resp = requests.post(api_url, json=payload, stream=True, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        # bubble up so caller can fallback
        print(f"[OLLAMA] request failed: {e}")
        return None

    full_text = []
    try:
        # Try streaming lines first (common with Ollama)
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw:
                continue
            line = raw.strip()
            # many Ollama streaming lines are JSON objects per-line; try parse
            try:
                j = json.loads(line)
            except Exception:
                # if not JSON, append as-is
                full_text.append(line)
                continue
            # Ollama variants might use "response" or "text"
            if isinstance(j, dict):
                if "response" in j and isinstance(j["response"], str):
                    full_text.append(j["response"])
                elif "text" in j and isinstance(j["text"], str):
                    full_text.append(j["text"])
                elif "choices" in j and isinstance(j["choices"], list):
                    # some variants use choices -> text
                    for c in j["choices"]:
                        if isinstance(c, dict) and "text" in c:
                            full_text.append(c["text"])
                # if a done flag exists, break
                if j.get("done"):
                    break
            else:
                # if j is not dict (unlikely), append raw
                full_text.append(line)
    except Exception:
        # fall back to trying to read full body
        try:
            text_body = resp.text
            full_text.append(text_body)
        except Exception:
            pass

    text_out = "".join(full_text).strip()
    # DEBUG: print raw response so you can see exactly what Ollama returned
    print("\n--- RAW OLLAMA OUTPUT START ---")
    print(text_out)
    print("--- RAW OLLAMA OUTPUT END ---\n")

    if not text_out:
        # no content
        return None

    # try to extract a JSON object from the returned text
    m = re.search(r"\{[\s\S]*\}", text_out)
    if m:
        try:
            parsed = json.loads(m.group(0))
        except Exception:
            parsed = None
    else:
        # maybe entire output was JSON string (non-stream)
        try:
            parsed = json.loads(text_out)
        except Exception:
            parsed = None

    # sanitize parsed (normalize None -> empty lists/strings)
    if not parsed or not isinstance(parsed, dict):
        return None

    # ensure keys exist and normalized
    parsed_sanitized = {
        "title": parsed.get("title") or None,
        "seniority": parsed.get("seniority") or None,
        "must_have": parsed.get("must_have") or [],
        "any_of": parsed.get("any_of") or [],
        "location": parsed.get("location") or None,
        "min_years": parsed.get("min_years"),
        "max_years": parsed.get("max_years"),
        "raw_query": parsed.get("raw_query") or nl or ""
    }
    # ensure lists are lists
    if parsed_sanitized["must_have"] is None:
        parsed_sanitized["must_have"] = []
    if parsed_sanitized["any_of"] is None:
        parsed_sanitized["any_of"] = []

    return parsed_sanitized


# -------------------- Search Endpoint --------------------
@app.get("/search_candidates")
def search_candidates(query: str):
    if not query or query.strip() == "":
        return {"query": query, "results": [], "message": "Enter a valid query"}

    # 1) Try LLM parser (Ollama) if enabled; else fallback parser
    parsed = None
    if CONFIG.get("ollama", {}).get("enabled", False):
        try:
            parsed = parse_nl_with_ollama(query)
        except Exception as e:
            print(f"[OLLAMA] parse error: {e}")
            parsed = None

    if not parsed:
        parsed = fallback_parser(query)

    # Normalize parsed fields to avoid None issues
    parsed["must_have"] = parsed.get("must_have") or []
    parsed["any_of"] = parsed.get("any_of") or []
    parsed["location"] = parsed.get("location") or None
    # if min_years is None try to detect explicit numeric years
    if parsed.get("min_years") is None:
        ey_min, ey_max = detect_explicit_years(query.lower())
        if ey_min is not None:
            parsed["min_years"] = ey_min
            parsed["max_years"] = ey_max

    # short-circuit strict behavior:
    # If both location and explicit experience (min_years present) are provided, apply SQL filters first,
    # then rank results (semantic) inside that small subset.
    has_location = bool(parsed.get("location"))
    has_exp = parsed.get("min_years") is not None

    # Build SQL filter depending on min/max years and location
    where_clauses = []
    params = []

    if has_location and CONFIG.get("filters", {}).get("enforce_strict_location", True):
        where_clauses.append("LOWER(location) = LOWER(?)")
        params.append(parsed["location"])

    if has_exp and CONFIG.get("filters", {}).get("enforce_strict_experience", True):
        mn = parsed.get("min_years")
        mx = parsed.get("max_years")
        if mn is not None and mx is not None:
            # exact range
            where_clauses.append("CAST(experience AS INTEGER) BETWEEN ? AND ?")
            params.extend([mn, mx])
        elif mn is not None and mx is None:
            # either treat as exact or at-least depending on config; we treat explicit number as exact if query
            # contained a numeric expression We check whether min==max earlier via detect_explicit_years: if max==min
            # we would have set both.
            where_clauses.append("CAST(experience AS INTEGER) = ?")
            params.append(mn)

    where_clause_sql = " AND ".join(where_clauses)

    # fetch candidates from DB using SQL filters first (strict subset)
    sql_rows = query_candidates(where_clause_sql, tuple(params)) if where_clause_sql else query_candidates()

    # if strict filters were present and returned candidates, we restrict ranking to them
    candidate_id_set = {r["id"] for r in sql_rows} if sql_rows else set()

    # if we have candidate subset -> run semantic search but only keep items present in candidate_id_set
    vec_top_k = CONFIG.get("search", {}).get("vector_top_k", 50)
    vec_results = vector_search(query, top_k=vec_top_k) or []

    # Ensure vec_results are list of dicts with id and score
    # Some implementations returned list of ids; normalize both cases
    normalized_vec = []
    for v in vec_results:
        if isinstance(v, dict) and "id" in v:
            normalized_vec.append({"id": v["id"], "score": float(v.get("score", 0.0))})
        elif isinstance(v, (list, tuple)) and len(v) >= 2:
            normalized_vec.append({"id": v[0], "score": float(v[1])})
        elif isinstance(v, str):
            normalized_vec.append({"id": v, "score": 0.0})
    vec_results = normalized_vec

    # Build SQL rows by id for quick lookup
    sql_by_id = {r["id"]: r for r in sql_rows}

    sem_w = CONFIG.get("scoring", {}).get("semantic_weight", 0.5)
    skill_w = CONFIG.get("scoring", {}).get("skill_weight", 0.3)
    exp_w = CONFIG.get("scoring", {}).get("experience_weight", 0.2)
    min_relevance = CONFIG.get("scoring", {}).get("min_relevance_threshold", 0.2)
    enforce_must_have = CONFIG.get("filters", {}).get("enforce_must_have", True)

    must_skills = [normalize_skill(s).lower() for s in (parsed.get("must_have") or [])]


    out = []

    # If we had SQL filters and they returned results -> restrict ranking to those
    if candidate_id_set:
        # iterate vector results in order, pick those in candidate_id_set first
        seen_ids = set()
        for v in vec_results:
            cid = v["id"]
            if cid not in candidate_id_set:
                continue
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            candidate = sql_by_id.get(cid) or get_candidate_by_id(cid)
            if not candidate:
                continue
            cand_skills = [normalize_skill(s).lower() for s in (candidate.get("skills") or [])]
            skill_matches = len([m for m in must_skills if m in cand_skills])
            skill_score = (skill_matches / len(must_skills)) if must_skills else 0.0

            exp_score = 0.0
            if parsed.get("min_years") is not None:
                try:
                    exp_val = int(candidate.get("experience") or 0)
                    mn = parsed.get("min_years")
                    mx = parsed.get("max_years") or mn
                    if mn <= exp_val <= mx:
                        exp_score = 1.0
                    else:
                        diff = min(abs(exp_val - mn), abs(exp_val - mx))
                        exp_score = max(0, 1 - diff / max(1, (mx - mn) or 1))
                except Exception:
                    exp_score = 0.0

            sem_score = float(v.get("score", 0.0))
            final_score = sem_w * sem_score + skill_w * skill_score + exp_w * exp_score

            # apply must-have enforcement if demanded
            if enforce_must_have and must_skills and skill_matches == 0:
                continue

            if final_score < min_relevance and skill_matches == 0:
                continue

            out.append({
                "candidate": candidate,
                "semantic": sem_score,
                "skill_score": skill_score,
                "exp_score": exp_score,
                "final_score": final_score
            })

        # If no vector hits among the SQL subset, fallback to skill-based ranking among SQL results
        if not out:
            for r in sql_rows:
                candidate = r
                cand_skills = [normalize_skill(s).lower() for s in (candidate.get("skills") or [])]
                skill_matches = len([m for m in must_skills if m in cand_skills])
                if enforce_must_have and must_skills and skill_matches == 0:
                    continue
                skill_score = (skill_matches / len(must_skills)) if must_skills else 0.0
                final_score = skill_w * skill_score
                out.append({
                    "candidate": candidate,
                    "semantic": 0.0,
                    "skill_score": skill_score,
                    "exp_score": 0.0,
                    "final_score": final_score
                })
    else:
        # No strict SQL subset (no location+exp both present OR no results) -> use normal vector search across DB
        # Combine vector results and DB entries
        for v in vec_results:
            cid = v["id"]
            sem_score = float(v.get("score", 0.0))
            candidate = get_candidate_by_id(cid)
            if not candidate:
                continue
            cand_skills = [normalize_skill(s).lower() for s in (candidate.get("skills") or [])]
            skill_matches = len([m for m in must_skills if m in cand_skills])
            skill_score = (skill_matches / len(must_skills)) if must_skills else 0.0

            exp_score = 0.0
            if parsed.get("min_years") is not None:
                try:
                    exp_val = int(candidate.get("experience") or 0)
                    mn = parsed.get("min_years")
                    mx = parsed.get("max_years") or mn
                    if mn <= exp_val <= mx:
                        exp_score = 1.0
                    else:
                        diff = min(abs(exp_val - mn), abs(exp_val - mx))
                        exp_score = max(0, 1 - diff / max(1, (mx - mn) or 1))
                except Exception:
                    exp_score = 0.0

            final_score = sem_w * sem_score + skill_w * skill_score + exp_w * exp_score

            if enforce_must_have and must_skills and skill_matches == 0:
                # if strict must-have, skip; otherwise allow scoring to dictate ranking
                continue

            if final_score < min_relevance and skill_matches == 0:
                continue

            out.append({
                "candidate": candidate,
                "semantic": sem_score,
                "skill_score": skill_score,
                "exp_score": exp_score,
                "final_score": final_score
            })

        # Fallback DB skill matching if no sem results
        if not out:
            # try simple skill-only matching across DB rows (respecting enforce_must_have)
            sql_all = query_candidates()
            for r in sql_all:
                cand_skills = [normalize_skill(s).lower() for s in (r.get("skills") or [])]
                skill_matches = len([m for m in must_skills if m in cand_skills])
                if enforce_must_have and must_skills and skill_matches == 0:
                    continue
                skill_score = (skill_matches / len(must_skills)) if must_skills else 0.0
                out.append({
                    "candidate": r,
                    "semantic": 0.0,
                    "skill_score": skill_score,
                    "exp_score": 0.0,
                    "final_score": skill_score * skill_w
                })

    if not out or all(o["final_score"] == 0 for o in out):
        return {"query": query, "results": [], "message": "No results found. Please refine your search."}

    # sort and compute star rating
    out = sorted(out, key=lambda x: x["final_score"], reverse=True)
    max_score = max([o["final_score"] for o in out] or [1.0])
    for o in out:
        o["star"] = round((o["final_score"] / max_score) * 5, 2) if max_score > 0 else 0

    return {"query": query, "results": out}
