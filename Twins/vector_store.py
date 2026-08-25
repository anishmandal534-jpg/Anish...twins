"""
Vector store — Qdrant.

Stores embedded text chunks for semantic retrieval.

The vector store is separate from the graph database:
- Qdrant = semantic/text retrieval
- Neo4j = structured persona facts/relationships

Requires a running Qdrant instance.
"""

import os
import uuid
from typing import List, Dict, Any

from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from embeddings import embed_text, embed_texts, VECTOR_SIZE


# ============================================================
# Configuration
# ============================================================

QDRANT_URL = os.getenv(
    "QDRANT_URL",
    "http://localhost:6333",
).strip()

COLLECTION = os.getenv(
    "QDRANT_COLLECTION",
    "persona_chunks",
).strip()


# Reuse one Qdrant client for the lifetime of the backend.
_client = None


# ============================================================
# Qdrant client
# ============================================================

def get_client() -> QdrantClient:
    """
    Return the shared Qdrant client.

    The collection is created automatically if it doesn't exist.
    """

    global _client

    if _client is None:

        _client = QdrantClient(
            url=QDRANT_URL,
        )

        _ensure_collection(_client)

    return _client


# ============================================================
# Collection setup
# ============================================================

def _ensure_collection(client: QdrantClient) -> None:
    """
    Create the persona collection if it does not already exist.
    """

    existing_collections = [
        collection.name
        for collection in client.get_collections().collections
    ]

    if COLLECTION in existing_collections:
        return

    print(
        f"[Qdrant] Creating collection '{COLLECTION}' "
        f"with vector size {VECTOR_SIZE}"
    )

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=qmodels.VectorParams(
            size=VECTOR_SIZE,
            distance=qmodels.Distance.COSINE,
        ),
    )

    print(
        f"[Qdrant] Collection '{COLLECTION}' created successfully."
    )


# ============================================================
# Insert / update text chunks
# ============================================================

def upsert_chunks(
    chunks: List[str],
    source: str,
) -> List[str]:
    """
    Embed and store text chunks in Qdrant.

    Each chunk gets:
        - a UUID
        - an embedding vector
        - the original text
        - the source filename/URL

    Returns:
        List of generated point IDs.
    """

    if not chunks:
        return []

    client = get_client()

    # Remove empty chunks.
    cleaned_chunks = [
        chunk.strip()
        for chunk in chunks
        if chunk and chunk.strip()
    ]

    if not cleaned_chunks:
        return []

    print(
        f"[Qdrant] Embedding {len(cleaned_chunks)} chunks "
        f"from source: {source}"
    )

    vectors = embed_texts(cleaned_chunks)

    if len(vectors) != len(cleaned_chunks):
        raise RuntimeError(
            "Embedding count does not match chunk count."
        )

    ids = [
        str(uuid.uuid4())
        for _ in cleaned_chunks
    ]

    points = []

    for chunk_id, text, vector in zip(
        ids,
        cleaned_chunks,
        vectors,
    ):

        points.append(
            qmodels.PointStruct(
                id=chunk_id,
                vector=vector,
                payload={
                    "text": text,
                    "source": source,
                },
            )
        )

    client.upsert(
        collection_name=COLLECTION,
        points=points,
    )

    print(
        f"[Qdrant] Stored {len(points)} chunks "
        f"from '{source}'."
    )

    return ids


# ============================================================
# Semantic search
# ============================================================

def search(
    query: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search Qdrant for the most semantically relevant chunks.

    Uses the current Qdrant query_points() API.

    Returns:

        [
            {
                "text": "...",
                "source": "...",
                "score": 0.91
            }
        ]
    """

    if not query or not query.strip():
        return []

    if top_k <= 0:
        return []

    client = get_client()

    # Convert the user's question into the same
    # embedding space used when storing documents.
    vector = embed_text(query)

    # Current Qdrant Python client API.
    response = client.query_points(
        collection_name=COLLECTION,
        query=vector,
        limit=top_k,
        with_payload=True,
        with_vectors=False,
    )

    results = []

    for point in response.points:

        payload = point.payload or {}

        text = payload.get(
            "text",
            "",
        )

        source = payload.get(
            "source",
            "unknown",
        )

        if not text:
            continue

        results.append(
            {
                "text": text,
                "source": source,
                "score": float(
                    point.score
                ),
            }
        )

    return results


# ============================================================
# Debug / health helpers
# ============================================================

def collection_info():
    """
    Return basic information about the Qdrant collection.

    Useful for debugging from the backend.
    """

    client = get_client()

    return client.get_collection(
        collection_name=COLLECTION,
    )


def list_chunks(
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Return a small sample of stored chunks.

    Useful for verifying that your resume/documents
    were actually ingested into Qdrant.
    """

    client = get_client()

    points, _ = client.scroll(
        collection_name=COLLECTION,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

    results = []

    for point in points:

        payload = point.payload or {}

        results.append(
            {
                "id": str(point.id),
                "text": payload.get(
                    "text",
                    "",
                ),
                "source": payload.get(
                    "source",
                    "unknown",
                ),
            }
        )

    return results