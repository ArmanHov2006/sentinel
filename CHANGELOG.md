# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2025-03-01

### Added

- **Structured logging** — structlog with JSON output, correlation IDs via `X-Request-ID`, and configurable log levels
- **API key authentication** — Virtual API keys stored in Redis for M2M auth; optional `REQUIRE_AUTH` and `SENTINEL_MASTER_KEY`
- **OpenTelemetry tracing** — OTLP export to collector; trace context propagation through the request pipeline
- **Test suite** — Unit and integration tests with pytest; coverage reporting; tests for auth, rate limiter, providers, PII shield
- **CI/CD** — GitHub Actions workflow: Ruff lint/format, pytest with coverage, Docker build and smoke test
- **Security hardening** — Security headers (X-Content-Type-Options, X-Frame-Options, HSTS in production); fail-open behavior for optional components

### Changed

- N/A (initial release)

### Fixed

- N/A (initial release)

---

## Conventional Commits Reference

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `refactor:` — Code change that neither fixes a bug nor adds a feature
- `test:` — Adding or updating tests
- `chore:` — Maintenance (deps, config, etc.)
