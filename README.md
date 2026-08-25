Persona Twin + OpenRouter
This version uses OpenRouter's OpenAI-compatible API at https://openrouter.ai/api/v1. Keep the API key only in backend/.env, never in frontend JavaScript or Git.

Requirements
Windows 10/11
Python 3.10+
Docker Desktop
An OpenRouter API key
Internet access for the first embedding-model download
1. Create databases
In PowerShell from the project root:

docker run -d --name persona-qdrant -p 6333:6333 -v "${PWD}/qdrant_data:/qdrant/storage" qdrant/qdrant
docker run -d --name persona-neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/change-me neo4j:5
If containers already exist:

docker start persona-qdrant persona-neo4j
Check:

Qdrant: http://localhost:6333/dashboard
Neo4j: http://localhost:7474 (neo4j / change-me)
2. Backend
cd persona-twin�ackend
py -3 -m venv venv
.�env\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
notepad .env
Set:

OPENROUTER_API_KEY=YOUR_NEW_KEY
OPENROUTER_MODEL=openrouter/auto
NEO4J_PASSWORD=change-me
PERSONA_NAME=Your Name
PERSONA_BIO=Short description of the persona.
openrouter/auto automatically routes the request to a suitable model. You can replace it with a specific current model slug from the OpenRouter model catalog.

3. Start API
uvicorn main:app --reload --port 8000
Open:

http://localhost:8000/health
http://localhost:8000/docs
Health should show "openrouter_configured": true.

4. Add source data
Put TXT/MD/PDF/DOCX files in: persona-twin\data aw_sources\

For WhatsApp, use a filename ending in _whatsapp.txt. The parser keeps messages matching PERSONA_NAME.

Then:

cd persona-twin�ackend
.�env\Scripts\Activate.ps1
python extract_data.py
python ingest_cli.py
Ingestion creates embeddings in Qdrant and structured persona information in Neo4j. Start with a small file first.

5. Run frontend
With the backend running, open another PowerShell:

cd persona-twinrontend
python -m http.server 5500
Open: http://localhost:5500

In Settings, keep Backend URL as: http://localhost:8000

6. Test
Browser
Type: Tell me about yourself.

API
Open http://localhost:8000/docs and test /chat.

PowerShell example:

$body = @{
  messages = @(
    @{ role = "user"; content = "Hello, introduce yourself." }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod http://localhost:8000/chat -Method Post -ContentType "application/json" -Body $body
7. Troubleshooting
openrouter_configured: false: check .env is inside backend and restart Uvicorn.
401: rotate/recreate the OpenRouter key and paste the new key into .env.
404 model: choose a valid model slug from OpenRouter's model catalog.
Qdrant/Neo4j errors: run docker ps; both containers must be running.
Neo4j auth error: NEO4J_PASSWORD must match the password used when the container was created.
First embedding run is slow because all-MiniLM-L6-v2 downloads locally.
Ingestion is intentionally slower because each chunk is sent to the OpenRouter model for extraction.
OpenRouter notes
OpenRouter is OpenAI-compatible: the important settings are the base URL, Bearer API key, and provider/model model slug. HTTP-Referer and X-Title are optional attribution headers.
