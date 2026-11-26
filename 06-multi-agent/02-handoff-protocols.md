# Handoff Protocols

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [OpenAI Agents SDK handoffs](https://openai.github.io/openai-agents-python/handoffs/), [A2A protocol](https://a2a-protocol.org/latest/)

## Why this matters

When agent A hands off to agent B, what exactly passes between them? Get this wrong and you get context loss, repeated work, or state corruption. Handoffs are the seams of multi-agent systems — and seams are where things break. The expert framing: a handoff is a *serialization boundary*. Everything not explicitly passed is lost, and everything passed must be interpretable by the receiver — the same class of problem as an API contract, with the twist that the "parser" on the other side is a model that will *improvise* when the contract is ambiguous.

## Core concepts

### What gets passed

- **Task description** — what B should do.
- **Relevant context** — distilled, not raw transcript.
- **State** — typed object (Pydantic model or TypedDict).
- **Artifacts** — files, IDs, URLs produced so far.
- **Return protocol** — when B is done, what should it return to A?

The deep design question each item hides: *how much context does B need to do its job well?* Too little → B re-asks or guesses (visible as repeated work or wrong assumptions); too much → you pay tokens for context B ignores, and B gets *contaminated* by A's frame (B inherits A's interpretation of an ambiguous task instead of forming its own). The distillation is lossy compression with a purpose — keep what B's job depends on, drop what only mattered to A's job.

### Three handoff styles

| Style | Example | When | Contract enforcement |
|-------|---------|------|---------------------|
| **Message-based** | "Tell the billing agent the user wants a refund for order X" | OpenAI Agents SDK | Weak — free-text prompt, receiver improvises |
| **State-based** | Pass a typed state object | LangGraph | Strong — schema is code, checked at runtime |
| **Shared-blackboard** | All agents read/write a shared store | Network topology | Implicit — whoever writes last wins; needs ownership rules |

The enforcement column is the expert addition: message-based handoffs are *conventions* (B might ignore fields, misread emphasis); state-based handoffs are *contracts* (schema-validated, versionable). The failure signatures differ: conventions fail silently (B "understood" differently), contracts fail loudly (schema mismatch = error). Loud failures are easier to fix — one reason typed-state systems (LangGraph) dominate production multi-agent.

### The return protocol — the half everyone forgets

Defining what B returns is as important as what A sends. Without a return contract: B answers in its own format; A must re-parse prose; downstream code can't rely on the result. With one (B's `output_type` is a schema; A's next step consumes it typed) the composition becomes testable end-to-end. Two patterns:

- **Handoff (transfer)** — B's output *is* the final output; A is out of the loop. No return needed, but then A never sees what happened — fine for routing, wrong when A must integrate.
- **Delegation (agent-as-tool)** — B is a tool A calls; B returns its schema; A continues. This is the supervisor pattern's backbone (`05-agents/01-openai-agents-sdk.md`), and the return schema is what makes it composable.

### Handoff hygiene — four rules

1. **Pass the original goal, not just the sub-task.** B without the goal optimizes the sub-task locally ("found 50 sources!") when the goal needed 3 good ones. One line of goal context prevents local optimization.
2. **Declare what's already done.** The #1 duplicated-work cause: B re-does what A already tried. "Already attempted: X (failed, reason); Y (succeeded, artifact at Z)" is cheap and prevents it.
3. **Schema both directions.** Input contract and output contract, both typed, both versioned.
4. **Never hand off mid-tool-call.** The handoff boundary should be at a *completed* semantic step (tool results in, summary out), not between a tool call and its result — receivers that inherit half-finished tool states improvise badly.

### Cross-vendor handoffs: A2A

Framework-native handoffs (Agents SDK, LangGraph) assume one process. When agents live in *different* systems — different vendors, companies, or trust domains — the **Agent2Agent (A2A) protocol** (Linux Foundation) is the interop layer: agents advertise capability documents (agent cards), communicate over JSON-RPC with task lifecycle semantics, and negotiate content types per message. A2A complements MCP rather than competing with it: MCP connects an agent to tools; A2A connects agents to agents.

