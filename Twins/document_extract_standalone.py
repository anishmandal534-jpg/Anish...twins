"""
Same file-type support as document_extract.py, but reading from a plain
filesystem path — for CLI scripts (extract_data.py, ingest.py) rather than
FastAPI upload requests.
"""

import os


def extract_text_from_path(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()

    if ext in (".txt", ".md"):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    elif ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    elif ext == ".docx":
        import docx
        document = docx.Document(path)
        return "\n".join(p.text for p in document.paragraphs)

    else:
        raise ValueError(f"Unsupported file type: {ext}")
