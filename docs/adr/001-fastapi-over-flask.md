# ADR 001: FastAPI over Flask

## Status

Accepted

## Context

Sentinel requires a web framework to expose an OpenAI-compatible API, handle middleware (rate limiting, tracing, metrics), and integrate with async LLM provider clients. The framework must support high throughput, automatic API documentation, and strong typing for request/response validation.

Flask is widely used and has a large ecosystem, but it is synchronous by default. Async support in Flask 2.0+ exists but is less mature than frameworks designed for async from the ground up. LLM API calls are I/O-bound and benefit from async concurrency.

## Decision

We chose **FastAPI** over Flask for the following reasons:

1. **Native async support** — FastAPI is built on Starlette and supports `async def` handlers natively. This allows non-blocking I/O when calling OpenAI, Anthropic, and Redis, improving throughput under load.

2. **OpenAPI (Swagger) out of the box** — FastAPI generates interactive API documentation at `/docs` automatically from Pydantic models and route signatures. No additional tooling required.

3. **Pydantic integration** — Request and response validation is built-in via Pydantic. This reduces boilerplate and ensures type safety across the API boundary.

4. **Performance** — FastAPI/Starlette is among the fastest Python web frameworks in benchmarks, important for a gateway that proxies every request.

5. **Modern Python** — Type hints are first-class. FastAPI leverages them for validation, documentation, and IDE support.

## Consequences

- **Positive**: Async handlers enable efficient concurrent LLM calls; developers get auto-generated docs; Pydantic catches invalid payloads early.
- **Negative**: FastAPI has a smaller ecosystem than Flask; some middleware patterns differ from Flask's decorator-based approach.
- **Neutral**: Team must be familiar with async/await; dependency injection is via FastAPI's `Depends()` rather than Flask extensions.
