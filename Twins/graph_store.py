"""
Graph DB — Neo4j. Two things live here:

  - Persona knowledge graph: Person / Fact / Opinion / Topic / Entity /
    Event nodes, built by graph_extract.py during ingestion.
  - Agent memory: Session / Memory nodes, written by agent_memory.py as
    the chat runs.

Requires a running Neo4j instance (see README for the docker command).
"""

import os
from dotenv import load_dotenv
load_dotenv()

from neo4j import GraphDatabase

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    return _driver


def init_schema():
    driver = get_driver()
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT person_name IF NOT EXISTS "
            "FOR (p:Person) REQUIRE p.name IS UNIQUE"
        )
        session.run(
            "CREATE CONSTRAINT topic_name IF NOT EXISTS "
            "FOR (t:Topic) REQUIRE t.name IS UNIQUE"
        )
        session.run(
            "CREATE CONSTRAINT session_id IF NOT EXISTS "
            "FOR (s:Session) REQUIRE s.id IS UNIQUE"
        )


def write_extraction(person_name: str, extraction: dict, source: str, chunk_id: str):
    """extraction: {"facts": [...], "opinions": [{"topic","text"}, ...],
    "relationships": [{"target","type","description"}, ...],
    "events": [{"text","date"}, ...]} — as produced by graph_extract.py"""
    driver = get_driver()
    with driver.session() as session:
        session.run("MERGE (p:Person {name: $name})", name=person_name)

        for fact in extraction.get("facts", []):
            session.run(
                """
                MATCH (p:Person {name: $person})
                MERGE (f:Fact {text: $text})
                SET f.source = $source, f.chunk_id = $chunk_id
                MERGE (p)-[:HAS_FACT]->(f)
                """,
                person=person_name, text=fact, source=source, chunk_id=chunk_id,
            )

        for op in extraction.get("opinions", []):
            topic = (op.get("topic") or "general").strip() or "general"
            text = op.get("text", "")
            if not text:
                continue
            session.run(
                """
                MATCH (p:Person {name: $person})
                MERGE (t:Topic {name: $topic})
                MERGE (o:Opinion {text: $text})
                SET o.source = $source, o.chunk_id = $chunk_id
                MERGE (p)-[:HAS_OPINION_ABOUT]->(o)
                MERGE (o)-[:ABOUT]->(t)
                """,
                person=person_name, topic=topic, text=text,
                source=source, chunk_id=chunk_id,
            )

        for rel in extraction.get("relationships", []):
            target = rel.get("target", "")
            if not target:
                continue
            rel_type = (rel.get("type") or "RELATED_TO").upper().replace(" ", "_")
            rel_type = "".join(ch for ch in rel_type if ch.isalnum() or ch == "_") or "RELATED_TO"
            desc = rel.get("description", "")
            session.run(
                f"""
                MATCH (p:Person {{name: $person}})
                MERGE (e:Entity {{name: $target}})
                MERGE (p)-[r:{rel_type}]->(e)
                SET r.description = $desc, r.source = $source
                """,
                person=person_name, target=target, desc=desc, source=source,
            )

        for ev in extraction.get("events", []):
            text = ev.get("text", "")
            if not text:
                continue
            date = ev.get("date", "")
            session.run(
                """
                MATCH (p:Person {name: $person})
                MERGE (ev:Event {text: $text})
                SET ev.date = $date, ev.source = $source, ev.chunk_id = $chunk_id
                MERGE (p)-[:EXPERIENCED]->(ev)
                """,
                person=person_name, text=text, date=date,
                source=source, chunk_id=chunk_id,
            )


def query_relevant(person_name: str, keywords: list, limit: int = 8):
    """Shallow (1-hop) keyword-matched retrieval across facts/opinions/events.
    Simple on purpose — swap in an LLM-driven entity/topic extraction step
    ahead of this if keyword matching feels too blunt once you're tuning."""
    if not keywords:
        return []
    driver = get_driver()
    results = []
    with driver.session() as session:
        for kw in keywords:
            recs = session.run(
                """
                MATCH (p:Person {name: $person})-[:HAS_FACT|HAS_OPINION_ABOUT|EXPERIENCED]->(n)
                WHERE toLower(n.text) CONTAINS toLower($kw)
                RETURN labels(n)[0] AS type, n.text AS text
                LIMIT $limit
                """,
                person=person_name, kw=kw, limit=limit,
            )
            for r in recs:
                results.append({"type": r["type"], "text": r["text"]})

    seen = set()
    unique = []
    for r in results:
        key = (r["type"], r["text"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique[:limit]
