# Prompt Caching

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)

## Why this matters

Prompt caching is the single highest-leverage cost optimization in 2026. Cache a 10K-token system prompt that you reuse 10,000 times/day → save 80%+ on input tokens for those calls. OpenAI caching is automatic (with optional explicit controls); Anthropic caching is explicit via `cache_control` markers.

## Core concepts

### What a prompt cache actually is

It's the provider's KV-cache for your prefix, kept warm between requests (the same machinery as PagedAttention/prefix caching in `00-foundations/02-kv-cache-and-inference.md`, exposed and priced). A hit skips re-running prefill on those tokens — which is why it cuts both price (~10x) and TTFT (30-60%): you're not just paying less, the provider isn't recomputing.

### The one rule: match is prefix-exact at the token level

Caches match the token sequence from position 0 — not semantics, not fuzzy similarity. One changed token at the front invalidates everything after it; a 5,000-token identical suffix doesn't help. That single rule generates all the discipline: static content first, dynamic last; no timestamps/request-IDs/date-headers in the prefix; identical tool-definition serialization (key order included — a re-serialized dict is a new prefix); stable tokenization (a whitespace difference is a token difference).

### Two flavors

| Provider | Behavior | Cache hit discount |
|----------|----------|-------------------|
| OpenAI | Automatic for prompts over the model's cache threshold with a shared prefix; `prompt_cache_key` steers traffic into the same cache | Cached input ~10x cheaper on current models (e.g. GPT-6.1 Sol: $2 → $0.10; Astra: $10 → $1) |
| Anthropic | Explicit `cache_control` markers, up to 4 breakpoints | Cache reads 0.1x base price; writes cost 1.25x (5-min TTL) or 2x (1-hour TTL) |

### The economics

A 10K-token system prompt reused 10K times/day at $2/1M input tokens (Sonnet 5.5 / GPT-6.1 Sol class):
- No caching: $200/day in input.
- OpenAI auto-cache: ~$10/day at the $0.10 cached rate.
- Anthropic explicit cache: ~$20/day read + a one-time 2.5M-token write premium (~$5 at 1.25x).

## Code: Anthropic explicit caching

```python
import anthropic
client = anthropic.Anthropic()

SYSTEM = [
    {"type": "text", "text": "<your 10K-token system prompt>"},
    {"type": "text", "text": "Cached on 2026-10-20.",
     "cache_control": {"type": "ephemeral", "ttl": "1h"}},
]

resp = client.messages.create(
    model="claude-sonnet-5-5", max_tokens=1024,
    system=SYSTEM, messages=[{"role": "user", "content": "hi"}],
)
# Measure the hit rate — don't assume it:
read = resp.usage.cache_read_input_tokens
write = resp.usage.cache_creation_input_tokens
print(f"cache read={read} write={write} of {resp.usage.input_tokens} input")
```

## Code: OpenAI caching (automatic + explicit key)

```python
from openai import OpenAI
client = OpenAI()

resp = client.chat.completions.create(
    model="gpt-6.1-sol",
    messages=MESSAGES,               # keep the static prefix first
    prompt_cache_key="billing-agent-v3",  # steer to a stable cache slice
)
cached = resp.usage.prompt_tokens_details.cached_tokens
print(f"cached {cached} of {resp.usage.prompt_tokens} input tokens")
```

## Production concerns

- **Latency:** Cache hits cut TTFT by 30-60%.
- **Cost:** Track `cached_tokens` (OpenAI) and `cache_read_input_tokens` (Anthropic) separately in your cost dashboard.
- **Failure modes:** Default TTLs are ~5 minutes (Anthropic default; 1h optional; OpenAI is minutes-scale). Low-traffic prompts may never hit — use the 1-hour TTL or explicit cache keys for slow traffic. Anthropic's write premium means a *churning* prompt costs MORE than no caching (1.25-2x writes, no reads) — if you can't keep a prefix stable, don't mark it cacheable.
- **Multi-turn placement:** the conversation itself is the growing stable prefix — on Anthropic, put a breakpoint at the tool definitions and another at the latest assistant turn so each exchange extends a cached prefix rather than starting fresh. On OpenAI, just keep message order append-only and never edit history in place.
- **Eviction is opaque.** Providers don't document exact eviction policy (capacity, LRU-ish, per-org). Treat hit rate as an observable to monitor and alert on, never a guarantee to depend on for correctness.
- **Security:** Don't cache prompts containing user-specific PII — cache hit = data leak across users. Partition `prompt_cache_key` by tenant where the same static prompt serves multiple customers.

## Anti-patterns

- ❌ **Putting dynamic data before static data in the prompt.** Cache won't hit because the prefix changed.
- ❌ **Caching prompts with per-user content mixed in.** Cross-user leak risk.
- ❌ **Assuming cache hits.** Measure the `cached_tokens / input_tokens` ratio and alert when it drops.
- ❌ **Exceeding 4 cache breakpoints (Anthropic).** Cache the biggest stable prefixes (system + tools + few-shot), not each message.

## Decision framework

| Situation | Use |
|-----------|-----|
| High-traffic shared system prompt | Anthropic `cache_control` (1h TTL) or OpenAI auto-cache |
| Many parallel users, isolated traffic | OpenAI `prompt_cache_key` per shard/tenant |
| Low-QPS overnight jobs | 1-hour TTL (Anthropic) — or accept misses and batch instead |
| Verifying savings | Log usage fields; ratio < 50% on a hot path = bug |

## References

- [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — verified 2026-10-20
- [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) — verified 2026-10-20
