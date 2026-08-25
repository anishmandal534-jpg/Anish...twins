"""Extract structured persona data using an OpenRouter model."""
import json
import os
import re
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/auto").strip()
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY) if API_KEY else None
EXTRA_HEADERS = {
    "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:8000"),
    "X-Title": os.getenv("OPENROUTER_SITE_NAME", "Persona Twin"),
}

EXTRACTION_PROMPT = """You extract structured persona information from text written by or about {person}.

Return ONLY valid JSON. No markdown fences and no commentary.
Required shape:
{{
  "facts": ["short factual statement"],
  "opinions": [{{"topic": "short topic", "text": "opinion in third person"}}],
  "relationships": [{{"target": "person/company/place", "type": "WORKED_AT", "description": "short description"}}],
  "events": [{{"text": "what happened", "date": "approximate date or empty string"}}]
}}

Only include information explicitly supported by the text. Do not invent or infer.
If a category has nothing, use [].

Text:
\"\"\"
{text}
\"\"\"
"""

def _clean_json(raw: str) -> dict:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end+1])
            except json.JSONDecodeError:
                pass
    return {"facts": [], "opinions": [], "relationships": [], "events": []}

def extract_from_chunk(text: str, person_name: str) -> dict:
    if client is None:
        raise RuntimeError("OPENROUTER_API_KEY is missing.")
    prompt = EXTRACTION_PROMPT.format(person=person_name, text=text)
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=1024,
        temperature=0,
        extra_headers=EXTRA_HEADERS,
        messages=[{"role": "user", "content": prompt}],
    )
    data = _clean_json(response.choices[0].message.content if response.choices else "")
    for key in ("facts", "opinions", "relationships", "events"):
        if not isinstance(data.get(key), list):
            data[key] = []
    return data
