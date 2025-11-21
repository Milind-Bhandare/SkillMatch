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

🔧 How SkillMatch Uses Gen-AI

SkillMatch doesn’t rely on keyword tricks. It uses Gen-AI in three targeted ways:

1. Smart Query Understanding

The LLM cleans messy recruiter queries and extracts role, skills, experience, and location.
If the intent isn’t clear, the system rejects the query instead of hallucinating.

2. Meaning-Based Candidate Ranking

Resumes are converted into vector embeddings, letting the system understand related skills (Python ↔ Py, ML ↔ Machine Learning).
SQL handles strict filters (location, experience), and ChromaDB ranks candidates by true relevance, not wording.

3. AI-Generated Candidate Summaries

Clicking a candidate triggers an LLM summary built from their resume, skills, and experience.
You get a quick snapshot: strengths, role-fit, and any gaps — no need to read the whole resume.

## Setup

1. Clone repo

git clone https://github.com/<your-username>/skillmatch.git

   cd skillmatch

2. Install dependencies :

pip install -r requirements.txt

3. Intstall and Run Ollama (if using local LLM) :

ollama pull gemma:2b
ollama run gemma:2b

4. Start API
uvicorn app:app --reload --port 8000


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

📌 Extra Commands

Check DB schema:

python scripts/ensure_db_schema.py


Rebuild SQLite DB:

python db/db.py --rebuild


Clear Chroma vectors (if required):

python clear_vectors.py

🔧 Technologies / Tools

Python (backend logic)

FastAPI / Uvicorn (HTTP server)

SQLite (structured data storage)

ChromaDB (semantic search vector database)

LLM(s) (via Ollama or Hugging Face) for query parsing

HTML/TailwindCSS/JS for frontend recruiter/job-seeker interface

🎯 Future Improvements

Add authentication (for recruiters/job-seekers)

More advanced skill‐extraction (multi-page resumes, CV designs)

Pagination/filter UI for large candidate lists

Deploy to cloud (AWS, Azure) with scalable vector store

Add analytics for recruiter usage / applicant tracking

🧑‍💻 Contributing

Contributions are welcome. Feel free to open an issue or submit a pull request for bug fixes, enhancements or new features. Please ensure tests (if added) pass and follow consistent coding style.

🧬 Contact

Created by Milind Bhandare

For questions or feedback, raise an issue or email me at: [milindbhandare7777@gmail.com].