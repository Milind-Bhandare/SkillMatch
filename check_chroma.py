# check_chroma.py
from chroma.chroma_store import _load_vectors, search, PERSIST_DIR
import json
import numpy as np

# Load all vectors
vecs = _load_vectors()
print(f"\nLoaded {len(vecs)} vectors from {PERSIST_DIR}\n")

# Print stored vectors + metadata
meta_file = PERSIST_DIR / "metadata.json"
metas = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}

for cid, vec in vecs.items():
    print(f"Candidate ID: {cid}")
    print(f"Metadata: {metas.get(cid, {})}")
    print(f"Vector length: {len(vec)}")
    print(f"First 10 values: {vec[:10].tolist()}")
    print("-" * 50)

# Example search
query = "Python developer with machine learning experience"
print(f"\nSearching for: {query}\n")
results = search(query, top_k=5)

for r in results:
    print(f"ID: {r['id']}, Score: {r['score']:.4f}, Metadata: {r['metadata']}")
