# 🚀 SkillMatch — **AI-Powered Resume Search Bot**

**SkillMatch** is a **plug-and-play AI-powered recruitment assistant** that helps **job seekers** upload resumes and **recruiters** find the right candidates using plain-English queries.

> *"Python developer with 2 years experience in Pune"*

Resumes are parsed, skills extracted, and stored in **SQLite** and **ChromaDB** for semantic search. Recruiter queries are parsed by an **LLM (Ollama or Hugging Face)** and matched using strict filtering + relevance ranking.

---

## ✨ **Key Features**

* **Job Seekers** — Upload resumes via a web form; resume parsed, skills extracted, stored.
* **Recruiters** — Search using plain English and receive **ranked** candidate matches.
* **Strict Filters** — **Location** and **years of experience** applied via SQL before semantic ranking.
* **Skill Normalization** — Variants like **py → Python** are standardized automatically.
* **Fallback Parser** — If the LLM fails, a keyword parser ensures searches still work.
* **Zero Noise** — Nonsensical queries (e.g., “banana drones on Mars”) return **no results**, not garbage.

---

## 🔧 How SkillMatch Uses **Gen‑AI**

SkillMatch applies Gen‑AI where it matters:

1. **Smart Query Understanding** — LLM extracts **role**, **skills**, **experience**, **location** from messy recruiter input. If intent is unclear, the system rejects the query rather than hallucinate.

2. **Meaning‑Based Candidate Ranking** — Resumes → **vector embeddings**, enabling related-skill matches (e.g., **Python ↔ Py**, **ML ↔ Machine Learning**). SQL enforces hard filters, ChromaDB ranks by semantic relevance.

3. **AI‑Generated Candidate Summaries** — Click a candidate to see an LLM summary (strengths, role-fit, gaps) — **fast screening** without reading full resumes.

---

## ⚙️ Setup

1. **Clone repo**

```bash
git clone https://github.com/<your-username>/skillmatch.git
cd skillmatch
```

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Install & run Ollama** (if using local LLM)

```bash
ollama pull gemma:2b
ollama run gemma:2b
```

4. **Start API**

```bash
uvicorn app:app --reload --port 8000
```

---

## 🔍 How It Works — Quick Flow

### **Job Seekers**

1. Visit: `http://127.0.0.1:8000/`
2. Fill **name**, **email**, upload **resume**
3. Resume parsed → skills extracted → stored in **SQLite + ChromaDB**

### **Recruiters**

1. Visit: `http://127.0.0.1:8000/recruiter`
2. Enter a plain English query (e.g., *“Java Spring Boot AWS with 3+ years in Bangalore”*)
3. System parses query (Ollama/HF) → applies SQL filters → ranks candidates → shows results → Generate AI Summery 

---

## 📌 Useful Commands

* **Check DB schema**

```bash
python scripts/ensure_db_schema.py
```

* **Rebuild SQLite DB**

```bash
python db/db.py --rebuild
```

* **Clear Chroma vectors**

```bash
python clear_vectors.py
```

---

## 🛠️ Technologies

**Python** • **FastAPI / Uvicorn** • **SQLite** • **ChromaDB** • **Ollama / Hugging Face LLMs** • **HTML / TailwindCSS / JS**

---

## 🎯 Roadmap (short & brutal)

* **Add authentication** (required — don't skip)
* **Improve skill extraction** for multi-page / complex CV formats
* **Pagination & filter UI** for large candidate lists
* **Cloud deploy** (AWS/Azure) with a scalable vector store
* **Recruiter analytics / applicant tracking**

---

## 🤝 Contributing

Contributions welcome. Open an issue or a PR for bug fixes, features, or tests. Keep code style consistent and include tests when possible.

---

## 👤 Author

**Milind Bhandare** — `milindbhandare7777@gmail.com`

For questions or feedback: open an issue or email.
