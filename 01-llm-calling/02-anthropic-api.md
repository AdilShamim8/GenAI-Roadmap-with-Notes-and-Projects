# Anthropic API

> **Level:** BEG · **Last verified:** 2026-10-20 · **Sources:** [Claude Platform Docs](https://platform.claude.com/docs/en/overview)

## Why this matters

Anthropic's Claude is the second pillar of the frontier-model landscape. The API differs from OpenAI's in important ways (system prompt is top-level, prompt caching is explicit, tool calling has its own shape). Since late 2026 the current lineup is the Claude 5.5 family — Opus 5.5, Sonnet 5.5, and Haiku 5.5 — plus the research-flagship Fable line.

## Core concepts

- **Top-level system prompt** — not a message in the list; a parameter on the request.
- **Messages** — list of `{role, content}` where `content` can be a string or a list of content blocks (text, image, tool_use, tool_result, thinking).
- **Prompt caching** — explicit. You mark cacheable blocks with `cache_control`. Cache reads are 0.1x base price; cache writes cost 1.25x (5-minute TTL) or 2x (1-hour TTL).
- **Extended thinking** — all Claude 5.5 models think by default and expose an `effort` setting (low → max); you get a `thinking` block in the response. You can still set an explicit token budget.
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
```

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

## Production concerns

- **Latency:** Opus 5.5 is the deep-work model; Sonnet 5.5 runs 30%+ faster and Haiku 5.5 is the fastest Claude yet. Route by task.
- **Cost:** Prompt caching is the single biggest lever — cache system prompts, few-shot examples, and tool definitions (up to 4 cache breakpoints). Stack with Batches for another 50% off.
- **Failure modes:** `overloaded_error` during peak; retry with backoff.
- **Security:** Anthropic's usage policies are stricter than OpenAI's; some content gets blocked that other APIs allow.

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
