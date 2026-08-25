"""
Simple character-based chunker with overlap. Good enough to start with —
swap for a token-aware splitter later if chunk boundaries start cutting
sentences awkwardly.
"""


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150):
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end == n:
            break
        start = end - overlap
    return chunks
