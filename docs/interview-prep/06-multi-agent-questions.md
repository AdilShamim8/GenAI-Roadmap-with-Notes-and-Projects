# Multi-Agent Systems — Interview Questions

> **Rung:** [06-multi-agent](../../06-multi-agent/01-orchestration-topologies.md) · **Last verified:** 2026-10-20

## Q1 — Your multi-agent system has agents duplicating work and occasionally deadlocking. Diagnose the topology

**Model answer:** Duplicated work + deadlock in one system points at a **network or swarm topology without coordination contracts**. Duplicated work: two branches solved the same sub-task because nothing declared ownership — artifact IDs deduplicate (whoever writes first wins, later writers detect the existing artifact and read it). Deadlock: cyclic handoffs (A waits on B waits on A) with no timeouts — put a timeout on every wait and break cycles at the orchestrator with (agent, task) pair tracking.

The structural fix: move toward a supervisor or hierarchy where *someone owns dispatch* — the topology question is really "where does control live." Supervisor buys predictability with a bottleneck; swarm buys flexibility with drift; network buys power with chaos. Production networks are always *constrained* — allowlists of who may call whom, cycle detection.

**Senior note:** the failure that surprises teams isn't deadlock but **live-lock** — agents productively busy, never converging on done. The vaccine is checkable convergence criteria (goal predicates evaluated by code), iteration/depth caps that convert infinite loops into alertable errors, and budget termination that checkpoints and reports partial.

## Q2 — What crosses the boundary in a handoff, and what usually goes wrong?

**Model answer:** Five things cross: task description, distilled context, typed state, artifacts (IDs/URLs — not content), and the return protocol. A handoff is a *serialization boundary*: everything not explicitly passed is lost, and everything passed gets improvised on by the receiver when the contract is ambiguous.

The four rules that prevent the classic bugs: (1) pass the **original goal**, not just the sub-task — receivers without the goal locally optimize ("found 50 sources!" when 3 good ones were wanted); (2) declare **what's already done** ("attempted X, failed because Y") — the #1 duplicated-work cause; (3) schema **both directions** — typed input and typed return, or the caller re-parses prose; (4) hand off at **completed semantic steps** — receivers inheriting half-finished tool states improvise badly.

**Senior note:** distinguish transfer (handoff — B's output is final, A is out of the loop) from delegation (agent-as-tool — B returns a typed result, A composes). Supervisor patterns need delegation; routing patterns need transfer. And on cross-vendor: A2A standardizes the *envelope* (agent cards, task lifecycle, JSON-RPC), not payload semantics — your typed contracts still give messages meaning, and every hop needs authn/authz.

## Q3 — Long-horizon agent design: what's actually different from a 30-second agent?

**Model answer:** A 5-hour run is a stateful distributed system whose workers are non-deterministic and whose every step costs money. Four problems, with the classical counterparts you steal from: **state growth** (→ distillation at semantic boundaries, artifacts by reference); **failure recovery** (→ checkpoints as write-ahead logs — resume re-pays only the current step's context, not the full run; idempotent sub-task outputs under stable IDs make downstream references survive restarts); **cost control** (→ hard budgets with 50/80/100% alerts, *per-sub-task* attribution so postmortems identify which plan step burned it); **oversight** (→ periodic critic review with *fresh context* — the critic checks drift without inheriting the worker's frame — plus mechanical escalation triggers: cost > X, N consecutive failures, destructive-action requests).

What's genuinely new vs. classical systems: **soft failures** — a worker confidently taking the wrong branch at hour 2 raises nothing; detection is critics and eval hooks, and wrongness compounds silently. And resumption has *token cost*: re-priming context the crashed process already paid for.

**Senior note:** the product requirement everyone misses — a progress surface (done/running/blocked, spend vs budget, critic verdicts) fed by one structured event log that also drives alerts. And async UX contract: "started/progressing/done" with notification moments, never a synchronous spinner.

## Q4 — How do you size and bound a sub-agent?

**Model answer:** Sizing by the coupled columns: tools × iterations. Past ~15 tools, selection accuracy and context budget visibly degrade (the ">15 tools" row is where mis-selection compounds into more iterations into more context); the escape is splitting into 2-4 sub-agents of 5-8 tools, or a tool-router. Iterations: 5-10 for domain-bounded work; 25+ means the agent is improvising a plan, not executing one.

The boundary test that works: the one-sentence job description with no "and" — "retrieves and ranks sources" is two jobs (they fail for different reasons, get debugged differently, deserve separate evals). And when a sub-agent at all? Only when the job needs *multiple tool calls with judgment between them* — a millisecond tool call doesn't need a second LLM hop; and the real payoff is **context isolation** (the sub-agent's reading noise stays out of the parent's window).

**Senior note:** typed failure modes are the contract everyone skips — enumerate not-found / ambiguous / tool-error / low-confidence and give each a schema-shaped response. A sub-agent whose failures are as typed as its successes is composable; free-text "I couldn't find it, maybe try..." forces the parent to parse vibes. Plus model-tiering with a floor: cheap tier for mechanical jobs, but a too-cheap retrieval agent returns garbage the expensive parent then reasons about *confidently*.
