# chroma/chroma_store.py
from pathlib import Path
import json, numpy as np
from sentence_transformers import SentenceTransformer
from config.config_loader import CONFIG
import os

PERSIST_DIR = Path(CONFIG["embeddings"].get("persist_directory", "data/chroma_store"))
PERSIST_DIR.mkdir(parents=True, exist_ok=True)
VEC_FILE = PERSIST_DIR / "vectors.json"

MODEL_NAME = CONFIG["embeddings"].get("model", "all-MiniLM-L6-v2")
MODEL = SentenceTransformer(MODEL_NAME)


def _load_vectors():
    if VEC_FILE.exists():
        with open(VEC_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: np.array(v) for k, v in data.items()}
    return {}


def _save_vectors(vecs: dict):
    serial = {k: v.tolist() for k, v in vecs.items()}
    with open(VEC_FILE, "w", encoding="utf-8") as f:
        json.dump(serial, f)


def add_or_update_candidate(candidate_id: str, text: str, metadata: dict = None):
    vecs = _load_vectors()
    vec = MODEL.encode([text])[0]
    vecs[candidate_id] = vec
    _save_vectors(vecs)
    # also optionally persist metadata file
    meta_file = PERSIST_DIR / "metadata.json"
    metas = {}
    if meta_file.exists():
        metas = json.loads(meta_file.read_text(encoding="utf-8"))
    metas[candidate_id] = metadata or {}
    meta_file.write_text(json.dumps(metas), encoding="utf-8")


def search(query: str, top_k: int = 20):
    vecs = _load_vectors()
    if not vecs:
        return []
    qv = MODEL.encode([query])[0]
    results = []
    for cid, vec in vecs.items():
        # cosine similarity
        score = float(np.dot(qv, vec) / (np.linalg.norm(qv) * np.linalg.norm(vec)))
        results.append((cid, score))
    results.sort(key=lambda x: x[1], reverse=True)
    # include metadata if available
    meta_file = PERSIST_DIR / "metadata.json"
    metas = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
    out = []
    for cid, score in results[:top_k]:
        out.append({"id": cid, "score": float(score), "metadata": metas.get(cid, {})})
    return out
