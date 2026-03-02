# Contributing to Sentinel

Thank you for your interest in contributing to Sentinel. This document covers setup, the PR process, and code style.

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/ArmanHov2006/sentinel.git
cd sentinel
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

Or with uv:

```bash
uv pip install -r requirements.txt
```

### 3. Configure environment

Create a `.env` file in the project root (or copy from `.env.example` if it exists). Set at least:

- `OPENAI_API_KEY` — for chat and optional judge
- `REDIS_HOST` — `localhost` if running Redis locally

### 4. Run tests

```bash
export PYTHONPATH=src
pytest -v
```

---

## Pull Request Process

1. **Branch** — Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Test** — Ensure all tests pass:
   ```bash
   PYTHONPATH=src pytest -v --cov=sentinel
   ```

3. **Lint** — Run Ruff:
   ```bash
   ruff check src tests
   ruff format src tests
   ```

4. **Commit** — Use [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat: add semantic cache`
   - `fix: correct rate limit window calculation`
   - `docs: update README`

5. **PR** — Open a pull request. CI will run Ruff and pytest. Address any feedback before merge.

---

## Code Style

### Ruff

- **Linting**: `ruff check src tests`
- **Formatting**: `ruff format src tests`
- Line length: 100. See `ruff.toml` for full config.

### Logging

- Use **structlog** for all application logging.
- Prefer structured fields over string interpolation:
  ```python
  logger.info("request_processed", request_id=req_id, latency_ms=latency)
  ```

### Data Models

- Use **frozen dataclasses** for immutable value objects:
  ```python
  @dataclass(frozen=True)
  class APIKeyData:
      key_hash: str
      name: str
  ```

### Resilience

- **Fail-open** — Security and resilience components (PII shield, circuit breaker, cache) should fail open when dependencies (Redis, models) are unavailable. Log warnings and continue serving requests where safe.
