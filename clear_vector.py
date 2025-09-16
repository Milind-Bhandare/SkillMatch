# scripts/clear_vectors.py
from pathlib import Path
from config.config_loader import CONFIG
p = Path(CONFIG["embeddings"].get("persist_directory", "data/chroma_store"))
vec = p / "vectors.json"
meta = p / "metadata.json"
for f in (vec, meta):
    if f.exists():
        f.unlink()
        print("Removed", f)
print("Cleared vector store.")
