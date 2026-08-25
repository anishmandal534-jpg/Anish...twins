"""
Run after extract_data.py. Ingests every .txt file in data/clean/ into
the vector store + graph DB.

Run from the backend/ folder, with Qdrant and Neo4j both running:
    python ingest_cli.py
"""

import os

from ingest import ingest_file

CLEAN_DIR = "../data/clean"


def main():
    if not os.path.isdir(CLEAN_DIR):
        print(f"No {CLEAN_DIR}/ folder found — run extract_data.py first.")
        return

    files = sorted(f for f in os.listdir(CLEAN_DIR) if f.endswith(".txt"))
    if not files:
        print(f"No .txt files found in {CLEAN_DIR}/ — run extract_data.py first.")
        return

    print(f"Ingesting {len(files)} file(s)...\n")
    total_chunks = 0
    for fname in files:
        path = os.path.join(CLEAN_DIR, fname)
        print(f"  {fname} ...", end=" ", flush=True)
        result = ingest_file(path)
        total_chunks += result["chunks_ingested"]
        print(f"{result['chunks_ingested']} chunks")

    print(f"\nDone. {total_chunks} chunks embedded + extracted across {len(files)} file(s).")


if __name__ == "__main__":
    main()
