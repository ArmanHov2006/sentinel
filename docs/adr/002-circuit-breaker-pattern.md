# ADR 002: Circuit Breaker Pattern

## Status

Accepted

## Context

When an LLM provider (OpenAI, Anthropic) experiences outages or high latency, repeated retries from Sentinel can exacerbate the problem and waste resources. Without protection, a failing provider can cause cascading failures, timeouts, and poor user experience.

We need a mechanism to stop sending requests to a failing provider temporarily, allow it to recover, and then probe it again without manual intervention.

## Decision

We implement a **3-state circuit breaker** per provider:

1. **CLOSED** — Normal operation. Requests flow through. Failures are counted.
2. **OPEN** — Provider is considered unhealthy. Requests fail immediately with 503 (or trigger failover) without calling the provider. After a configurable recovery timeout, the circuit transitions to HALF_OPEN.
3. **HALF_OPEN** — A single probe request is allowed. Success → CLOSED. Failure → OPEN.

Each provider (OpenAI, Anthropic) has its own circuit breaker instance. When one provider's circuit is OPEN, the router can fail over to another provider if configured.

## Consequences

- **Positive**: Prevents thundering herd to a failing provider; reduces latency for users (fast-fail instead of long timeouts); enables automatic recovery.
- **Negative**: Requires tuning of failure threshold and recovery timeout; OPEN state may delay recovery if timeout is too long.
- **Neutral**: Circuit state is in-memory per process; in multi-instance deployments, each instance maintains its own state (eventual consistency).
