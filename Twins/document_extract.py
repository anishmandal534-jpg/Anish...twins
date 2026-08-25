"""
Minimal text extraction for uploaded documents.

This is a stand-in for real chunking/embedding — that lands with the
ingestion pipeline (build-order step 2). For now, extracted text is
passed back to the frontend and re-sent as inline context on each chat
turn, so you can see document-aware answers before the vector/graph
store exists.
"""

import io

from fastapi import UploadFile, HTTPException

MAX_CHARS_PER_DOC = 20_000  # keep any single doc from blowing out the context window


def extract_text(file: UploadFile, raw: bytes) -> str:
    name = (file.filename or "").lower()

    if name.endswith((".txt", ".md")):
        text = raw.decode("utf-8", errors="ignore")

    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError:
            raise HTTPException(status_code=500, detail="pypdf not installed — run pip install -r requirements.txt")
        reader = PdfReader(io.BytesIO(raw))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)

    elif name.endswith(".docx"):
        try:
            import docx
        except ImportError:
            raise HTTPException(status_code=500, detail="python-docx not installed — run pip install -r requirements.txt")
        document = docx.Document(io.BytesIO(raw))
        text = "\n".join(p.text for p in document.paragraphs)

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type for '{file.filename}'. Supported: .txt, .md, .pdf, .docx",
        )

    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail=f"Couldn't extract any text from '{file.filename}'.")

    truncated = len(text) > MAX_CHARS_PER_DOC
    return text[:MAX_CHARS_PER_DOC] + ("\n\n[...truncated...]" if truncated else "")
