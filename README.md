# Sentinel

An LLM gateway and proxy with guardrails, PII detection, and quality evaluation.

## Project Structure

```
sentinel/
├── src/
│   └── sentinel/
│       ├── domain/          # Domain models and exceptions
│       ├── core/            # Configuration, HTTP client, telemetry
│       ├── providers/       # LLM provider integrations
│       ├── services/        # Business logic
│       └── api/             # FastAPI routes and schemas
├── tests/                   # Test suite
└── requirements.txt         # Python dependencies
```

## Features

- **Multi-Provider Support**: OpenAI, Anthropic, and more via LiteLLM
- **Guardrails**: PII detection, content filtering, banned keyword checking
- **Quality Evaluation**: Async Judge model scoring
- **Streaming Support**: Server-Sent Events (SSE) for streaming responses
- **Structured Logging**: JSON-formatted telemetry without logging sensitive content
- **Caching**: Redis-backed request/response caching

## Setup

1. **Run Redis via Docker** (needed for caching; bridges WSL/Windows when using Docker Desktop):
   ```bash
   docker run -d --name redis -p 6379:6379 redis:latest
   ```
   Verify:
   ```bash
   docker exec redis redis-cli ping
   ```
   Should return: `PONG`.  
   If a container named `redis` already exists, remove it first: `docker rm -f redis`, then run the `docker run` command again.

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create `.env` file:**

   Use **Groq** (optional; preferred if set):
   ```env
   GROQ_API_KEY=gsk-your-groq-key-here
   # GROQ_BASE_URL defaults to https://api.groq.com/openai/v1
   ```

   Or use **OpenAI**:
   ```env
   OPENAI_API_KEY=sk-your-key-here
   OPENAI_BASE_URL=https://api.openai.com/v1
   ```

   Other options:
   ```env
   SENTINEL_ENV=development
   REQUEST_TIMEOUT_SECONDS=60
   HOST=0.0.0.0
   PORT=8000
   ```
   If both `GROQ_API_KEY` and `OPENAI_API_KEY` are set, Groq is used.

   **Groq (free tier):** Get a key at [console.groq.com](https://console.groq.com) → API Keys → Create API Key. Put `GROQ_API_KEY=gsk_...` in `.env`. (You can instead use `OPENAI_API_KEY=gsk_...` and `OPENAI_BASE_URL=https://api.groq.com/openai/v1`; the app treats that as the OpenAI-style provider and will call Groq.)

   **Model names for Groq** (use these in requests instead of `gpt-4`):
   - `llama-3.1-8b-instant` — very fast, good quality  
   - `llama-3.3-70b-versatile` — fast, great quality  
   - `mixtral-8x7b-32768` — fast, great quality  

4. **Run tests:**
   ```bash
   export PYTHONPATH=src  # On Windows: $env:PYTHONPATH="src"
   python -m pytest tests/ -v
   ```

5. **End-to-end checks** (Redis running, `.env` with Groq key, server running):
   - **Redis:** `docker exec redis redis-cli ping` → `PONG`
   - **Start server:** `PYTHONPATH=src uvicorn sentinel.main:app --port 8000` (or `$env:PYTHONPATH="src"; python -m uvicorn sentinel.main:app --port 8000` on Windows)
   - **Health:** `GET http://localhost:8000/health` → `{"status":"healthy",...}`
   - **Chat (cache miss):** `POST http://localhost:8000/v1/chat/completions` with body `{"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":"Hello"}],"temperature":0.7}` → real LLM reply
   - **Cache keys:** `docker exec redis redis-cli KEYS "llm:*"` → at least one key after a non-streaming chat
   - **Chat (cache hit):** same POST again → same response, served from cache
   - **Streaming:** same URL with `"stream": true` → SSE chunks, then `data: [DONE]`

## Development

The project uses:
- **FastAPI** for the web framework
- **Pydantic** for data validation
- **Presidio** for PII detection
- **Redis** for caching
- **Structlog** for structured logging

## Status

✅ Session 1: Domain models, exceptions, config, HTTP client, telemetry
✅ Sentinel Bridge: Guardrails, PII detection, Judge scoring, streaming models
🔄 Week 2: FastAPI + LiteLLM Integration (in progress)
