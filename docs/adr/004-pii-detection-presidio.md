# ADR 004: PII Detection with Presidio

## Status

Accepted

## Context

User prompts may contain personally identifiable information (PII): emails, phone numbers, names, SSNs, credit card numbers, IP addresses. Sending such data to third-party LLM providers poses privacy and compliance risks (GDPR, HIPAA, etc.).

We need a solution to detect and handle PII before it leaves our gateway. Options include regex-based detection, custom NER models, or off-the-shelf libraries.

## Decision

We use **Microsoft Presidio** for PII detection and redaction:

1. **Extensibility** — Presidio supports multiple entity types (EMAIL, PHONE_NUMBER, PERSON, LOCATION, CREDIT_CARD, etc.) and allows adding custom recognizers. Regex-only solutions are brittle and hard to extend.
2. **Redaction** — Presidio provides analyzers (detect) and anonymizers (redact/replace). We use both: detect entities, then redact with configurable replacement (e.g., `[EMAIL]`, `[PHONE]`).
3. **Configurable actions** — We support `BLOCK` (reject request), `REDACT` (replace and forward), and `WARN` (log and forward) to accommodate different compliance requirements.
4. **Maturity** — Presidio is maintained by Microsoft and used in production by many organizations.

## Consequences

- **Positive**: Robust detection across entity types; easy to add new recognizers; configurable behavior per environment.
- **Negative**: Presidio adds dependency and some latency; may have false positives/negatives that require tuning.
- **Neutral**: Presidio can use spaCy models; we use the default or lightweight models to balance accuracy and performance.
