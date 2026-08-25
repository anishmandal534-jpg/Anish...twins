"""
Local text embeddings (no external API key needed beyond your Anthropic
key for chat/extraction). Uses sentence-transformers, downloaded once and
cached locally.
"""

from sentence_transformers import SentenceTransformer

_model = None
MODEL_NAME = "all-MiniLM-L6-v2"  # 384-dim, fast, good enough for style retrieval
VECTOR_SIZE = 384


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_text(text: str):
    return get_model().encode(text).tolist()


def embed_texts(texts):
    return get_model().encode(texts).tolist()
