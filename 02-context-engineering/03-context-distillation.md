# Context Distillation

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [Letta memory patterns](https://github.com/letta-ai/letta), [Claude: manage context](https://platform.claude.com/docs/en/build-with-claude/context-management)

## Why this matters

Long agent runs accumulate dead context: tool outputs you no longer need, intermediate reasoning, resolved sub-tasks. Without active distillation, your agent drifts, gets slower, and costs more with every turn.

## Core concepts

### Three distillation patterns

1. **Rolling summary** — every N turns, replace the oldest turns with a summary.
2. **Tool-output compaction** — after a tool call completes, replace the raw output with a 1-paragraph summary in the next turn.
3. **Hierarchical memory** — keep a short working context (last 5 turns) + a longer episodic memory (summarized) + retrieval into raw history.

### The async summarizer

Run summarization as a background task, not in the user-facing turn. Insert the summary into the next turn's context.

### Platform-native compaction (2025-26)

The big providers shipped first-class versions of these patterns — reach for them before hand-rolling:

- **Anthropic context management APIs** — context editing (clear old tool results), and a **memory tool** that persists key facts to client-side files, reloading them into later sessions. Claude Code's compaction is the flagship example.
- **LangChain 1.0 Summarization middleware** — built into `create_agent`; condenses history as it approaches the context limit.
- **Agent SDK / framework checkpointers** — durable state you can rewind instead of carrying forward.

## Code: rolling summary

```python
from openai import OpenAI
client = OpenAI()

def maybe_summarize(history: list[dict], threshold: int = 20) -> list[dict]:
    if len(history) < threshold * 2:
        return history
    system = history[0]
    old = history[1:threshold]
    recent = history[threshold:]

    summary = client.chat.completions.create(
        model="gpt-6-luna",  # cheap tier — summaries don't need a flagship
        messages=[
            {"role": "system", "content": "Summarize the conversation so far in <300 words. Preserve decisions, key facts, and unresolved questions."},
            *old,
        ],
    ).choices[0].message.content

    return [system, {"role": "user", "content": f"[Previous conversation summary]\n{summary}"}, *recent]
```

## Production concerns

- **Latency:** Summarization adds a background call; doesn't affect user TTFT if async.
- **Cost:** Summary calls are cheap (small model) and pay for themselves in token savings.
- **Failure modes:** Summaries lose detail that matters for a later turn. Always preserve "decisions made" and "open questions".
- **Security:** Don't summarize PII into a long-lived memory store without redaction.

## Anti-patterns

- ❌ **Summarizing the entire context every turn.** Expensive and noisy.
- ❌ **Truncating history by turn count, not content.** Loses long-range dependencies.
- ❌ **Storing raw transcripts forever.** Use episodic memory with TTLs.

## Decision framework

| Situation | Use |
|-----------|-----|
| Long-running coding/file agent | Provider-native compaction (Anthropic memory tool / Claude-style) |
| Conversation drift on turn count | Rolling summary (this file's pattern) |
| Huge tool outputs (API dumps) | Tool-output compaction right after the call |
| Cross-session personalization | Hierarchical memory + a memory layer (see `../05-agents/06-agent-memory-patterns.md`) |

## References

- [Letta (formerly MemGPT) — memory patterns](https://github.com/letta-ai/letta) — verified 2026-10-20
- [Claude: context management](https://platform.claude.com/docs/en/build-with-claude/context-management) — verified 2026-10-20
