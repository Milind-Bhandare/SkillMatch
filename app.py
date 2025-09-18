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
    if not skill:
        return None
    skill_lower = str(skill).lower().strip()
    norm_map = SKILLS_DICT.get("normalization_map", {}) or {}
    if skill_lower in norm_map:
        return norm_map[skill_lower]
    known = [s.lower() for s in SKILLS_DICT.get("skills", [])]
    best = difflib.get_close_matches(skill_lower, known, n=1, cutoff=0.85)
    if best:
        idx = known.index(best[0])
        return SKILLS_DICT["skills"][idx]
    return skill.strip()


def detect_explicit_years(nl: str):
    if not nl:
        return None, None
    m = re.search(r'(\d{1,2})\s*\+\s*(?:years|yrs|year)?', nl)
    if m:
        return int(m.group(1)), 50  # treat "3+" as 3 to 50
    m = re.search(r'(\d{1,2})\s*(?:years|yrs|year)', nl)
    if m:
        n = int(m.group(1))
        return n, n
    return None, None


def map_seniority(nl_lower: str):
    exp_map = CONFIG.get("experience_ranges", {})
    for key in ["Fresher", "Junior", "Mid", "Senior", "Lead"]:
        if key.lower() in nl_lower:
            r = exp_map.get(key, {})
            return key, r.get("min"), r.get("max")
    return None, None, None


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


def fallback_parser(nl: str):
    nl_lower = (nl or "").lower()

    # normalize common seniority abbreviations
    seniority_aliases = {
        r"\bsr[\.\s]": "senior ",
        r"\bjr[\.\s]": "junior ",
        r"\bmid[\.\s]": "mid ",
        r"\blead[\.\s]": "lead ",
        r"\bfresher[\.\s]?": "fresher "
    }
    for pattern, replacement in seniority_aliases.items():
        nl_lower = re.sub(pattern, replacement, nl_lower)

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

    # seniority mapping
    s, mn, mx = map_seniority(nl_lower)
    if s:
        parsed["seniority"] = s
        parsed["min_years"], parsed["max_years"] = mn, mx

    # explicit years override seniority ranges
    ey_min, ey_max = detect_explicit_years(nl_lower)
    if ey_min is not None:
        parsed["min_years"], parsed["max_years"] = ey_min, ey_max

    # skills
    words = re.split(r'[\s,/;|]+', nl_lower)
    seen = set()
    for w in words:
        if len(w) < 2:
            continue
        norm = normalize_skill(w)
        if norm and norm not in seen:
            seen.add(norm)
            parsed["must_have"].append(norm)

    # title
    for t in ["developer", "engineer", "analyst", "manager", "architect"]:
        if t in nl_lower:
            parsed["title"] = t.title()
            break

    # location
    for loc in CONFIG.get("cities", []) or []:
        if loc and loc.lower() in nl_lower:
            parsed["location"] = loc
            break

    return parsed


# -------------------- Search --------------------
@app.get("/search_candidates")
def search_candidates(query: str):
    if not query or query.strip() == "":
        return {"query": query, "results": [], "message": "Enter a valid query"}

    try:
        parsed = fallback_parser(query)
    except Exception as e:
        print(f"[OLLAMA] parse error: {e}")
        parsed = None

    if not parsed:
        parsed = parse_nl_with_ollama(query)

    # enforce filters
    where_clauses, params = [], []

    if parsed.get("location"):
        where_clauses.append("LOWER(location) = LOWER(?)")
        params.append(parsed["location"])

    if parsed.get("min_years") is not None:
        mn, mx = parsed.get("min_years"), parsed.get("max_years")
        if mx is None:
            mx = mn
        where_clauses.append("CAST(experience AS INTEGER) BETWEEN ? AND ?")
        params.extend([mn, mx])

    sql_rows = query_candidates(" AND ".join(where_clauses), tuple(params)) if where_clauses else query_candidates()

    # vector search
    vec_results = vector_search(query, top_k=CONFIG.get("search", {}).get("vector_top_k", 50)) or []
    vec_map = {v["id"]: float(v.get("score", 0.0)) for v in vec_results if isinstance(v, dict)}

    must_skills = [normalize_skill(s).lower() for s in parsed.get("must_have") or []]

    out = []
    for r in sql_rows:
        cand_skills = [normalize_skill(s).lower() for s in (r.get("skills") or [])]
        skill_matches = len([m for m in must_skills if m in cand_skills])
        skill_score = (skill_matches / len(must_skills)) if must_skills else 0.0
        sem_score = vec_map.get(r["id"], 0.0)
        exp_score = 0.0
        if parsed.get("min_years") is not None:
            try:
                exp_val = int(r.get("experience") or 0)
                mn, mx = parsed.get("min_years"), parsed.get("max_years") or parsed.get("min_years")
                exp_score = 1.0 if mn <= exp_val <= mx else 0.0
            except Exception:
                pass
        final_score = (
                CONFIG["scoring"].get("semantic_weight", 0.5) * sem_score +
                CONFIG["scoring"].get("skill_weight", 0.3) * skill_score +
                CONFIG["scoring"].get("experience_weight", 0.2) * exp_score
        )
        if CONFIG["filters"].get("enforce_must_have", True) and must_skills and skill_matches == 0:
            continue
        out.append({"candidate": r, "semantic": sem_score, "skill_score": skill_score,
                    "exp_score": exp_score, "final_score": final_score})

    if not out:
        return {"query": query, "results": [], "message": "No results found. Please refine your search."}

    out = sorted(out, key=lambda x: x["final_score"], reverse=True)
    max_score = max([o["final_score"] for o in out] or [1.0])
    for o in out:
        o["star"] = round((o["final_score"] / max_score) * 5, 2)
    return {"query": query, "results": out}
