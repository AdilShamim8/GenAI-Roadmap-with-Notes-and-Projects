# Guardrails, Retries, Fallbacks

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [tenacity](https://github.com/jd/tenacity), [OpenAI error codes](https://developers.openai.com/api/docs/error-codes)

## Why this matters

Production agents fail. APIs rate-limit, models hallucinate, tools throw. The difference between a demo and a production agent is how it handles failure. Three patterns matter: guardrails (prevent), retries (recover), fallbacks (degrade).

## Core concepts

### Guardrails

Run before and after the LLM call:
- **Input guardrails** — validate input, redact PII, detect injection.
- **Output guardrails** — validate output, filter toxic content, enforce schema.

### Retries

- **Idempotent retries** — same call, retry on transient failure.
- **Backoff** — exponential, with jitter.
- **Cap** — 3 retries max; then fail.

### Fallbacks

- **Model fallback** — GPT-5 → Claude Sonnet → Gemini Flash.
- **Tool fallback** — primary API fails, use cached data.
- **UX fallback** — "I'm having trouble, here's what I found so far."

## Code: retry with backoff

```python
import asyncio, random
from functools import wraps

def retry(max_attempts=3, base_delay=1.0, exceptions=(Exception,)):
    def deco(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await fn(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        raise
                    delay = base_delay * (2 ** attempt) + random.random()
                    await asyncio.sleep(delay)
        return wrapper
    return deco

@retry(max_attempts=3, exceptions=(TimeoutError, RateLimitError))
async def call_llm(prompt: str) -> str:
    return await client.chat.completions.create(...)
```

## Code: model fallback chain

```python
MODELS = ["gpt-6.1-sol", "claude-sonnet-5-5", "gemini-3.8-flash"]

async def call_with_fallback(prompt: str) -> str:
    for model in MODELS:
        try:
            return await call_model(model, prompt)
        except (RateLimitError, OverloadedError) as e:
            continue
    raise RuntimeError("All models failed")
```

## Code: output guardrail

```python
from pydantic import BaseModel, ValidationError

class Output(BaseModel):
    answer: str
    confidence: float  # 0..1

def safe_call(prompt: str) -> Output:
    for _ in range(3):
        raw = llm_call(prompt)
        try:
            out = Output.model_validate_json(raw)
            if 0 <= out.confidence <= 1:
                return out
        except ValidationError:
            continue
    raise RuntimeError("Output failed validation after 3 retries")
```

## Production concerns

- **Latency:** Retries add latency; budget for worst case.
- **Cost:** Retried calls still cost money.
- **Failure modes:** Retrying non-idempotent operations causes duplicates.
- **Security:** Don't retry in a way that exposes PII in logs.

## Anti-patterns

- ❌ **Retrying all 4xx errors alike.** 429 (rate limit) and 408 (timeout) are retryable — honor `Retry-After`; 400/401/403/404 are not, and retrying just adds noise.
- ❌ **Infinite retry loops.** Always cap attempts and total time.
- ❌ **Hand-rolling retries when the SDK has them.** `OpenAI(max_retries=...)` and `Anthropic(max_retries=...)` handle backoff correctly for connection errors and 429/5xx.
- ❌ **No timeout per attempt.** A hung call without a timeout blocks the whole chain.
- ❌ **No fallback when one model is enough.** Don't over-engineer.

## Decision framework

| Failure | Response |
|---------|----------|
| 429 rate limit | Retry with backoff, honor `Retry-After`; then fail over |
| 5xx / overloaded | Retry with backoff; then next model in chain |
| 400/401/403/404 | Do not retry — fix the request |
| Timeout | Retry once with same model, then fail over |
| Validation failure | Re-ask with the schema (max 2x), then degrade |

## References

- [Tenacity (retry library)](https://github.com/jd/tenacity) — verified 2026-10-20
- [OpenAI: Error handling](https://platform.openai.com/docs/guides/error-codes) — verified 2026-10-20
