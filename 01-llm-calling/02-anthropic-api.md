# Anthropic API

> **Level:** BEG · **Last verified:** 2026-10-20 · **Sources:** [Claude Platform Docs](https://platform.claude.com/docs/en/overview)

## Why this matters

Anthropic's Claude is the second pillar of the frontier-model landscape. The API differs from OpenAI's in important ways (system prompt is top-level, prompt caching is explicit, tool calling has its own shape). Since late 2026 the current lineup is the Claude 5.5 family — Opus 5.5, Sonnet 5.5, and Haiku 5.5 — plus the research-flagship Fable line.

## Core concepts

- **Top-level system prompt** — not a message in the list; a parameter on the request.
- **Messages** — list of `{role, content}` where `content` can be a string or a list of content blocks (text, image, tool_use, tool_result, thinking, document). The block model is the real interface: tool calling works by the assistant emitting a `tool_use` block and you replying with a `tool_result` block *in the next user message* — the pairing is enforced, and unpaired blocks are a hard API error.
- **`stop_reason`** — read it on every response to drive your control loop: `end_turn` (natural stop), `max_tokens` (truncation — your bug), `stop_sequence` (custom halt), `tool_use` (you owe a tool_result). Agents that only check for text content silently mishandle the last two.
- **Prompt caching** — explicit. You mark cacheable blocks with `cache_control`. Cache reads are 0.1x base price; cache writes cost 1.25x (5-minute TTL) or 2x (1-hour TTL).
- **Extended thinking** — all Claude 5.5 models think by default and expose an `effort` setting (low → max); you get a `thinking` block in the response (billed as output). You can still set an explicit token budget.
- **Computer use** — Claude can drive a virtual computer (browser, terminal) via the computer-use tool.
- **Message Batches** — async batches completed within 24h at 50% off.

## Code: minimal chat

```python
import anthropic
client = anthropic.Anthropic()

resp = client.messages.create(
    model="claude-sonnet-5-5",  # balanced tier
    max_tokens=1024,
    system="You are a helpful assistant.",  # top-level, not a message
    messages=[
        {"role": "user", "content": "Summarize the KV-cache in one sentence."}
    ],
)
print(resp.content[0].text)
print(f"Tokens: in={resp.usage.input_tokens} out={resp.usage.output_tokens}")
# The two cache telemetry fields (pair with stop_reason in your logs):
print(f"cache_write={resp.usage.cache_creation_input_tokens}"
      f" cache_read={resp.usage.cache_read_input_tokens}")
```

`cache_read_input_tokens` is where the savings live — a healthy multi-turn workload shows it climbing toward the full static-prefix length per request. `cache_creation_input_tokens` spiking instead means your prefix is churning: something at the front of the prompt (timestamp, per-request ID) is breaking the common prefix, and every request is paying the 1.25-2x write fee again.

## Prompt caching

```python
resp = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=1024,
    system=[
        {"type": "text", "text": LARGE_SYSTEM_PROMPT,
         "cache_control": {"type": "ephemeral", "ttl": "1h"}},
    ],
    messages=[{"role": "user", "content": "..."}],
)
# Reads of the cached prefix bill at 0.1x base price (Sonnet 5.5: $0.20/1M).
```

The break-even math from the write/read prices: a 5-min cache (1.25x write, 0.1x reads) pays for itself after ~2 hits within the TTL; the 1h option (2x write) after ~3. So the TTL choice is a traffic-shape question — requests arriving within minutes take `5m` and pay the cheaper write, slow-drip traffic (humans returning within the hour) takes `1h`. Up to 4 cache breakpoints per request: typically system prompt, tool definitions, long few-shot header, and the conversation prefix — front-load the static parts so each breakpoint maximizes shared prefix length.

## Production concerns

- **Latency:** Opus 5.5 is the deep-work model; Sonnet 5.5 runs 30%+ faster and Haiku 5.5 is the fastest Claude yet. Route by task.
- **Cost:** Prompt caching is the single biggest lever — cache system prompts, few-shot examples, and tool definitions (up to 4 cache breakpoints). Stack with Batches for another 50% off.
- **Failure modes:** the error taxonomy worth automating on — `overloaded_error` (529, capacity; retry with backoff and a cap), 429 rate limits (honor the headers; the Python SDK retries automatically), `invalid_request_error` (your bug; don't retry). During peak windows, fail over to Sonnet 5.5 for Opus-bound traffic rather than hammering retries.
- **Security:** Anthropic's usage policies are stricter than OpenAI's; some content gets blocked that other APIs allow. `system`-level injection defenses (`02-context-engineering/04-prompt-injection-defense.md`) compose cleanly with the top-level system prompt — use that.

## Anti-patterns

- ❌ **Stuffing the system prompt into a `system` message.** Anthropic wants it as the top-level `system` param.
- ❌ **Not using `cache_control` for static prompts.** You're paying 10x more than you need to.
- ❌ **Comparing model names by string prefix.** `claude-sonnet-4-5` is not the same as `claude-sonnet-5-5`.
- ❌ **Assuming Haiku is cheap at every size.** Haiku 5.5 is $0.10/$0.50 only up to 100K tokens; past that it jumps to $0.50/$2.50 — for long-context work, price the tiers against each other.

## Decision framework

| Situation | Use |
|-----------|-----|
| High-volume, latency-sensitive steps | Haiku 5.5 (≤100K contexts) |
| Default agentic/coding workhorse | Sonnet 5.5 ($2/$10) |
| Complex, long-horizon work where quality dominates | Opus 5.5 ($4/$20) |
| Static prompts reused across requests | `cache_control` (+1h TTL for slow traffic) |
| Offline eval/backfill runs | Message Batches (50% off) |
| Cost control on thinking | Lower `effort` rather than switching models |

## References

- [Claude API reference](https://platform.claude.com/docs/en/api/messages) — verified 2026-10-20
- [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — verified 2026-10-20
- [Models overview](https://platform.claude.com/docs/en/models/overview) — verified 2026-10-20
