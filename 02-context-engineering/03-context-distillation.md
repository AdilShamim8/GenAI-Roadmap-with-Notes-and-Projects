# Context Distillation

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [Letta memory patterns](https://github.com/letta-ai/letta), [Claude: manage context](https://platform.claude.com/docs/en/build-with-claude/context-management)

## Why this matters

Long agent runs accumulate dead context: tool outputs you no longer need, intermediate reasoning, resolved sub-tasks. Without active distillation your agent drifts, gets slower, and costs more with every turn. The subtle trap: compaction is lossy *by design* — the engineering problem is choosing *what* to lose, and making that choice auditable, not avoiding loss entirely.

## Core concepts

### The loss budget: what must survive a summary

A summary is a lossy compression of your conversation state. The failure isn't "we summarized"; it's summarizing away the wrong things. Rank context by downstream utility:

| Tier | Content | Compaction policy |
|------|---------|-------------------|
| 1 — Never lose | Decisions made, commitments to user, IDs/paths of artifacts, open questions | Preserve verbatim or structured-keyword |
| 2 — Summarize | Resolved sub-task narratives, tool-output details, dead-end explorations | LLM summary with tier-1 extraction |
| 3 — Drop | Raw tool outputs already summarized, failed branches, boilerplate greetings | Delete; keep pointer to raw log outside context |

The classic post-mortem pattern: an agent re-does work it already did, or contradicts an earlier commitment, because the summary dropped "we already tried X and it failed." Tier-1 extraction is the fix — always preserve decisions and open questions *verbatim*, in a structured block, not woven into prose.

### The summary-as-input problem

A summary is itself untrusted-ish input to future turns: whatever the summarizer model got wrong becomes ground truth for every later decision. Two mitigations: (1) use structured summaries (key-decisions list, not narrative prose) so omissions are visible as absence; (2) keep the raw transcript in durable storage (DB, not context) so recovery is a retrieval step, not a re-run.

### Three distillation patterns

1. **Rolling summary** — every N turns, replace the oldest turns with a summary.
2. **Tool-output compaction** — after a tool call completes, replace the raw output with a 1-paragraph summary in the next turn. Highest ROI: tool outputs are the biggest single context consumer in agent traces, and their useful lifetime is usually one or two turns.
3. **Hierarchical memory** — short working context (last ~5 turns) + episodic memory (summarized) + retrieval into raw history. This is the Letta/MemGPT lineage: the OS analogy is exact — main memory (context window) vs disk (memory store), with the model itself acting as the pager that decides what to swap in/out via memory tools.

### The async summarizer

Run summarization as a background task, not in the user-facing turn: trigger on a token threshold (e.g. active budget 80% from `01-context-budgeting.md`), summarize the oldest third, insert the summary at the next turn boundary. Synchronous summarization adds its own full LLM call latency to the visible path — a UX and TTFT regression for something the user doesn't need to wait for.

### Summarizers vs prompt caches — the hidden coupling

Compaction rewrites history, and prompt caches match a **prefix-exact token sequence** (`01-llm-calling/06-prompt-caching.md`). A mid-conversation summary that rewrites early turns invalidates the cache for everything after the rewrite point. Net effect: the compaction call *saves* input tokens but the next request *pays* fresh-input price on the entire rewritten prefix. At ~10x cached-vs-fresh pricing, aggressive compaction can be net-negative on cost for cache-hit-heavy workloads. Expert heuristics:

- Compact at most once per session phase, not every N=small turns.
- Append summaries as new context (keeping the old prefix intact and cached) when the old prefix would otherwise remain stable; rewrite only when the savings exceed the cache-invalidation cost.
- Measure: compare `cached_tokens/input_tokens` before/after enabling compaction. If hit rate collapses, your compaction is thrashing the cache.

### Platform-native compaction (2025-26)

The big providers shipped first-class versions of these patterns — reach for them before hand-rolling:

- **Anthropic context management APIs** — context editing (clear old tool results server-side) and a **memory tool** that persists key facts to client-side files, reloading them into later sessions. Claude Code's compaction is the flagship example.
- **LangChain 1.0 Summarization middleware** — built into `create_agent`; condenses history as it approaches the context limit.
- **Agent SDK / framework checkpointers** — durable state you can rewind instead of carrying forward.

Platform tools have a real advantage over hand-rolled ones: they can edit *inside* the provider's cached prefix representation or persist across sessions with tooling support, which a client-side rewriter can't.

## Code: rolling summary with tier-1 extraction

```python
from openai import OpenAI
client = OpenAI()

def maybe_summarize(history: list[dict], threshold: int = 20) -> list[dict]:
    if len(history) < threshold * 2:
        return history
    system = history[0]
    old = history[1:threshold]
    recent = history[threshold:]

    resp = client.chat.completions.create(
        model="gpt-6-luna",  # cheap tier — summaries don't need a flagship
        response_format={"type": "json_schema", "json_schema": {
            "name": "session_summary",
            "schema": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "decisions": {"type": "array", "items": {"type": "string"}},
                    "open_questions": {"type": "array", "items": {"type": "string"}},
                    "artifacts": {"type": "array", "items": {"type": "string"}},
                    "narrative": {"type": "string"},
                },
                "required": ["decisions", "open_questions", "artifacts", "narrative"],
            },
        }},
        messages=[
            {"role": "system", "content": (
                "Summarize the conversation for a future session of the same agent. "
                "Extract: every decision made (verbatim where possible), open questions, "
                "IDs/paths of artifacts created. Narrative under 200 words. "
                "Never invent details."
            )},
            *old,
        ],
    )
    import json
    s = json.loads(resp.choices[0].message.content)
    summary_block = (
        f"[Previous conversation — decisions]\n"
        + "\n".join(f"- {d}" for d in s["decisions"])
        + f"\n[Open questions]\n" + "\n".join(f"- {q}" for q in s["open_questions"])
        + f"\n[Artifacts]\n" + "\n".join(f"- {a}" for a in s["artifacts"])
        + f"\n[Narrative]\n{s['narrative']}"
    )

    return [system, {"role": "user", "content": summary_block}, *recent]
```

Design points: structured output (not prose) so a missing decision is visible as an empty list, cheap-tier model (the summarizer runs constantly), and the summary is *inserted as a user-role block* — never merged into the system prompt, which would break the cache prefix.

## Production concerns

- **Latency:** Summarization adds a background call; doesn't affect user TTFT if async. Watch queue depth if traffic bursts — summarizers are the first thing to backlog.
- **Cost:** The summarizer call is small-model + old context, but the *savings* depend on cache interaction (above). Model it, then measure.
- **Failure modes:** (1) Summaries lose tier-1 detail — mitigate with structured extraction; (2) summary drift — compounding re-summaries of summaries lose fidelity like re-encoded JPEGs; keep tier-1 items verbatim across re-summarizations; (3) the summarizer inherits prompt-injection risk from the content it reads — a malicious tool output can persist into the "decisions" list. Sanitize untrusted content before it enters a summary (`04-prompt-injection-defense.md`).
- **Security:** Don't summarize PII into a long-lived memory store without redaction. Summaries outlive sessions — apply retention policy to the memory layer, not just the transcript.
- **Evals:** Compaction is a behavior change — run your golden set with compaction enabled at aggressive thresholds; measure task success with vs. without (`../07-evals/01-golden-datasets.md`).

## Anti-patterns

- ❌ **Summarizing the entire context every turn.** Expensive, noisy, and cache-thrashing.
- ❌ **Truncating history by turn count, not content.** Loses long-range dependencies a summary would keep.
- ❌ **Prose-only summaries.** Missing decisions are invisible inside a narrative. Structure forces explicit extraction.
- ❌ **Compacting mid-prefix without measuring cache hit rate.** Fresh-input repricing can exceed the token savings.
- ❌ **Storing raw transcripts forever with no retention policy.** Use episodic memory with TTLs.

## Decision framework

| Situation | Use |
|-----------|-----|
| Long-running coding/file agent | Provider-native compaction (Anthropic memory tool / Claude-style) |
| Conversation drift on turn count | Rolling summary (this file's pattern) |
| Huge tool outputs (API dumps) | Tool-output compaction right after the call — biggest single win |
| Cross-session personalization | Hierarchical memory + a memory layer (see `../05-agents/06-agent-memory-patterns.md`) |
| Cache-hit-heavy hot path | Compact rarely; append instead of rewrite; measure hit rate before/after |

## References

- [Letta (formerly MemGPT) — memory patterns](https://github.com/letta-ai/letta) — verified 2026-10-20
- [Claude: context management](https://platform.claude.com/docs/en/build-with-claude/context-management) — verified 2026-10-20