A2A's model is *task-lifecycle*, not conversation-carrying: a task has states (submitted, working, completed, failed), and agents exchange messages/artifacts within that envelope. The expert read on the A2A/HTTP analogy: it inherits web semantics deliberately — agent cards are like `/.well-known/` discovery, tasks are like job submissions with polling or streaming updates. What it does *not* standardize is the payload semantics — your typed contracts still matter inside the envelope; A2A moves them, your schemas give them meaning. And trust: cross-organization handoffs need authentication and *authorization* at every hop (B should verify A's identity and scope, not blindly execute) — the same discipline as federated API access.

## Code: OpenAI Agents SDK handoff

```python
from agents import Agent, Runner

billing = Agent(name="Billing", instructions="You handle refunds. Return a JSON with refund_id and amount.", model="gpt-6.1-sol")
triage = Agent(name="Triage", instructions="Route to billing.", handoffs=[billing], model="gpt-6.1-sol")

result = Runner.run_sync(triage, "I want a refund for order 123.")
# Triage calls handoff to billing; billing runs to completion; final output is billing's.
```

## Code: LangGraph state handoff

```python
class State(TypedDict):
    user_query: str
    billing_decision: dict | None
    final_response: str | None

def triage(state: State) -> State:
    if "refund" in state["user_query"].lower():
        return {**state, "next": "billing"}
    return {**state, "next": "support"}

def billing(state: State) -> State:
    # ... process refund
    return {**state, "billing_decision": {"refund_id": "r_123", "amount": 49.99}}
```

## Code: delegation with a typed return (the composable pattern)

```python
from pydantic import BaseModel, Field

class RefundDecision(BaseModel):
    refund_id: str | None
    amount: float = Field(ge=0)
    reason: str

billing_tool = billing.as_tool(
    tool_name="process_refund",
    tool_description="Process a refund; returns decision with refund_id and amount.",
)
# The supervisor stays in the loop, consumes RefundDecision typed, and can
# retry, compensate, or integrate — impossible with an untyped handoff.
```

## Production concerns

- **Latency:** Each handoff is a fresh LLM call with new context — the receiver re-primes (instructions + payload). Distillation cuts the payload; nothing cuts the re-priming. Chain length, not agent count, drives latency: 5-deep handoff chains are 5× TTFT.
- **Cost:** Distill context before handoff; don't pass raw transcripts — you pay for every token B never uses, on every handoff.
- **Failure modes:** (1) handoff target doesn't exist — validate capability registries at startup, not call time; (2) state schema mismatch — version the contracts, fail loudly on drift; (3) receiver ignoring passed context (re-asking the user what A already knew) — eval handoffs end-to-end with replayed transcripts (`../07-evals/`); (4) circular handoffs A→B→A — cycle detection at the orchestrator.
- **Security:** Don't pass PII across agents that don't need it — handoffs are data-flow events; log them as such (DLP-visible). Cross-trust-domain handoffs (A2A) need per-hop authn/authz and payload minimization: B gets what its task needs, never the whole user record.

## Anti-patterns

- ❌ **Passing the entire conversation history.** Distill.
- ❌ **No return type from the handoff target.** You can't act on what you can't parse.
- ❌ **Circular handoffs.** A→B→A→B→...
- ❌ **Sub-task without the goal.** Receivers locally optimize.
- ❌ **Handing off without declaring what's done.** Duplicated work.
- ❌ **Untyped handoffs in production.** Conventions fail silently; contracts fail loudly.

## References

- [OpenAI Agents SDK handoffs](https://openai.github.io/openai-agents-python/handoffs/) — verified 2026-10-20
- [LangGraph multi-agent](https://docs.langchain.com/oss/python/langchain/multi-agent) — verified 2026-10-20
- [A2A protocol](https://a2a-protocol.org/latest/) — verified 2026-10-20
