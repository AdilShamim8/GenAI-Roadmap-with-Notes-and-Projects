# LangGraph Stateful Agents

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [LangGraph docs](https://docs.langchain.com/oss/python/langgraph/)

## Why this matters

When you need durable, multi-step, multi-agent workflows with explicit state, conditional branching, and human-in-the-loop checkpoints, LangGraph is the most mature option. Since October 2025 it is a **1.0-stable** line (no breaking changes from 0.3 — LangChain 1.0's `create_agent` is built on the same runtime). It's more verbose than OpenAI Agents SDK or Claude Agent SDK, but it gives you control nothing else matches. The expert framing: LangGraph is not an agent framework with graph features — it's a *durable execution engine* that happens to run LLM nodes. That's the lens that predicts when it's worth the verbosity.

## Core concepts

### The graph

A LangGraph agent is a directed graph where:

- **Nodes** are functions (or LLM calls).
- **Edges** are conditional or unconditional transitions.
- **State** is a typed dict (or Pydantic model) passed between nodes.
- **Checkpoints** serialize state at every step, enabling pause/resume.

### Why durable execution is the real product

Most "agent frameworks" hide state in closure variables. LangGraph makes it explicit — you can serialize it, replay it, fork it, time-travel it. What that buys you, concretely:

- **Crash recovery.** A 40-step workflow that dies at step 38 resumes from checkpoint 37 — the LLM calls already made (the expensive part) aren't repeated. Without checkpoints, a crash means a full re-run: full cost, full latency, and *different results* (non-determinism), which breaks anything downstream expecting the earlier partial state.
- **Human-in-the-loop as a first-class pause.** `interrupt_before=["tools"]` stops *before* side effects, parks state in the checkpointer, and resumes on approval — hours or days later, in a different process. This is the mechanism that makes "agent asks for approval" operationally real rather than a UI overlay.
- **Deterministic replay for debugging.** Given a checkpoint and the graph version, you can re-execute from any point and watch the state evolve — the closest thing agents have to a time-travel debugger.
- **Time-travel as a product feature.** Fork from an old checkpoint ("what if we'd taken the other branch?") is a few lines on top of the checkpointer.

The cost is honest too: state must be *serializable* (every node's inputs/outputs cross the checkpoint boundary — Pydantic models or plain dicts, not live DB connections), and state *shape* becomes API you must version (an old checkpoint replayed against a renamed state field breaks).

### Reducers — the state-merge semantics most people miss

`messages: Annotated[list, add_messages]` isn't decoration; it's a **reducer** — the function that merges node outputs into state. `add_messages` appends (deduplicating by id); without an annotation, node returns *overwrite* the field. This is the difference between "each node contributes its observations" and "each node replaces the truth," and it's the #1 source of "where did my state go" bugs. Design rule: accumulative fields (messages, found-artifacts, log) get reducers; single-truth fields (current_plan, final_answer) stay overwriting.

### Graph design — control flow you own

Unlike prompt-driven agents (where the model chooses the next step), graph edges are *your* code. The tradeoff:

- You gain: testability (edges are pure functions of state), auditability (the path taken is explicit), and reliability on the happy path.
- You give up: the model's ability to improvise structure. A rigid graph can't handle "the task turned out to need a step that isn't a node."

The 2026 consensus architecture mixes both: graphs for the *process skeleton* (deterministic stages: intake → plan → execute → review), agent loops *inside* nodes for the improvisational parts (the "execute" node runs a ReAct loop with tools). You get structure where it matters and autonomy where it helps. Node-level agent loops still need their own turn caps — the graph's recursion limit is not a substitute for an inner-loop `max_turns`.

## Code: a ReAct agent in LangGraph

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

class State(TypedDict):
    messages: Annotated[list, add_messages]  # reducer: append, don't overwrite

@tool
def get_weather(city: str) -> str:
    '''Get weather for a city.'''
    return f"Sunny, 22C in {city}."

llm = ChatOpenAI(model="gpt-6.1-sol").bind_tools([get_weather])

def call_model(state: State):
    return {"messages": [llm.invoke(state["messages"])]}

def should_continue(state: State):
    last = state["messages"][-1]
    return "tools" if last.tool_calls else END

from langgraph.prebuilt import ToolNode

graph = StateGraph(State)
graph.add_node("agent", call_model)
graph.add_node("tools", ToolNode([get_weather]))
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", should_continue, ["tools", END])
graph.add_edge("tools", "agent")
app = graph.compile()

result = app.invoke({"messages": [("user", "Weather in Tokyo?")]})
print(result["messages"][-1].content)
```

## Code: human-in-the-loop checkpoint

```python
from langgraph.checkpoint.memory import MemorySaver

app = graph.compile(
    checkpointer=MemorySaver(),   # use PostgresSaver/RedisSaver in prod
    interrupt_before=["tools"],   # or the interrupt() function API
)
config = {"configurable": {"thread_id": "abc"}}
result = app.invoke({"messages": [("user", "Delete the file /tmp/data.csv")]}, config)
# Inspect result["messages"][-1].tool_calls; if approved:
app.invoke(None, config)  # resumes
```

`thread_id` is the conversation/session key — checkpointer state is *per-thread*. The subtle production point: `interrupt_before` parks *before* the node runs, so the tool call is visible in state (you can inspect what it *wants* to do) but hasn't executed — the correct interception point for approvals. Resuming with `app.invoke(None, config)` continues as if nothing happened; resuming with a modified state lets your approval flow inject constraints.

## Production concerns

- **Latency:** Graph overhead is ~10ms per node. Negligible vs LLM calls — but checkpoint writes are I/O: a Postgres checkpointer adds a write per step. Batch or accept it; do not checkpoint inside tight inner loops.
- **Cost:** State size affects checkpoint storage cost — keep state lean (don't put raw 50KB tool outputs in state; store an artifact ID, fetch in the node that needs it). This mirrors context discipline: state is your durable context.
- **Failure modes:** (1) cycles looping forever — set `recursion_limit` (it counts *super-steps*, and exceeding it raises `GraphRecursionError` — catch it, don't let it 500 your API); (2) non-serializable state sneaking in (a live client object in state fails at checkpoint time, mid-run); (3) checkpoint-version drift — you changed the state schema, old threads can't resume; plan migrations or version the graph.
- **Security:** State/checkpoints can contain PII — they persist whatever flowed through. Encrypt checkpointer storage at rest; scope retention (a durable store of every conversation's full state is a data-subject-request nightmare). `thread_id` is also an isolation boundary — one user resuming another's thread id is an authorization bug class unique to checkpointed systems.
- **Testing:** Edges are pure state→state functions — unit-test them without any LLM. Nodes with LLM calls get eval-suite treatment (`../07-evals/`). This testability split is half the value of the graph model.

## Anti-patterns

- ❌ **Using LangGraph for a simple ReAct loop.** OpenAI Agents SDK — or LangChain 1.0's `create_agent` (LangGraph under the hood, 10 lines) — is simpler.
- ❌ **Putting everything in state.** Only what nodes need; artifacts by reference.
- ❌ **No recursion limit.** `app.invoke(..., config={"recursion_limit": 25})`.
- ❌ **MemorySaver in production.** It's in-memory only; use the Postgres or Redis checkpointer.
- ❌ **Non-serializable objects in state.** Fails at checkpoint time.
- ❌ **Renaming state fields without a checkpoint migration plan.** Old threads break silently.

## Decision framework

| Need | Use |
|------|-----|
| Simple ReAct agent, any provider | `create_agent` (LangChain 1.0) or OpenAI Agents SDK |
| Custom graph, conditional edges, durable state | Raw `StateGraph` (this file) |
| Pause/resume + human approval | Checkpointer + `interrupt_before` / `interrupt()` |
| Multi-hour workflows with retries | LangGraph + Postgres checkpointer, or a durable-execution layer |
| Mixed structure + autonomy | Graph skeleton + agent-loop nodes |

## References

- [LangGraph docs](https://docs.langchain.com/oss/python/langgraph/) — verified 2026-10-20
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph) — verified 2026-10-20
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) — verified 2026-10-20
