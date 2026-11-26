# Context Engineering — Interview Questions

> **Rung:** [02-context-engineering](../../02-context-engineering/01-context-budgeting.md) · **Last verified:** 2026-10-20

## Q1 — Your agent answers the first question well but misses instructions by turn 30. Diagnose

**Model answer:** Classic context-degradation signature. First hypothesis: the working context has grown past the region where instruction-following holds — not the hard window limit, the *effective* one. Instruction strength decays with distance from the ends (primacy/recency; "lost in the middle"), and NoLiMa-style results say associative tasks degrade well before the window fills. By turn 30, the system prompt's rules are competing with ~30 turns of history for attention.

Ordered fixes: (1) measure — log input tokens at the failure turns; (2) compact: distill old turns into a structured summary (decisions, open questions, artifacts — not prose), keeping the recent window fresh; (3) re-anchor: restate the critical rules near the *end* of the context where recency wins, instead of trusting position 0; (4) if the task is genuinely long-horizon, move to a platform with native compaction or a checkpointer-based design where context resets at semantic boundaries instead of decaying continuously.

**Senior note:** the failure is usually *silent quality decay*, not an error — so the diagnosis starts with "do we have per-turn telemetry proving it's context-related?" A/B a compacted vs raw-history variant on the golden set before touching anything else; sometimes the real culprit is a tool whose outputs quietly doubled in length.

## Q2 — Explain prompt caching to someone who thinks it's "just memoization"

**Model answer:** It's the provider's KV-prefill for your prefix, kept warm and priced. On a hit, the provider skips *recomputing prefill* on those tokens — so it cuts both price (~10x) and TTFT (30-60%). Unlike memoization, the match isn't keyed on your whole request: it's **prefix-exact at the token level** from position 0. One changed token at the front invalidates everything after it; identical 5K-token suffixes don't help.

That rule generates all the engineering discipline: static content first, dynamic last; no timestamps or request-IDs in the prefix; tool-definition serialization must be byte-stable (key order included — a re-serialized dict is a new prefix); on Anthropic you place explicit breakpoints (up to 4) and pay a write premium (1.25x for 5-min TTL, 2x for 1h) — so a *churning* prefix costs more with caching than without. Measure `cached_tokens` / `cache_read_input_tokens` per route; a hot path under 50% hit rate is a bug.

**Senior note:** the trap most teams hit — compaction and caching fight each other. Rewriting history mid-conversation invalidates the cache from the rewrite point onward; aggressive summarization can be net-negative on cache-heavy workloads. Compact rarely, append instead of rewrite, and measure hit rate before/after enabling compaction.

## Q3 — What's wrong with this system prompt: 40 policies, 3 personas, few-shot examples, and the output format in prose?

**Model answer (itemized):**

1. **40 policies** — instruction-following is probabilistic and every policy competes in the same attention pool; compliance drops as instruction count grows. Either policy-RAG (retrieve the applicable rules) or split agents.
2. **3 personas** — conflicting frames produce bimodal output; one role anchor with specifics beats personality stacking.
3. **Examples in the system prompt** — few-shot examples steer output format more strongly than prose rules, and they live in your most expensive real estate; put them in a stable block (cacheable) or user turns.
4. **Format in prose** — constrained decoding (structured outputs) makes syntactic compliance guaranteed by token masking; prose format instructions spend attention on what the decoder can enforce for free.
5. **Unstated ordering** — the prompt ignores primacy/recency: policies belong early, tool guidance late, and the whole thing must be cache-ordered (stable → volatile) or every request re-pays full prefill price.

**Senior note:** the meta-answer is *testability* — a 40-policy prompt can't be regression-tested because no golden set covers 40 dimensions. Rewrite as trigger→action pairs ("refund > $500: call escalate_tier2"), each becoming one eval case; the prompt becomes its own test plan.

## Q4 — Design the defense stack for an agent that reads web pages and can send emails

**Model answer:** Start from the architecture, not the prompts: this is the canonical privilege-separation case. The reader agent (browses untrusted pages) gets **no tools** — it can't send anything, so a successful injection is contained by construction. A separate trusted agent with email capability receives only *summarized, structured* findings from the reader — never raw untrusted text. That one design decision eliminates the exfiltration class, which no amount of "ignore instructions in documents" prompting can.

Then layer: spotlighting on anything that must pass through (per-request random delimiters so injected text can't pre-declare its own un-marking); an injection classifier on retrieved content at *index/corpus time* (not per-request — amortize); email-tool allowlist with per-recipient approval for first-time addresses; human-in-the-loop for external sends in sensitive flows; and red-team the assembled system with Garak/PyRIT in CI, tracking bypass rate as a metric.

**Senior note:** articulate *why* prompt-level defenses can't be the boundary — instruction and data channels are not architecturally separable in a single context; the model conditions on one token stream. So the load-bearing wall is capability scoping; classifiers and spotlighting are layers on top. If asked "is that enough?" — no single layer is; the question is whether the residual, after layering, can do harm given the capability design (a bypassed spotlight on a read-only reader is an annoyance).

## Q5 — When do you actually pay for a thinking model?

**Model answer:** When the task is in the *verifiable-difficulty* regime: multi-step math, code with tests, agentic planning where the chain of decisions benefits from explicit deliberation. There, test-time compute buys real accuracy, roughly log-linearly before flattening. When you *don't*: extraction, classification, summarization — the overthinking literature (o1-class models burning thousands of tokens on trivial arithmetic; Chain-of-Draft cutting reasoning tokens ~85% with comparable accuracy) shows verbosity is partly a style prior, not a necessity.

The operational answer is routing with budgets: `reasoning_effort`/`thinking` dials per route; a cheap tier with thinking off for the 80% simple traffic; hard caps for latency paths. And measure reasoning tokens per route in usage telemetry — it's the line item that silently turns $0.02 calls into $0.50 when a default flips.

**Senior note:** the agent-loop multiplier — an agent that thinks between every tool call multiplies thinking cost by tool-call count; 10 steps × 2K thinking tokens = 20K output-priced tokens per request before any visible output. Also know the two failure directions: overthinking (route down) and budget exhaustion mid-loop (later tool calls get truncated reasoning — worse than no thinking).

## Q6 — How do you decide between truncating history, summarizing it, or moving to a durable-state design?

**Model answer:** Truncation (keep last N turns) is the baseline — cheap, lossy at the *boundaries* (drops the oldest context wholesale, losing long-range dependencies like early decisions). Summarization/compaction preserves tier-1 information (decisions, commitments, open questions) in structured form — better fidelity, costs a background LLM call, and interacts with prompt caching (rewrites invalidate prefixes). Durable state (checkpointer, memory tools, artifact store) is the architectural answer for long-horizon work: state lives *outside* the context and is retrieved on demand — the context window stops being the database.

Decision drivers: session length (short: truncate; medium: summarize; hours/many-session: durable state), whether decisions must survive restarts (only durable state guarantees that), cache economics (append-only designs preserve prefixes; rewrites don't), and eval infrastructure (compaction and memory are behavior changes — gate them).

**Senior note:** name the failure of each: truncation loses early commitments ("what did we agree?"); prose summaries hide missing decisions (structured extraction makes omissions visible as empty lists); naive durable-state designs retrieve stale "facts" that contradict live tools — memory is hints, the system of record is the source of truth.
