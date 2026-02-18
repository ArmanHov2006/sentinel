---
name: Sentinel Completion Plan
overview: Create a comprehensive, self-contained text file containing every remaining task to finish the Sentinel project -- with exact file paths, code patterns, specifications, and dependency order -- designed to be handed directly to Claude as a prompt.
todos:
  - id: create-plan-file
    content: Create SENTINEL_COMPLETION_PLAN.txt with all 8 phases, every file spec, code patterns, and test requirements -- self-contained for Claude
    status: pending
isProject: false
---

# Sentinel Project Completion Plan

**Note:** This file (`Complete-Plan.md`) is the plan. The deliverable is a separate file `SENTINEL_COMPLETION_PLAN.txt` to be generated at the project root with full specifications for each phase.

## What This Plan Does

Generate a single `SENTINEL_COMPLETION_PLAN.txt` file at the project root. This file will be a self-contained, copy-paste-ready document containing:

1. **Current codebase snapshot** -- every existing file path, its purpose, and key patterns/conventions used (imports, class structure, error handling style, test style)
2. **Every missing file** -- listed in exact dependency order with full specifications
3. **Every file that needs modification** -- with precise descriptions of what to add/change
4. **Exact implementation order** (8 phases, each with prerequisites)
5. **Code conventions** extracted from existing code so Claude matches the style exactly
6. **Full test specifications** for every missing test file
7. **Infrastructure specifications** for Docker, monitoring, CI, and docs

The file will be structured so that someone (or Claude) can work through it phase by phase, top to bottom, and end up with the complete project matching the spec.

---

## Phase Order (8 Phases)

### Phase 1: New Domain Models and Schemas (no dependencies on missing code)

- `src/sentinel/auth/models.py` -- Tenant, APIKey dataclasses
- `src/sentinel/api/schemas/usage.py` -- Usage response Pydantic models
- `src/sentinel/api/schemas/audit.py` -- Audit response Pydantic models
- Add `auth/__init__.py` (the `shield/` package already exists)

### Phase 2: Core Infrastructure Additions

- `src/sentinel/core/prometheus.py` -- Prometheus metrics export using the existing `MetricsCollector` pattern from [core/metrics.py](src/sentinel/core/metrics.py)

### Phase 3: New Services (depend on domain models + Redis pattern from [services/cache.py](src/sentinel/services/cache.py))

- `src/sentinel/services/cost.py` -- TokenCostCalculator
- `src/sentinel/services/audit.py` -- AuditService (Redis-backed)
- `src/sentinel/services/semantic_cache.py` -- SemanticCache (embeddings + cosine similarity)
- `src/sentinel/services/judge.py` -- JudgeService (LLM-as-Judge)

### Phase 4: Auth Module (depends on Redis, domain models)

- `src/sentinel/auth/__init__.py`
- `src/sentinel/auth/api_keys.py` -- APIKeyManager
- `src/sentinel/auth/middleware.py` -- AuthMiddleware (FastAPI middleware)

### Phase 5: New API Endpoints (depend on services + auth)

- Split [api/routes/health.py](src/sentinel/api/routes/health.py) to add `/health/ready` and `/health/live`
- `src/sentinel/api/v1/usage.py` -- GET `/v1/usage`
- `src/sentinel/api/v1/audit.py` -- GET `/v1/audit`, GET `/v1/audit/{request_id}`
- Add Prometheus endpoint to [api/routes/metrics.py](src/sentinel/api/routes/metrics.py)
- Modify [api/v1/chat.py](src/sentinel/api/v1/chat.py) to integrate cost calculation, audit logging, and auth

### Phase 6: Wire Everything in main.py

- Modify [main.py](src/sentinel/main.py) to initialize and register all new services, middleware, and routes

### Phase 7: Infrastructure and Monitoring

- Update [docker-compose.yml](docker-compose.yml): add Prometheus + Grafana if not present; ensure Prometheus has a volume mount for `./monitoring/prometheus.yml` (scrape config), Grafana has mounts for provisioning and dashboards, and Prometheus `depends_on` Sentinel (with health condition)
- Create `monitoring/prometheus.yml` (scrape Sentinel at `http://sentinel:8000/metrics/prometheus`)
- Create `monitoring/grafana/provisioning/datasources/prometheus.yml`
- Create `monitoring/grafana/provisioning/dashboards/dashboards.yml`
- Create `monitoring/grafana/dashboards/sentinel.json` (10 panels)
- Update [Dockerfile](Dockerfile) to multi-stage build
- Create `docker-compose.dev.yml`
- Split [requirements.txt](requirements.txt) into prod + `requirements-dev.txt`
- Update [.env.example](.env.example) with new variables

### Phase 8: Tests, Docs, Polish

- 9 new test files + expand existing ones
- `tests/test_integration.py` (20+ tests)
- `loadtests/locustfile.py` + `loadtests/mock_provider.py`
- `scripts/demo.py`
- `ARCHITECTURE.md`
- Update [README.md](README.md)
- Update [.github/workflows/ci.yml](.github/workflows/ci.yml)
- Remove TODO in main.py, run ruff

---

## Key Conventions to Embed in the Document

Extracted from existing code so Claude matches the style:

- **Imports**: stdlib first, then third-party, then `sentinel.*` (ruff isort, `known-first-party = ["sentinel"]`)
- **Logging**: `logger = logging.getLogger(__name__)` at module level
- **Error handling**: fail-open pattern (log warning, continue without feature)
- **Redis access**: always wrap in try/except, return safe defaults on failure
- **Settings**: Pydantic `BaseSettings` with `SettingsConfigDict(env_prefix=...)`
- **Domain models**: frozen dataclasses in `domain/models.py`
- **Schemas**: Pydantic `BaseModel` with `Field()` descriptions
- **Tests**: class-based grouping (`class TestXxx`), `@pytest.mark.anyio` for async, `sys.path.insert` at top, `AsyncMock` for Redis
- **Middleware**: extend `BaseHTTPMiddleware` with `dispatch()` method
- **Line length**: 100 (ruff config)
- **Quote style**: double quotes
- **No comments that just narrate** -- only explain non-obvious intent

---

## File to Create

A single file: `c:\Users\arman\sentinel\SENTINEL_COMPLETION_PLAN.txt`

This file will contain all 8 phases with:

- Exact file paths
- Full class/method signatures
- Field specifications
- Test case names and assertions
- Docker/YAML configurations
- The complete spec text from the user's plan (embedded as reference)
- Cross-references to existing code patterns

Estimated length: ~2000-3000 lines of detailed specification.

---

## Quick Reference: Browser URLs (after `docker-compose up`)

| Service        | URL                     |
|----------------|-------------------------|
| Sentinel (API, dashboard, `/health`, `/metrics`, `/docs`) | http://localhost:8000   |
| Prometheus     | http://localhost:9090   |
| Grafana        | http://localhost:3000   |
| Redis Commander (with `--profile dev`) | http://localhost:8081 |
