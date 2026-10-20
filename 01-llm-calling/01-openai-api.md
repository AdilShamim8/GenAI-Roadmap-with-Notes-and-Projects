# OpenAI API

> **Level:** BEG · **Last verified:** 2026-10-20 · **Sources:** [OpenAI API Docs](https://developers.openai.com/api/docs/)

## Why this matters

OpenAI's API is the default starting point for GenAI work. Even if you end up on Anthropic or self-hosted, the OpenAI client shape (messages, roles, tool calls) is the de facto industry interface. Two things changed since the GPT-4 era that you must internalize: the **Responses API** is now the primary interface, and the **GPT-6 family** (Astra / Sol / Luna tiers) replaced both GPT-4/5 flagships and the separate o-series reasoning models.

## Core concepts

- **Messages** — list of `{role, content}` dicts. Roles: `system`/`developer`, `user`, `assistant`, `tool`.
- **Responses API** — the primary endpoint: stateful conversations (`previous_response_id`), tools, computer use, structured outputs, and reasoning controls in one place. Chat Completions still works and remains the cross-provider compatibility layer.
- **Reasoning effort** — GPT-6/5.x thinking models expose `reasoning.effort` (low → max); thinking tokens are billed as output. Reasoning is no longer a separate o-series — it is a dial on the same model line.
- **Prompt caching** — automatic for prompts above the model's cache threshold with a shared prefix; cached input is ~10x cheaper (verified Astra rates: $10 input vs $1 cached per 1M). Order prompts static-first, dynamic-last (see `06-prompt-caching.md`).
- **Context window** — a *per-tier* property, not a family property: Astra is verified at 1.05M tokens, and the cheaper tiers are smaller — check the current per-model window in the docs before routing long-context work to a mid or cheap tier.
- **Built-in tools** — the Responses API also hosts server-side tools (`web_search`, `file_search`, `code_interpreter`) that run on OpenAI infrastructure and bill separately from token pricing. They remove code you'd otherwise write, at the price of less control and per-call billing — the classic build-vs-rent trade-off.
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

The `previous_response_id` continuation is convenience, not a discount: prior turns still count as input tokens on the next call (only the provider's prefix cache makes them cheap). For multi-turn in production, weigh server-side state (simpler, locks you in, one more failure surface) against re-sending the transcript (portable across providers, cache-friendly if you keep the prefix stable).

## Reading `usage` like an expert

```python
u = resp.usage
# Responses API: prompt/completion/total + the two fields that actually matter:
print(u.input_tokens, u.output_tokens, u.total_tokens)
# u.input_tokens_details.cached_tokens  -> tokens billed at the ~10x-cheaper cached rate
# u.output_tokens_details.reasoning_tokens -> thinking you paid for but never displayed
```

Wire `cached_tokens` and `reasoning_tokens` into your metrics pipeline on day one: they are the two levers that move OpenAI bills the most, and neither appears in `total_tokens` breakdowns unless you ask for them. A drop in cache-hit rate or a silent rise in reasoning share is often the first visible symptom of a prompt-structure regression or a model-alias swap.

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
- **Failure modes:** Rate limits (TPM/RPM, and separate input/output-token meters), 429s, occasional 5xx. The Python client retries connection errors and 429/5xx automatically (`max_retries`, default 2) with exponential backoff — know that before you wrap calls in your own retry loop and double-retry. Honor `Retry-After` when present; add jitter to your own backoff; set explicit `timeout=` per call-path (the client default is 10 min, which is wrong for interactive paths).
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
