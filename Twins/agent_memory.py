from dotenv import load_dotenv
load_dotenv()
"""
Build-order step 5 (agent memory graph): logs each conversation turn as
a Memory node linked to a Session node, so future turns can recall
"we talked about this before" without replaying full chat history.
"""

from graph_store import get_driver


def log_turn(session_id: str, user_message: str, assistant_reply: str):
    if not session_id:
        session_id = "default"
    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MERGE (s:Session {id: $session_id})
            CREATE (m:Memory {user: $user_message, reply: $assistant_reply, ts: timestamp()})
            MERGE (s)-[:HAS_TURN]->(m)
            """,
            session_id=session_id, user_message=user_message, assistant_reply=assistant_reply,
        )


def recent_memory(session_id: str, limit: int = 5):
    if not session_id:
        session_id = "default"
    driver = get_driver()
    with driver.session() as session:
        recs = session.run(
            """
            MATCH (s:Session {id: $session_id})-[:HAS_TURN]->(m:Memory)
            RETURN m.user AS user, m.reply AS reply
            ORDER BY m.ts DESC LIMIT $limit
            """,
            session_id=session_id, limit=limit,
        )
        return [{"user": r["user"], "reply": r["reply"]} for r in recs][::-1]
