# Agents — Interview Questions

> **Rung:** [05-agents](../../05-agents/01-openai-agents-sdk.md) · **Last verified:** 2026-10-20

## Q1 — Compare the OpenAI Agents SDK, Claude Agent SDK, and LangGraph in one breath each, then pick one for a support agent with human-approval escalations

**Model answer:** **OpenAI Agents SDK** — a thin, unopinionated loop runtime: agents as immutable config, handoffs, guardrails hooks, tracing; you own structure and state. **Claude Agent SDK** — an *operator* subprocess (the Claude Code engine): engine-managed compaction, built-in hardened file/bash/search tools, permission callbacks, sessions with fork — built for hours-long file work. **LangGraph** — a durable execution engine: typed state, checkpointed steps, interrupt/resume — graphs as the process skeleton.

For a support agent with human escalations: **LangGraph**. The escalation requirement is a *pause*: state must park at "interrupt_before the escalation action," survive until the human responds (possibly hours), and resume exactly — that's a checkpointer (`interrupt_before` + durable saver), which is LangGraph's core primitive. The OpenAI SDK has no native pause; you'd build state persistence yourself. The Claude Agent SDK is shaped for file-operating work, not conversational support.

**Senior note:** the honest caveat — if the support agent is mostly single-turn with occasional escalation, OpenAI SDK + a database row for pending approvals is *simpler* and ships faster. Choose the tool for the statefulness you actually have; "human approval" only demands a checkpointer when approvals are slow and state is rich.

## Q2 — What actually distinguishes agent frameworks from each other, technically?

**Model answer:** Three axes predict your experience better than feature matrices: **where control flow lives** (LangGraph: your code — edges are testable functions; CrewAI: the framework's conventions — fastest to demo, interpretive to debug; MS Agent Framework: typed workflows + actor-model async — distributed scale), **how state is treated** (explicit/typed/checkpointed vs ambient in closures), and **what failure mode the abstraction makes easy** (hidden control flow means behavior is a function of framework version + prompts — pin and eval both).

And the graveyard factor: AutoGen retired in Oct 2025 (projects stranded); framework risk is real, so keep domain logic framework-agnostic — tools, prompts, schemas as plain Python; the framework is a replaceable orchestration shell.

**Senior note:** the 2026 consensus architecture mixes both — graph skeleton for deterministic stages, agent loops *inside* nodes for improvisational parts; structure where it matters, autonomy where it helps. Inner loops still need their own turn caps; the graph's recursion limit is not a substitute.

## Q3 — Design a memory system for a personal assistant that persists across sessions

**Model answer:** Start from the memory-type split, because each has a different correctness criterion: **episodic** (what happened when — vector-retrievable), **semantic** (facts about the user — must be *true and current*, so latest-wins with history, not accumulating contradictions), **procedural** (how the assistant should behave — that's prompt content, evaluated like prompts).

The write path is the quality bottleneck: not "store the transcript" but *extraction with an update decision* — given existing memories and this turn, what's new, what's updated, what's contradicted (Mem0's design). The read path: top-K by relevance × recency, per-type lookup (semantic facts get direct lookup, not fuzzy search). Governance: per-user isolation (a data-boundary requirement), deletion that actually purges the vector index, provenance tags on every memory.

Two failure modes to name: **staleness** — retrieved memory as ground truth confidently contradicts the live system of record; the rule is memory-as-hints, tool-call-as-truth for anything authoritative. **Injection persistence** — a malicious message in one session writes a memory that re-injects into every future session; sanitize and provenance-tag at *write* time.

**Senior note:** the eval is golden Q&A over past sessions ("what did I say my setup was?") *plus* staleness tests where the correct answer is "call the tool, don't trust memory" — most memory systems are only tested on recall, never on knowing when not to trust themselves.

## Q4 — A production agent needs retries, fallbacks, and guardrails. Design the stack

**Model answer:** As a failure-budget system, spending where probability × consequence is highest:

**Guardrails** (prevent): deterministic first — schema validation, PII regex, allowlists (cheap, exact, testable); model-based second, only for judgments rules can't make, placed *between* model and tool for dangerous steps (an output guardrail after the tool ran is an audit, not a guard). **Retries** (recover): only idempotent operations; retryable errors only (429/5xx with backoff + jitter + `Retry-After`; never 400/401/403); caps on attempts *and* wall-clock, with the retry budget ⊂ the SLO. **Fallbacks** (degrade): cross-provider chain ordered by availability/cost/fit — and a fallback is a *designed UX state*: mark degraded responses, because silent quality drops train users to distrust everything.

**Senior note:** the pieces teams skip — timeout *per attempt* (a hung call blocks the chain and the retry policy never fires); idempotency keys on tool calls (a timed-out payment tool retried blind charges twice — timeouts need reconciliation, not retries); and failure-injection tests (kill the primary in staging; an untested fallback fails exactly when needed).

## Q5 — "We need multi-agent." What do you ask before writing code?

**Model answer:** What's forcing it? Multi-agent is justified by four specific constraints: **context isolation** (subtasks need incompatible contexts — the researcher's 50 documents shouldn't carry the writer's prose constraints), **parallelism** (independent subtasks where wall-clock matters), **permission separation** (different trust levels per subtask — the untrusted-content reader gets no write tools; that's a topology decision, not a policy), **specialization** (different models per stage). None of these → single agent with good tools wins: fewer moving parts, one context to debug, no handoff losses.

If multi-agent is warranted: supervisor (router vs planner distinction matters — planner-supervisors bloat context with every worker report) or agent-as-tool for composition; structured handoffs in *both* directions (input contract + typed return); correlation ids for cross-agent debugging; convergence criteria designed upfront (the failure nobody expects is live-lock — agents productively busy, never converging).

**Senior note:** the anti-pattern to name — multi-agent "because it's more powerful." It's more *expensive*; it's more powerful only when a specific constraint demands it. And every handoff is a serialization boundary: everything not explicitly passed is lost, and the receiver will improvise where the contract is ambiguous.
