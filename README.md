# SkillMatch – AI-Powered Resume Search Bot

SkillMatch is a **plug-and-play AI-powered recruitment assistant**.  
It allows **job seekers** to upload resumes and apply for jobs, and **recruiters** to search for candidates using plain English queries like:

> *"Python developer with 2 years experience in Pune"*

Behind the scenes, resumes are parsed, skills extracted, and stored in both **SQLite** and **ChromaDB** for semantic search. Recruiter queries are parsed with an **LLM (Ollama or Hugging Face)** and matched against the database with strict filtering + ranking.

---

## Features
- **Job Seekers**: Upload resumes via a web form. System parses resume text, extracts skills, and stores in database.
- **Recruiters**: Search with natural language queries and get ranked candidates.
- **Strict Filters**: Location and years of experience are applied first in SQL before semantic ranking.
- **Skill Normalization**: Variants like "py" → Python are automatically standardized.
- **Fallback Parser**: If the LLM can’t parse a query, a backup keyword parser ensures searches never fail.
- **Zero noise**: If query is nonsense (e.g., “banana drones on Mars”), no candidates are shown.

---

## Project Structure
skillmatch/
├─ app.py
├─ requirements.txt
├─ check_sqllite_db.py
├─ clear_vectors.py
├─ init.db
│
├─ config/
│ ├─ config.yml
│ ├─ skills_dict.json
│ └─ init.py
│
├─ db/
│ ├─ db.py
│ └─ init.py
│
├─ chroma/
│ ├─ chroma_store.py
│ └─ init.py
│
├─ services/
│ ├─ resume_ingest.py
│ ├─ skill_extractor.py
│ ├─ jobs.py
│ └─ init.py
│
├─ utils/
│ └─ text_extractor.py
│
├─ templates/
│ ├─ jobs.html
│ ├─ recruiter.html
│ └─ search.html
│
├─ static/
│ ├─ style.css
│ ├─ script.js
│ └─ recruiter.js
│
├─ scripts/
│ ├─ ensure_db_schema.py
│ └─ clear_vectors.py
│
└─ data/
├─ chroma_store/ # Created at runtime
└─ resume.db # SQLite DB

## Setup

1. Clone repo

git clone https://github.com/<your-username>/skillmatch.git

cd skillmatch

2. Install dependencies

pip install -r requirements.txt

3. Run Ollama (if using local LLM)

ollama pull gemma:2b
ollama run gemma:2b

4. Start API
uvicorn app:app --reload --port 8000

Example Queries
Input:
Python developer with 2 years experience in Pune
Output:

Name           Email             Experience   Rating
---------------------------------------------------
Anand Sharma   anad@mail.com     2 yrs        ★★★★★

Priya          abcd@test.com     9 yrs        ★★★★☆

Invalid Query:
Banana drones on Mars
Output:
No candidates found

Check DB schema:
python scripts/ensure_db_schema.py

Rebuild DB:
python db/db.py --rebuild

Clear Chroma vectors:
python clear_vectors.py  -- if required

## How It Works

### Job Seekers
1. Go to:
   http://127.0.0.1:8000/

2. Fill details like **name, email, and upload resume**.
3. Resume is parsed → skills extracted → stored in **SQLite + ChromaDB**.

### Recruiters
1. Go to:
   http://127.0.0.1:8000/recruiter

2. Enter query in plain English (e.g., *“Java Spring Boot AWS with 3+ years in Bangalore”*).
3. System parses query using Ollama/HF → applies SQL filters → ranks candidates → shows results.
