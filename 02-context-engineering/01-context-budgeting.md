# Context Window Budgeting

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [RULER](https://arxiv.org/abs/2404.06654), [NoLiMa](https://arxiv.org/abs/2502.05167), [Anthropic: Contextual retrieval](https://www.anthropic.com/news/contextual-retrieval)

## Why this matters

In 2026, the bottleneck isn't writing a good prompt — it's managing what's *in* the context window. Providers sell context length; models deliver *effective* context. RULER showed frontier models' working window is far shorter than their advertised one even on synthetic retrieval tasks, and NoLiMa showed performance degrades long before the window fills whenever a task needs reasoning beyond literal token matching. Budgeting is how you stay inside the region where the model actually works — while controlling a cost line that scales linearly with every token you keep.

## Core concepts

### Advertised window vs effective window

The advertised window is a hard API limit (a 400 error past it). The effective window is where accuracy holds. Two verified anchors:

- **RULER (arXiv 2404.06654)** — configurable synthetic tasks (NIAH variants, variable tracking, aggregation, QA) measure *operation* at depth, not just retrieval. Long-context models that ace 128K needle tests degrade sharply on multi-hop/aggregate tasks well inside the window.
- **NoLiMa (arXiv 2502.05167)** — tasks requiring *associative* reasoning (connect "car" ↔ "vehicle") rather than literal matching: 10 top models average >50% degradation at just 32K context. Literal-match tasks survive; reasoning-under-noise tasks do not.

Expert takeaway: treat "it fits in the window" as a capacity fact, never a capability claim. Your real budget is the shortest of {advertised window, provider output cap, your cost ceiling, your task's effective-context depth}.

### The context budget as an allocation table

For a 200K-token window (Claude Sonnet 5.5 / GPT-6-class; Gemini 3.x and the 1.05M-token GPT-6 family push higher), a production agent's budget:

| Slot | Tokens | % | Stability (for caching) |
|------|--------|---|------------------------|
| System prompt | 2,000 | 1% | Static — cache anchor |
| Tool definitions | 3,000 | 1.5% | Static — cache anchor |
| Retrieved context (RAG) | 20,000 | 10% | Per-request |
| Conversation history | 30,000 | 15% | Append-only growth |
| Working memory / scratchpad | 5,000 | 2.5% | Volatile |
| User input | 1,000 | 0.5% | Volatile |
| Reserved for output | 8,000 | 4% | — |
| Headroom | 131,000 | 65% | Deliberate |

Two notes experts disagree on, and why the table keeps 65% headroom: (1) utilization-based recall loss is real but task-dependent (NoLiMa-style associative tasks hurt earliest); (2) nobody measures recall on *their* task by default. Keeping active budget ≤ 50% of window is a hedge until you've run your own depth eval (`../07-evals/`).

### The five context sins

1. **Stale history** — every old turn dilutes attention to the current turn. Attention is a normalized competition: more tokens = smaller per-token share.
2. **Verbatim tool output** — full API responses bloat context; summarize. A single 500KB JSON dump is ~125K tokens: one bad tool result can eat half the window.
3. **Duplicate system prompts** — re-sent per request without caching. Untracked but easy to prove from `usage` telemetry.
4. **Unranked retrieval** — 20 chunks dumped in insertion order, not relevance. Position matters: **primacy and recency dominate the middle** (Lost in the Middle, arXiv 2307.03172). Order chunks best → worst, or place the best chunk last.
5. **No scratchpad eviction** — intermediate thoughts accumulate. Claude's interleaved thinking blocks and tool results are the usual silent bloat.
6. **Attention sinks** — models fixate on the first tokens of a sequence (streaming LLMs must keep them or output collapses, arXiv 2309.17453); the practical consequence is that your first tokens get outsized attention whether you want that or not — put the real policy there, not a greeting.

### Why the middle decays (mechanism)

Decoder attention is softmax-normalized over all previous tokens. With 100K tokens of context, attention mass spreads thin unless the query sharply matches specific keys. Retrieved-but-irrelevant tokens are distractors that *actively* absorb attention, not neutral padding — this is why "add more context" can *reduce* accuracy on multi-hop questions (NoLiMa's core finding). Mitigation is pre-filtering (retrieval quality), not window growth.

## Code: budget guard with a real tokenizer

The `len(text) // 4` heuristic is ±50% wrong across domains. Use the real thing:

```python
from tiktoken import get_encoding
_enc = get_encoding("o200k_base")  # GPT-6-family encoding

def n_tokens(text: str) -> int:
    return len(_enc.encode(text))

def tokens_for_message(msg: dict) -> int:
    # Provider message framing overhead (chatml-style): ~4-6 tokens per message
    # in addition to content. Exact constant varies by provider; 5 is the
    # conservative planning number.
    return n_tokens(msg.get("content", "")) + 5

def trim_history(history: list[dict], budget_tokens: int = 30_000) -> list[dict]:
    '''Keep system message + most recent turns within budget, oldest dropped first.'''
    if not history or history[0]["role"] != "system":
        return history
    out = [history[0]]
    running = tokens_for_message(history[0])
    for m in reversed(history[1:]):
        cost = tokens_for_message(m)
        if running + cost > budget_tokens:
            break
        out.insert(1, m)
        running += cost
    return out
```

Cost check before you ship the guard: at $2/1M input (GPT-6.1 Sol class), a 30K-token history cap costs ≈ $0.06/call at the fresh-input rate; prompt caching cuts that ~10x on the stable prefix (`01-llm-calling/06-prompt-caching.md`). The guard pays for itself the first time it prevents a 150K-token call.

## Production concerns

- **Latency:** Prefill is bandwidth-and-compute bound over input length. Rule-of-thumb from the serving math in `00-foundations/02-kv-cache-and-inference.md`: TTFT scales roughly linearly with uncached input tokens. Cached prefixes skip most of it.
- **Cost:** Linear in fresh input tokens; per-domain ratios (code ~3.5 chars/token, prose ~4, CJK up to 1) make the naive `//4` estimator dangerous for billing projections — encode with the actual tokenizer (`tiktoken` for OpenAI, `anthropic.count_tokens` for Claude).
- **Failure modes:** The model ignoring instructions in the middle of long contexts is a positional effect (Lost in the Middle), not a "flaw" you can prompt away. Re-state critical rules at the end of the turn where recency wins.
- **Security:** Retrieved context is untrusted — it can contain prompt injections (see `04-prompt-injection-defense.md`). Budget discipline and injection defense interact: compaction summaries of untrusted content inherit its instructions unless you mark provenance.
- **Observability:** Tag every request with input_tokens, cached_tokens, and (where exposed) reasoning_tokens. A "context budget" you don't measure is a guess. Alert on p95 input tokens per route.

## Anti-patterns

- ❌ **Stuffing all retrieved chunks into one user message.** Hard for the model to cite sources; worse recall.
- ❌ **Keeping full tool outputs in history.** Summarize after each tool call; keep raw artifacts outside the window, keyed by ID.
- ❌ **Assuming "fits in context" = "model will use it."** Test recall empirically with your own depth probes; NoLiMa warns literal-match evals overestimate you.
- ❌ **Budgeting with `len//4`.** Off by up to 50% per domain; breaks cache-breakpoint planning too.

## Decision framework

| Symptom | Fix |
|---------|-----|
| Cost spikes on long sessions | Cache the stable prefix; compact history past the budget |
| Model misses early instructions | Re-state critical rules at the end; shrink working set |
| Recall drops mid-conversation | Distill old turns (`03-context-distillation.md`) instead of truncating |
| Needle test passes, multi-hop fails | Effective window < advertised — restructure to retrieval + short working set |
| Window genuinely too small | Retrieve instead of stuffing (`../03-rag/08-long-context-vs-rag.md`) |

## References

- [RULER: What's the Real Context Size of Your Long Context Language Models?](https://arxiv.org/abs/2404.06654) — verified 2026-10-20
- [NoLiMa: Long-Context Evaluation Beyond Literal Matching](https://arxiv.org/abs/2502.05167) — verified 2026-10-20
- [Lost in the Middle](https://arxiv.org/abs/2307.03172) — verified 2026-10-20
- [Anthropic: Contextual retrieval](https://www.anthropic.com/news/contextual-retrieval) — verified 2026-10-20
- [Efficient Streaming Language Models with Attention Sinks](https://arxiv.org/abs/2309.17453) — verified 2026-10-20
