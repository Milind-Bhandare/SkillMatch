# db/db.py
import sqlite3
import json
import hashlib
import uuid
from pathlib import Path
from datetime import datetime
from config.config_loader import CONFIG

DB_PATH = Path(CONFIG["database"]["path"])
TABLE = CONFIG["database"].get("table_name", "candidates")


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # give a reasonable timeout in case of concurrent access
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def compute_text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def init_db():
    """Create table if it doesn't exist (uses config for path/table)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            id TEXT PRIMARY KEY,
            filename TEXT,
            name TEXT,
            email TEXT,
            phone TEXT,
            title TEXT,
            location TEXT,
            experience INTEGER,
            skills_json TEXT,
            raw_text TEXT,
            text_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(email),
            UNIQUE(text_hash)
        );
    """)
    conn.commit()
    conn.close()


def upsert_candidate(candidate: dict):
    """
    Insert or update candidate. Uses email as primary dedupe if present,
    else falls back to text_hash. Returns (candidate_id, is_new:bool)
    """
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cid = candidate.get("id") or str(uuid.uuid4())
    skills_json = json.dumps(candidate.get("skills", []), ensure_ascii=False)
    text_hash = compute_text_hash(candidate.get("raw_text", "") or "")

    # check existence first to determine is_new
    existing = None
    if candidate.get("email"):
        cur.execute(f"SELECT id FROM {TABLE} WHERE email = ? LIMIT 1", (candidate.get("email"),))
        existing = cur.fetchone()
    if not existing:
        cur.execute(f"SELECT id FROM {TABLE} WHERE text_hash = ? LIMIT 1", (text_hash,))
        existing = cur.fetchone()

    values = {
        "id": cid,
        "filename": candidate.get("filename"),
        "name": candidate.get("name"),
        "email": candidate.get("email"),
        "phone": candidate.get("phone"),
        "title": candidate.get("title"),
        "location": candidate.get("location"),
        "experience": candidate.get("experience"),
        "skills_json": skills_json,
        "raw_text": candidate.get("raw_text"),
        "text_hash": text_hash,
        "updated_at": datetime.utcnow().isoformat()
    }

    # Perform upsert: prefer email conflict if present, else text_hash conflict
    try:
        if values["email"]:
            cur.execute(f"""
                INSERT INTO {TABLE} (id, filename, name, email, phone, title, location, experience,
                                    skills_json, raw_text, text_hash, created_at, updated_at)
                VALUES (:id, :filename, :name, :email, :phone, :title, :location, :experience,
                        :skills_json, :raw_text, :text_hash, CURRENT_TIMESTAMP, :updated_at)
                ON CONFLICT(email) DO UPDATE SET
                    filename=excluded.filename,
                    name=excluded.name,
                    phone=excluded.phone,
                    title=excluded.title,
                    location=excluded.location,
                    experience=excluded.experience,
                    skills_json=excluded.skills_json,
                    raw_text=excluded.raw_text,
                    text_hash=excluded.text_hash,
                    updated_at=excluded.updated_at;
            """, values)
        else:
            cur.execute(f"""
                INSERT INTO {TABLE} (id, filename, name, phone, title, location, experience,
                                    skills_json, raw_text, text_hash, created_at, updated_at)
                VALUES (:id, :filename, :name, :phone, :title, :location, :experience,
                        :skills_json, :raw_text, :text_hash, CURRENT_TIMESTAMP, :updated_at)
                ON CONFLICT(text_hash) DO UPDATE SET
                    filename=excluded.filename,
                    name=excluded.name,
                    phone=excluded.phone,
                    title=excluded.title,
                    location=excluded.location,
                    experience=excluded.experience,
                    skills_json=excluded.skills_json,
                    raw_text=excluded.raw_text,
                    updated_at=excluded.updated_at;
            """, values)
        conn.commit()
    except sqlite3.IntegrityError:
        # In case of race or other integrity issues, fall through
        pass

    # fetch id
    cur.execute(f"SELECT id FROM {TABLE} WHERE email = ? OR text_hash = ? LIMIT 1",
                (values["email"], text_hash))
    row = cur.fetchone()
    conn.close()

    found_id = row["id"] if row else cid
    is_new = False if existing else True
    return found_id, is_new


def _parse_skills_field(d):
    if "skills_json" in d and d["skills_json"]:
        try:
            d["skills"] = json.loads(d["skills_json"])
        except Exception:
            d["skills"] = [s.strip() for s in str(d["skills_json"]).split(",") if s.strip()]
    else:
        d["skills"] = []
    return d


def get_candidate_by_id(candidate_id: str):
    init_db()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (candidate_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    return _parse_skills_field(d)


def query_candidates(where: str = "", params: tuple = ()):
    """
    Returns list[dict] of candidates. `where` is raw SQL WHERE clause fragment (no leading WHERE).
    `params` must be a tuple for SQL placeholders.
    """
    init_db()
    conn = get_conn()
    cur = conn.cursor()
    sql = f"SELECT * FROM {TABLE}"
    if where:
        sql += f" WHERE {where}"
    cur.execute(sql, params or ())
    rows = cur.fetchall()
    cols = [c[0] for c in cur.description] if cur.description else []
    conn.close()
    out = [dict(zip(cols, r)) for r in rows]
    # parse skills_json field into skills list
    return [_parse_skills_field(o) for o in out]
