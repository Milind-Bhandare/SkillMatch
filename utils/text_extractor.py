# utils/text_extractor.py
from pathlib import Path
import pdfplumber
import docx


def extract_text(path):
    path = Path(path)
    suf = path.suffix.lower()
    if suf == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if suf == ".pdf":
        text = []
        with pdfplumber.open(path) as pdf:
            for p in pdf.pages:
                text.append(p.extract_text() or "")
        return "\n".join(text)
    if suf in [".docx", ".doc"]:
        try:
            doc = docx.Document(path)
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            return ""
    # fallback
    return path.read_text(encoding="utf-8", errors="ignore")
