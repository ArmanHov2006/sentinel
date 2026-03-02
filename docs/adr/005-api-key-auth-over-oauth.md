# ADR 005: API Key Auth over OAuth

## Status

Accepted

## Context

Sentinel may be deployed in environments where multiple clients (applications, services) need to access the gateway. We need an authentication mechanism that:

- Identifies and authorizes each client
- Supports rate limiting and usage tracking per client
- Is simple to integrate for machine-to-machine (M2M) scenarios

OAuth 2.0 / OIDC is the standard for user-facing applications but adds complexity (token endpoints, refresh flows, JWTs) that may be unnecessary for server-to-server API access.

## Decision

We use **virtual API keys** for M2M authentication:

1. **Key format** — Keys are generated as `sk-sent-{hex}` (e.g., `sk-sent-a1b2c3...`). Only a hash is stored; plaintext is returned once at creation.
2. **Storage** — Keys are stored in Redis with metadata: name, owner, allowed models, rate limit (RPM), monthly token budget.
3. **Validation** — On each request, the `Authorization: Bearer <key>` header is validated. The key hash is looked up; if valid and active, the request proceeds with the key's rate limits and model restrictions applied.
4. **Admin API** — A master key (`SENTINEL_MASTER_KEY`) or admin endpoint allows creating, listing, and revoking keys when `REQUIRE_AUTH` is enabled.

OAuth can be added later as an alternative auth method if user-facing flows are required.

## Consequences

- **Positive**: Simple integration (single header); no token refresh logic; per-key rate limits and budgets; keys can be revoked instantly via Redis.
- **Negative**: API keys are long-lived; compromise requires rotation. No built-in user consent flows.
- **Neutral**: Auth is optional (`REQUIRE_AUTH=false` by default) so existing deployments are unaffected.
