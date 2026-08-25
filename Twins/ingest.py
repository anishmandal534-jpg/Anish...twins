"""
Build-order step 4 (+ feeds step 2's graph): the real ingestion pipeline.

For any piece of source text: chunk it, embed + store the chunks in
Qdrant, and run each chunk through the Claude extraction step to pull
out facts/opinions/relationships/events into Neo4j — with every graph
node tagged with the vector chunk_id it came from, so answers stay
traceable back to source.
"""

import os
from dotenv import load_dotenv
load_dotenv()

from chunking import chunk_text
from vector_store import upsert_chunks
from graph_store import write_extraction, init_schema
from graph_extract import extract_from_chunk

PERSONA_NAME = os.getenv("PERSONA_NAME", "The Persona")


def ingest_text(text: str, source_label: str, person_name: str = None) -> dict:
    person_name = person_name or PERSONA_NAME
    init_schema()

    chunks = chunk_text(text)
    if not chunks:
        return {"chunks_ingested": 0}

    chunk_ids = upsert_chunks(chunks, source_label)

    for chunk, chunk_id in zip(chunks, chunk_ids):
        extraction = extract_from_chunk(chunk, person_name)
        write_extraction(person_name, extraction, source_label, chunk_id)

    return {"chunks_ingested": len(chunks)}


def ingest_file(path: str, person_name: str = None) -> dict:
    from document_extract_standalone import extract_text_from_path
    text = extract_text_from_path(path)
    return ingest_text(text, source_label=os.path.basename(path), person_name=person_name)


def ingest_url(url: str, person_name: str = None) -> dict:
    import trafilatura
    downloaded = trafilatura.fetch_url(url)
    text = trafilatura.extract(downloaded) if downloaded else None
    if not text or not text.strip():
        raise ValueError(f"Could not extract readable text from {url}")
    return ingest_text(text, source_label=url, person_name=person_name)
