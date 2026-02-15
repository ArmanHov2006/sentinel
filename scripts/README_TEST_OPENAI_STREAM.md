# How the OpenAI Streaming Test Works

## What This Test Does

The script `test_openai_stream.py` is a **manual integration test** for `OpenAIProvider.stream()`. It:

1. Builds a real `OpenAIProvider` (with circuit breaker and retry policy).
2. Builds a minimal `ChatRequest` (one user message, a model, and parameters).
3. Calls `provider.stream(request)` and consumes the async generator.
4. Prints each chunk as it arrives so you see text **incrementally** (word-by-word or token-by-token), not all at once.

If streaming is implemented correctly, you see the model’s reply appear gradually. If you see nothing until the end and then everything at once, the response is not being streamed.

---

## What We Do For the Test

### 1. Fix the Python path

- The script lives under `scripts/` but the package is under `src/`.
- So we do:  
  `sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))`  
  so that `import sentinel...` resolves to `src/sentinel`.

### 2. Create the provider

- We create a `CircuitBreaker()` and `RetryPolicy()` (same as in `main.py`).
- We instantiate `OpenAIProvider(circuit_breaker, retry_policy)`.
- The provider reads `OPENAI_API_KEY` from settings (environment or `.env`). If the key is missing, it raises `ValueError`.

### 3. Build a minimal ChatRequest

- **messages:** One `Message(role=Role.USER, content="...")`.
- **model:** e.g. `"gpt-4o-mini"`.
- **parameters:** `ModelParameters(temperature=0.7)` (and optionally `max_tokens`, etc.).

This is the same shape the API layer builds when someone calls `POST /v1/chat/completions`; we’re just building it by hand for a direct test.

### 4. Consume the stream

- We call:  
  `async for chunk in provider.stream(request):`
- Each `chunk` is a string (e.g. one token or a few characters).
- We print with `print(chunk, end="", flush=True)` so:
  - Chunks are printed back-to-back (no newline between them).
  - Output is flushed so you see each chunk as soon as it’s yielded (no buffering).

### 5. Run the script

- From the **project root**:  
  `PYTHONPATH=src python scripts/test_openai_stream.py`
- Or from the project root, after `set PYTHONPATH=src` (Windows) or `export PYTHONPATH=src` (Unix), run:  
  `python scripts/test_openai_stream.py`

---

## Success Criteria

- **Streaming works:** Text appears **gradually** (word-by-word or token-by-token), not in one block at the end.
- **No crash:** No `KeyError` on missing `content`, and `[DONE]` is handled without being parsed as JSON.
- **Clean output:** No extra blank chunks (role/finish deltas with no content are not yielded).

---

## Requirements

- **OPENAI_API_KEY** must be set (environment variable or in `.env` in the project root). Otherwise the provider raises `ValueError` on creation.
- Network access to the OpenAI API (or your proxy).

---

## Summary

| Step | What we do |
|------|------------|
| 1 | Add `src` to `sys.path` so `sentinel` imports work. |
| 2 | Create `OpenAIProvider` with circuit breaker and retry (needs `OPENAI_API_KEY`). |
| 3 | Build a `ChatRequest` (messages, model, parameters). |
| 4 | `async for chunk in provider.stream(request): print(chunk, end="", flush=True)`. |
| 5 | Run with `PYTHONPATH=src python scripts/test_openai_stream.py`. |

This is a **manual** test: you run it when you change streaming and confirm by eye that output is incremental. It is not part of the automated test suite (which would mock the API).
