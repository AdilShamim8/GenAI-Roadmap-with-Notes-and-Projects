# Latency SLOs

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [OpenAI latency guide](https://developers.openai.com/api/docs/guides/latency-optimization), [Claude prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)

## Why this matters

LLM latency is variable, multi-second, and dominated by tokens. Without explicit SLOs, you'll ship an experience that feels broken. With them, you can decide rationally when to cache, when to stream, and when to route to a smaller model. The expert framing: LLM latency isn't a distribution you tune — it's a *sum of physics* (prefill compute, decode bandwidth, network) plus a *queueing system you don't control* (the provider's). Your levers are structural: fewer tokens, earlier first token, shorter dependency chains. SLOs tell you which lever the experience needs.

## Core concepts

### The four latency metrics

| Metric | What | Target (2026) |
|--------|------|---------------|
| **TTFT** (time to first token) | Pre-fill + first token | <500ms p95 |
| **TPS** (tokens per second) | Decode speed | >50 TPS |
| **End-to-end p50** | Median total | <2s |
| **End-to-end p95** | Tail | <5s |

### The physics behind the metrics (why each lever works)

- **TTFT ≈ prefill time** — compute over input tokens, mostly parallelized; it scales with *uncached* input length. This is why prompt caching cuts TTFT 30-60% (`01-llm-calling/06-prompt-caching.md`): the cached prefix's prefill is skipped entirely.
- **Decode time ≈ output tokens / TPS** — autoregressive, *serial*; every token waits for the previous one. You cannot buy parallel decode from an API. A 600-token answer at 60 TPS is 10 seconds no matter what — the only levers are fewer output tokens or a faster-decoding model tier.
- **Agent latency compounds serially** — N tool-loop iterations = N × (TTFT + thinking + decode). This is why agent UX feels slow even when each call is "fine": the loop multiplies.

The design consequences fall straight out: for perceived speed, stream (TTFT is what users *feel* — perceived latency ≈ TTFT once tokens flow); for actual speed, cut output length or iteration count; for tail control, cap both with timeouts.

### The cost of tail latency

p99 is often 5–10× p50 for LLM calls. A single slow call can block a request. Always set timeouts.

Why LLM tails are *worse* than typical services: provider-side queueing under load (your p99 includes their congestion), thinking-model variance (reasoning length is stochastic — a "medium effort" call can think for 2s or 40s), and retry amplification (your retry policy stacks backoff delays onto an already-slow path). Timeout design is therefore SLO-critical: the timeout per attempt must be shorter than the user-facing SLO, or the SLO is fiction.

### Latency budget breakdown

A typical agent call:

```text
User input          0ms
Auth + validation   20ms
Retrieval (RAG)     200ms
LLM call (TTFT)     500ms
LLM decode (200 tok, 60 TPS) 3300ms
Response delivery   50ms
Total               ~4s
```

If TTFT > 1s, users perceive lag. Stream.

The budget view is the expert's tool: an SLO of "4s p95" is a *budget of 4000ms* allocated across components — retrieval 200, TTFT 500, decode 3000, overhead 300. Every component owner spends against the same budget; when decode wants 4000ms, *something else must shrink* (cap output, cache the prefix) — or the SLO moves. Budgets make latency negotiations explicit instead of discovered in production.

### Streaming changes the contract, not the physics

Streaming doesn't make the response faster — total time is the same. It moves *perceived* latency to TTFT and changes the UX failure mode: a mid-stream stall (TTFT 300ms, then 5s of silence) is *worse* than a clean 2s wait because it looks broken. So streaming introduces its own SLOs: inter-token latency (ITL) p95 — gaps between tokens should be <100ms — and you need heartbeat/abort handling for stalls (`01-llm-calling/05-streaming.md`).

### Setting SLOs that are actually yours

Most of an LLM call's latency is the provider's; your SLO must account for *their* variance. The practical pattern: express your SLO as provider-baseline + your-overhead, measure the provider's p95 per model as a *monitored dependency* (a "vendor latency budget"), and alert when their p95 drifts — because when the provider slows, your SLO is unachievable at any architecture, and the right response is fallback/rerouting (`05-agents/05-guardrails-retries-fallbacks.md`), not paging your on-call to "fix" latency they can't affect.

## Code: latency instrumentation

```python
import time
from contextlib import contextmanager

@contextmanager
def latency_histogram(metric_name: str, tags: list[str] = None):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        metrics.histogram(metric_name, elapsed_ms, tags=tags or [])

# Usage — measure TTFT and ITL separately; they have different causes and fixes
with latency_histogram("llm.ttft_ms", ["model:gpt-6.1-sol"]):
    first = next(stream)  # first chunk
```

## Code: streaming for TTFT

```python
# Bad: blocks until full response
resp = client.chat.completions.create(model="gpt-6.1-sol", messages=[...])
return resp.choices[0].message.content

# Good: stream first token within 500ms
def stream_response(messages):
    stream = client.chat.completions.create(model="gpt-6.1-sol", messages=messages, stream=True)
    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
# FastAPI returns StreamingResponse(stream_response(...))
```

## Production concerns

- **Latency:** Measure it. Don't guess. Separate TTFT/decode/queueing in your metrics — a single "request latency" histogram can't distinguish a prefill problem from a decode problem from a provider congestion event.
- **Cost:** Caching reduces TTFT dramatically and input cost simultaneously — the rare lever that improves both latency and cost at once.
- **Failure modes:** (1) provider rate limits spike TTFT — fallbacks; (2) thinking models' variable reasoning time — cap budgets per route (`02-context-engineering/05-extended-thinking-models.md`); (3) streaming stalls mid-response — ITL monitoring + abort UX; (4) retry stacking blowing the SLO — retry budget ⊂ latency budget.
- **Security:** Latency telemetry shouldn't include content.

## Anti-patterns

- ❌ **Reporting only p50.** Tail is what users feel.
- ❌ **No timeouts on LLM calls.** One slow call blocks the request.
- ❌ **Blocking on full response when streaming is available.**
- ❌ **One latency histogram for everything.** TTFT/ITL/decode have different causes and different fixes.
- ❌ **SLOs that assume provider latency is constant.** Budget for the vendor's p95 as a monitored dependency.
- ❌ **Fixing decode time with tuning.** Serial autoregression only shrinks with fewer output tokens or a faster tier.

## References

- [OpenAI: Latency optimization](https://developers.openai.com/api/docs/guides/latency) — verified 2026-10-20
- [Anthropic: Prompt caching for latency](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) — verified 2026-10-20
