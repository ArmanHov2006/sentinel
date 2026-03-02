# ADR 003: Semantic Caching with FAISS

## Status

Accepted

## Context

Exact-match response caching (e.g., SHA-256 of the request body) only hits when the user sends an identical request. Paraphrased or slightly reworded prompts (e.g., "What is the capital of France?" vs "Tell me the capital of France") miss the cache even though the expected response is the same.

We want to increase cache hit rates by treating semantically similar requests as cache hits, while avoiding false positives that return incorrect responses.

## Decision

We use **FAISS** (Facebook AI Similarity Search) with **sentence-transformers** for semantic cache lookups:

1. **Embedding** — Incoming prompts are embedded using a sentence-transformer model (e.g., `all-MiniLM-L6-v2`). Embeddings are stored in a FAISS index.
2. **Similarity** — Cosine similarity between the query embedding and indexed embeddings is computed. If the highest similarity exceeds a configurable threshold (e.g., 0.88), the cached response is returned.
3. **Storage** — FAISS holds the vector index; Redis holds the corresponding response payloads. Keys map embedding IDs to cached responses.

The similarity threshold is configurable: lower (e.g., 0.85) allows more paraphrases but risks incorrect hits; higher (e.g., 0.93) is stricter.

## Consequences

- **Positive**: Significant cache hit rate improvement for paraphrased queries; reduces latency and provider costs.
- **Negative**: Adds embedding model load (CPU/GPU) and FAISS index memory; threshold tuning required per use case.
- **Neutral**: Embedding model is loaded at startup; first request may be slower. Consider lazy loading if startup time is critical.
