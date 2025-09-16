# services/resume_ingest.py
import hashlib, uuid, os
from utils.text_extractor import extract_text
from services.skill_extractor import extract_skills

def process_resume_file(path, filename=None):
    path = str(path)
    text = extract_text(path)
    if not text:
        text = ""
    text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
    skills = extract_skills(text)
    # return minimal candidate object
    candidate = {
        "id": str(uuid.uuid4()),
        "filename": filename or os.path.basename(path),
        "name": None,
        "email": None,
        "location": None,
        "experience": None,
        "skills": skills,
        "raw_text": text,
        "text_hash": text_hash
    }
    return candidate
