"""
Persona Twin backend using OpenRouter's OpenAI-compatible API.

Run from the backend folder:

    python -m uvicorn main:app --reload --port 8000
"""

import os
from typing import List, Literal, Optional

from dotenv import load_dotenv

# ============================================================
# Load backend/.env explicitly
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")

load_dotenv(
    dotenv_path=ENV_FILE,
    override=True,
)

from openai import OpenAI
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from document_extract import extract_text
from persona_prompt import build_persona_context
from agent_memory import log_turn
from ingest import ingest_text, ingest_url


# ============================================================
# OpenRouter configuration
# ============================================================

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    "",
).strip()

MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openrouter/auto",
).strip()

SITE_URL = os.getenv(
    "OPENROUTER_SITE_URL",
    "http://localhost:8000",
).strip()

SITE_NAME = os.getenv(
    "OPENROUTER_SITE_NAME",
    "Persona Twin",
).strip()

MAX_TOKENS = int(
    os.getenv(
        "OPENROUTER_MAX_TOKENS",
        "1024",
    )
)

TEMPERATURE = float(
    os.getenv(
        "OPENROUTER_TEMPERATURE",
        "0.7",
    )
)


# ============================================================
# Create OpenRouter client
# ============================================================

if not API_KEY or API_KEY.startswith("your-"):

    client = None

else:

    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=API_KEY,
    )


# ============================================================
# FastAPI application
# ============================================================

app = FastAPI(
    title="Persona Twin — OpenRouter Backend",
    version="1.1.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# OpenRouter headers
# ============================================================

EXTRA_HEADERS = {
    "HTTP-Referer": SITE_URL,
    "X-Title": SITE_NAME,
}


MAX_UPLOAD_BYTES = 15 * 1024 * 1024


# ============================================================
# Data models
# ============================================================

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class DocumentContext(BaseModel):
    filename: str
    text: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    documents: Optional[List[DocumentContext]] = None
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    reply: str
    model: str


class UploadResponse(BaseModel):
    filename: str
    text: str
    char_count: int


class IngestUrlRequest(BaseModel):
    url: str


# ============================================================
# Root endpoint
# ============================================================

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Persona Twin Backend",
        "provider": "OpenRouter",
        "health": "/health",
        "chat": "/chat",
        "openrouter_test": "/api/openrouter-test",
    }


# ============================================================
# Health check
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "openrouter_configured": client is not None,
        "model": MODEL,
    }


# ============================================================
# Backend configuration
# ============================================================

@app.get("/api/config")
def config():
    return {
        "provider": "openrouter",
        "model": MODEL,
        "base_url": OPENROUTER_BASE_URL,
    }


# ============================================================
# OpenRouter connection test
# ============================================================

@app.get("/api/openrouter-test")
def openrouter_test():

    if client is None:

        raise HTTPException(
            status_code=500,
            detail=(
                "OpenRouter API key is missing. "
                "Make sure backend/.env contains "
                "OPENROUTER_API_KEY=YOUR_NEW_KEY "
                "and restart the server."
            ),
        )

    try:

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Reply with exactly: "
                        "OpenRouter connection successful"
                    ),
                }
            ],
            max_tokens=20,
            temperature=0,
            extra_headers=EXTRA_HEADERS,
        )

    except Exception as e:

        print(
            f"[Persona Twin] OpenRouter test failed: {e}"
        )

        raise HTTPException(
            status_code=502,
            detail=f"OpenRouter connection failed: {e}",
        )

    if not response.choices:

        raise HTTPException(
            status_code=502,
            detail="OpenRouter returned no choices.",
        )

    reply = (
        response.choices[0].message.content
        or ""
    )

    return {
        "status": "success",
        "model": getattr(
            response,
            "model",
            MODEL,
        ),
        "reply": reply,
    }


# ============================================================
# Upload document
# ============================================================

@app.post(
    "/api/upload",
    response_model=UploadResponse,
)
async def upload(
    file: UploadFile = File(...),
):

    raw = await file.read()

    if len(raw) > MAX_UPLOAD_BYTES:

        raise HTTPException(
            status_code=413,
            detail="File too large (max 15MB).",
        )

    try:

        text = extract_text(
            file,
            raw,
        )

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=f"Could not read file: {e}",
        )

    return UploadResponse(
        filename=file.filename or "upload",
        text=text,
        char_count=len(text),
    )


