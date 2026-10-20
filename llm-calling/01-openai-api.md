# OpenAI API

> **Level:** BEG · **Last verified:** 2026-10-20 · **Sources:** [OpenAI API Docs](https://developers.openai.com/api/docs/)

## Why this matters

OpenAI's API is the default starting point for GenAI work. Even if you end up on Anthropic or self-hosted, the OpenAI client shape (messages, roles, tool calls) is the de facto industry interface. Two things changed since the GPT-4 era that you must internalize: the **Responses API** is now the primary interface, and the **GPT-6 family** (Astra / Sol / Luna tiers) replaced both GPT-4/5 flagships and the separate o-series reasoning models.

## Core concepts

- **Messages** — list of `{role, content}` dicts. Roles: `system`/`developer`, `user`, `assistant`, `tool`.
- **Responses API** — the primary endpoint: stateful conversations (`previous_response_id`), tools, computer use, structured outputs, and reasoning controls in one place. Chat Completions still works and remains the cross-provider compatibility layer.
- **Reasoning effort** — GPT-6/5.x thinking models expose `reasoning.effort` (low → max); thinking tokens are billed as output. Reasoning is no longer a separate o-series — it is a dial on the same model line.
- **Prompt caching** — automatic for prompts above the model's cache threshold with a shared prefix; cached input is ~10x cheaper (e.g. GPT-6.1 Sol: $2 input vs $0.10 cached).
- **Batch API** — same models, async within 24h, 50% off both input and output.

## Code: minimal chat (Chat Completions, works everywhere)

```python
from openai import OpenAI
client = OpenAI()

resp = client.chat.completions.create(
    model="gpt-6.1-sol",  # Sol = balanced tier; luna = cheap; astra = flagship
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Summarize the KV-cache in one sentence."},
    ],
)
print(resp.choices[0].message.content)
print(f"Tokens: in={resp.usage.prompt_tokens} out={resp.usage.completion_tokens}")
```

## Code: the Responses API (preferred for new builds)

```python
resp = client.responses.create(
    model="gpt-6.1-sol",
    instructions="You are a helpful assistant.",
    input="Summarize the KV-cache in one sentence.",
    reasoning={"effort": "low"},   # spend fewer thinking tokens
    max_output_tokens=512,
)
print(resp.output_text)
# continue the conversation server-side:
# follow = client.responses.create(model=..., previous_response_id=resp.id, input="...")
```

## Streaming

```python
stream = client.responses.create(
    model="gpt-6.1-sol",
    input="Write a haiku about KV-cache.",
    stream=True,
)
for event in stream:
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
```

## Production concerns

- **Latency:** TTFT is ~300ms–2s depending on prompt size and reasoning effort. Plan your UX around streaming; drop `reasoning.effort` to `low` or `none` for latency-sensitive paths.
- **Cost:** The GPT-6 family spans $0.10/$0.50 (Luna) to $10/$50 (Astra) per 1M tokens — a 100x spread. Route by task complexity and use Batch for anything that tolerates 24h.
- **Failure modes:** Rate limits (TPM/RPM), 429s, occasional 5xx. Always retry with exponential backoff and honor `Retry-After`.
- **Security:** Don't put PII in prompts unless your DPA allows it. Use the zero-retention enterprise tier for sensitive data.

## Anti-patterns

- ❌ **Calling the API synchronously in a request handler** — use streaming or `AsyncOpenAI`.
- ❌ **Hardcoding a model with no snapshot awareness** — rolling aliases (`gpt-6.1-sol`) update silently; pin dated snapshots for reproducibility, accept aliases for cost.
- ❌ **Ignoring `usage` in the response** — that's your cost telemetry.
- ❌ **Defaulting to the flagship tier** — most pipeline steps (classification, extraction, routing) belong on Luna-class models.

## Decision framework

| Situation | Use |
|-----------|-----|
| Cross-provider compatibility, simplest portability | Chat Completions |
| New OpenAI-native build: tools, state, reasoning controls | Responses API |
| Latency-sensitive UX | Streaming + `reasoning.effort: low/none` |
| Offline workloads (evals, backfills, enrichment) | Batch API (50% off) |
| High-volume simple steps (classification, extraction) | `gpt-6-luna` ($0.10/$0.50) |
| Hard reasoning, agentic tool use | `gpt-6.1-sol` or `gpt-6-astra` by budget |

## References

- [OpenAI API docs](https://developers.openai.com/api/docs/) — verified 2026-10-20
- [OpenAI Cookbook](https://developers.openai.com/cookbook/) — verified 2026-10-20
- [OpenAI pricing](https://developers.openai.com/api/docs/pricing) — verified 2026-10-20
