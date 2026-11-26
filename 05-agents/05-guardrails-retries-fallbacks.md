# Guardrails, Retries, Fallbacks

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [tenacity](https://github.com/jd/tenacity), [OpenAI error codes](https://developers.openai.com/api/docs/error-codes)

## Why this matters

Production agents fail. APIs rate-limit, models hallucinate, tools throw. The difference between a demo and a production agent is how it handles failure. Three patterns matter: guardrails (prevent), retries (recover), fallbacks (degrade). The expert framing: these three form a *failure budget* system. Every layer has a cost (latency, money, complexity), and the engineering task is spending that budget where failure probability × consequence is highest — not blanket-hardening everything.

## Core concepts

### Guardrails — and the taxonomy confusion to avoid

Run before and after the LLM call:

- **Input guardrails** — validate input, redact PII, detect injection.
- **Output guardrails** — validate output, filter toxic content, enforce schema.

A useful expert distinction: **deterministic guardrails** (schema validation, regex, PII detectors, allowlists — cheap, exact, testable) vs **model-based guardrails** (a classifier or second LLM checking the first — probabilistic, costly, itself fallible). Rule of thumb: deterministic first, model-based only for judgments rules can't make (is this *response* harmful?). A model-based guardrail adds its own failure modes — it can false-positive your good traffic and itself get prompt-injected, so it belongs *after* the deterministic layers, scoped to high-risk routes.

Guardrail placement matters as much as guardrail content: an output guardrail that runs *after* the tool executed is an audit, not a guard. If the expensive/dangerous step is a tool call, the guard goes *between* model and tool (the approval point — `05-agents/02-anthropic-claude-agent-sdk.md`'s `can_use_tool` is exactly this).

### Retries — the three-axis design space

Retrying is not one decision; it's three:

1. **What to retry** — idempotent operations only. An LLM call is idempotent (same input, new sample — fine to retry). A payment tool is not; retrying it needs an idempotency *key* at the payment API, or you charge twice. Classify every tool on this axis at build time.
2. **When to retry** — retryable vs non-retryable errors. 429 (rate limit) and 5xx/overloaded: retryable, with backoff; honor `Retry-After` when present. 400/401/403/404: never — the request is wrong, and re-sending the same wrongness adds load and noise. Timeouts: once, same target, then fail over (a timeout may mean the request *landed* — for non-idempotent calls, a timeout needs reconciliation, not a blind retry).
3. **How long** — cap both attempts and *total wall-clock*. Three retries with exponential backoff at 1s/2s/4s base = up to 7s of added latency; if your SLO is 3s p95, the retry budget *is* the SLO (`../08-production/02-latency-slos.md`). Timeout per attempt is the silent prerequisite: without it, one hung call blocks the chain and the retry policy never fires.

Backoff needs **jitter** (randomized delay) — synchronized retries from many clients create thundering-herd waves that keep the rate limit tripped. The SDK defaults handle this: `OpenAI(max_retries=...)`, `Anthropic(max_retries=...)` implement correct exponential backoff with jitter for connection errors and 429/5xx. Configure them; don't hand-roll a worse version alongside.

### Fallbacks — degradation as a designed product state

- **Model fallback** — GPT-6.1 → Claude Sonnet → Gemini Flash.
- **Tool fallback** — primary API fails, use cached data.
- **UX fallback** — "I'm having trouble, here's what I found so far."

The expert principle: **a fallback is a designed user experience, not an error handler.** "All models failed → 500" is a cop-out; "I can't complete the analysis right now, but here's the cached result from last run (stamped as such)" is a product decision that requires knowing, per feature, what *partial* looks like. Fallback design forces the question: what does this feature promise? If the promise is "frontier-model quality," falling back to a small model may be worse than degrading gracefully ("the fast path is down; the full answer will be emailed"). Match fallback quality-tier to the feature's promise, and *mark* degraded responses — silent quality drops train users to distrust everything.

Fallback chains also have ordering economics: order by (availability, cost, capability-fit) — usually cheap-and-different-provider first, since correlated outages (same provider's whole API) are the scenario you're defending against. A chain within one provider's models defends against model-specific rate limits, not provider outages; a cross-provider chain defends both but changes output style mid-session (brand voice drift — a real cost).

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
                    # full jitter: never worse than the base schedule, no herds
                    delay = random.uniform(0, base_delay * (2 ** attempt))
                    await asyncio.sleep(delay)
        return wrapper
    return deco

@retry(max_attempts=3, exceptions=(TimeoutError, RateLimitError))
async def call_llm(prompt: str) -> str:
    return await client.chat.completions.create(...)
```

## Code: model fallback chain (with degradation marking)

```python
MODELS = [
    ("gpt-6.1-sol", "primary"),
    ("claude-sonnet-5-5", "fallback"),   # cross-provider: survives provider outages
    ("gemini-3.8-flash", "degraded"),    # different tier: mark the response
]

async def call_with_fallback(prompt: str) -> tuple[str, str]:
    for model, tier in MODELS:
        try:
            return await call_model(model, prompt), tier
        except (RateLimitError, OverloadedError):
            continue
    raise RuntimeError("All models failed")
# Surface `tier` — the UX shows "slower model in use" for degraded, not silence.
```

## Code: output guardrail (deterministic-first)

```python
from pydantic import BaseModel, Field, ValidationError

class Output(BaseModel):
    answer: str
    confidence: float = Field(ge=0, le=1)  # deterministic range check, not a runtime if

def safe_call(prompt: str) -> Output:
    for _ in range(2):  # one self-correction, not three — see retry economics
        raw = llm_call(prompt)
        try:
            return Output.model_validate_json(raw)
        except ValidationError as e:
            last_error = e
    raise RuntimeError(f"Output failed validation: {last_error}")
```

## Production concerns

- **Latency:** Retries add latency; budget for worst case (sum of backoff schedule) against your SLO. The fallback chain's worst case is the *sum of each tier's timeout* — set per-attempt timeouts accordingly (usually 5-15s, not the SDK's 10-minute default).
- **Cost:** Retried calls still cost money — especially non-streamed calls that time out *after* the server generated the response. Timeout economics: an over-long timeout wastes wall-clock; an over-short one wastes tokens by retrying work the server did.
- **Failure modes:** (1) retrying non-idempotent operations causes duplicates — idempotency keys on tool calls; (2) fallback loops (fallback target also fails, retries back to primary, ping-pong) — the chain is one pass, no loops; (3) guardrail false-positives at scale — measure block rates, alert on spikes (a spike means either an attack or your guardrail drifting into good traffic).
- **Security:** Don't log PII in retry/fallback paths — the retry layer duplicates payloads into logs by default. Guardrails see your most sensitive traffic (they exist to check it); their logs are a data store with its own retention policy.
- **Testing:** Failure injection is the only honest test: kill the primary in staging, verify the fallback engages *and the UX marks it*; force 429s, verify backoff timing; corrupt an output, verify guardrail + self-correction path. Untested fallbacks fail exactly when needed — that's Murphy's law applied to resilience code.

## Anti-patterns

- ❌ **Retrying all 4xx errors alike.** 429 (rate limit) and 408 (timeout) are retryable — honor `Retry-After`; 400/401/403/404 are not, and retrying just adds noise.
- ❌ **Infinite retry loops.** Always cap attempts and total time.
- ❌ **Hand-rolling retries when the SDK has them.** `OpenAI(max_retries=...)` and `Anthropic(max_retries=...)` handle backoff correctly for connection errors and 429/5xx.
- ❌ **No timeout per attempt.** A hung call without a timeout blocks the whole chain.
- ❌ **No fallback when one model is enough.** Don't over-engineer.
- ❌ **Silent degradation.** If the fallback changed quality, the user must be told.
- ❌ **Model-based guardrails first.** Deterministic checks are cheaper, exact, and testable; use models only for judgment.

## Decision framework

| Failure | Response |
|---------|----------|
| 429 rate limit | Retry with backoff, honor `Retry-After`; then fail over |
| 5xx / overloaded | Retry with backoff; then next model in chain |
| 400/401/403/404 | Do not retry — fix the request |
| Timeout (idempotent call) | Retry once with same model, then fail over |
| Timeout (non-idempotent tool) | Reconcile state before any retry; use idempotency keys |
| Validation failure | Re-ask with the schema error (max 1x), then degrade |
| Provider outage | Cross-provider chain; mark degraded UX |

## References

- [Tenacity (retry library)](https://github.com/jd/tenacity) — verified 2026-10-20
- [OpenAI: Error handling](https://platform.openai.com/docs/guides/error-codes) — verified 2026-10-20