# ============================================================
# Ingest document
# ============================================================

@app.post("/api/ingest/file")
async def ingest_file_endpoint(
    file: UploadFile = File(...),
):

    raw = await file.read()

    if len(raw) > MAX_UPLOAD_BYTES:

        raise HTTPException(
            status_code=413,
            detail="File too large (max 15MB).",
        )

    try:

        text = extract_text(
            file,
            raw,
        )

        return ingest_text(
            text,
            source_label=file.filename or "upload",
        )

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=f"Ingestion failed: {e}",
        )


# ============================================================
# Ingest URL
# ============================================================

@app.post("/api/ingest/url")
def ingest_url_endpoint(
    req: IngestUrlRequest,
):

    try:

        return ingest_url(req.url)

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=f"Ingestion failed: {e}",
        )


# ============================================================
# Chat
# ============================================================

@app.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    req: ChatRequest,
):

    # --------------------------------------------------------
    # Validate messages
    # --------------------------------------------------------

    if not req.messages:

        raise HTTPException(
            status_code=400,
            detail="messages cannot be empty",
        )

    # --------------------------------------------------------
    # Check OpenRouter
    # --------------------------------------------------------

    if client is None:

        raise HTTPException(
            status_code=500,
            detail=(
                "OPENROUTER_API_KEY is missing. "
                "Put your API key in backend/.env "
                "and restart the server."
            ),
        )

    # --------------------------------------------------------
    # Get latest user message
    # --------------------------------------------------------

    last_user_msg = next(
        (
            m.content
            for m in reversed(req.messages)
            if m.role == "user"
        ),
        "",
    )

    # --------------------------------------------------------
    # Get document context
    # --------------------------------------------------------

    extra_docs = (
        [
            d.model_dump()
            for d in req.documents
        ]
        if req.documents
        else None
    )

    # --------------------------------------------------------
    # Build Persona Twin system prompt
    # --------------------------------------------------------

    try:

        system_prompt = build_persona_context(
            last_user_msg,
            extra_documents=extra_docs,
        )

    except Exception as e:

        print(
            f"[Persona Twin] Persona retrieval unavailable: {e}"
        )

        system_prompt = (
            "You are the user's Persona Twin. "
            "Answer naturally and accurately. "
            "Speak in first person when appropriate. "
            "Do not invent personal facts. "
            "If you do not know something, say so."
        )

    # --------------------------------------------------------
    # Build messages for OpenRouter
    # --------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    messages += [
        {
            "role": m.role,
            "content": m.content,
        }
        for m in req.messages
    ]

    # --------------------------------------------------------
    # Send request to OpenRouter
    # --------------------------------------------------------

    try:

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            extra_headers=EXTRA_HEADERS,
        )

    except Exception as e:

        print(
            f"[Persona Twin] OpenRouter request failed: {e}"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                f"OpenRouter request failed: {e}"
            ),
        )

    # --------------------------------------------------------
    # Check response
    # --------------------------------------------------------

    if not response.choices:

        raise HTTPException(
            status_code=502,
            detail="OpenRouter returned no choices.",
        )

    reply_text = (
        response.choices[0]
        .message
        .content
        or ""
    )

    if not reply_text.strip():

        raise HTTPException(
            status_code=502,
            detail="OpenRouter returned an empty response.",
        )

    # --------------------------------------------------------
    # Save memory
    # --------------------------------------------------------

    try:

        log_turn(
            req.session_id or "default",
            last_user_msg,
            reply_text,
        )

    except Exception as e:

        print(
            f"[Persona Twin] Memory logging failed: {e}"
        )

        system_prompt = (
        "You are the user's Persona Twin. "
        "Answer naturally and accurately. "
        "Do not invent personal facts. "
        "If you do not know something, say so."
    )

    # --------------------------------------------------------
    # Return response
    # --------------------------------------------------------

    return ChatResponse(
        reply=reply_text,
        model=(
            getattr(
                response,
                "model",
                MODEL,
            )
            or MODEL
        ),
    )