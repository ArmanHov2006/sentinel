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

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create `.env` file:**
   ```env
   SENTINEL_ENV=development
   OPENAI_API_KEY=sk-your-key-here
   OPENAI_BASE_URL=https://api.openai.com/v1
   REQUEST_TIMEOUT_SECONDS=60
   HOST=0.0.0.0
   PORT=8000
   ```

3. **Run tests:**
   ```bash
   export PYTHONPATH=src  # On Windows: $env:PYTHONPATH="src"
   python -m pytest tests/ -v
   ```

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
