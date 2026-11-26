# Sub-Agent Design

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [Anthropic: Building effective agents](https://www.anthropic.com/research/building-effective-agents), [Claude Code subagents](https://platform.claude.com/docs/en/claude-code/sub-agents)

## Why this matters

Sub-agents are the unit of decomposition in a multi-agent system. Bad sub-agent boundaries produce duplication, conflicts, and untraceable failures. Good boundaries produce a system where each agent has a clear job and the composition feels natural. The expert framing: a sub-agent is a *service* — and the discipline that makes services work (single responsibility, explicit contracts, owned resources, failure semantics) applies almost verbatim. What's different from microservices: sub-agents run *inside one parent's turn*, share the parent's latency budget, and fail *softly* (plausible garbage) as often as they fail loudly.

## Core concepts

### The single-responsibility principle (for agents)

Each sub-agent should:

- Have one job (retrieval, synthesis, QA, planning).
- Have a clear input contract.
- Have a clear output contract.
- Own its own tools.
- Not need to know about other agents' internals.

The test for "one job" that works in practice: *can you write a one-sentence description with no "and"?* "Retrieves and ranks sources" is two jobs (retrieval quality and ranking quality fail for different reasons, get debugged differently, and deserve separate evals). The "and" test catches the most common boundary bug — agents defined by *artifact* ("the report agent") instead of by *capability* ("synthesizes findings into prose"), which leads to kitchen-sink tool grants.

### Why context isolation is the real payoff

The strongest reason to spawn a sub-agent (vs. one agent doing everything) is **context isolation**: the sub-agent burns its own context window on its job's noise (50 documents read, 20 searches) and returns only the distillate. The parent's context stays clean, which means the *parent's* reasoning stays high-quality for longer runs (effective-context limits, `02-context-engineering/01-context-budgeting.md`). Claude Code's sub-agent architecture is built exactly this way — the research sub-agent reads everything; the main thread sees a summary. When you're deciding whether something deserves sub-agent treatment, ask: *does this job produce context noise the parent shouldn't carry?* If no, a tool call suffices; a sub-agent adds latency and an LLM hop for nothing.

### Sizing

| Sub-agent complexity | Tools | Iterations | When |
|----------------------|-------|------------|------|
| Trivial | 1–2 | 1–3 | Single tool call + summary |
| Moderate | 3–7 | 5–10 | Multi-step within one domain |
| Complex | 7–15 | 10–25 | Cross-domain, multi-step |
| Too complex | >15 | >25 | Split into multiple sub-agents |

Reading the table like an expert: the columns are *coupled* — more tools means more selection errors, which means more iterations, which means more context, which degrades everything. The ">15 tools" row isn't a style violation; it's the point where tool-selection accuracy and context budget visibly degrade. The escape is hierarchical decomposition: a sub-agent with 20 possible tools should be 2-4 sub-agents with 5-8 each, or one agent with a tool-*router* (a retrieval step that loads relevant tools on demand).

### The contract pattern

Every sub-agent should declare:

- **Input schema** — Pydantic model.
- **Output schema** — Pydantic model.
- **Tools** — fixed list, not dynamic.
- **Failure modes** — what it returns when it fails.

The failure-modes line is the one teams skip, and it's what makes composition robust. "Returns `{"sources": [], "found": false}` when nothing found" is a *designed* failure — the parent can branch on it. An agent that free-texts "I couldn't find anything, maybe try different keywords?" forces the parent to parse vibes. Enumerate the failure modes (not found, ambiguous input, tool error, confidence-low) and give each a schema-shaped response. A sub-agent whose failure modes are as typed as its success mode is composable; anything less is a prompt with extra steps.

### Model-tiering across sub-agents

Sub-agents are where model-tier routing gets easy wins: the retrieval sub-agent (mechanical: search, filter, format) runs on a cheap tier; the synthesis sub-agent (judgment) runs frontier. The parent pays for exactly the intelligence each step needs. But watch the *floor*: a too-cheap retrieval agent mis-selects tools and returns garbage the expensive parent then reasons about confidently — garbage in, very articulate garbage out. Tier per sub-agent based on *its* error cost, not just its task glamor.

## Code: a well-designed retrieval sub-agent

```python
import json
from pydantic import BaseModel, Field
from agents import Agent, Runner, function_tool

class RetrievalInput(BaseModel):
    query: str = Field(description="The question to find sources for.")
    max_sources: int = Field(default=5, ge=1, le=20)

class RetrievalOutput(BaseModel):
    sources: list[dict] = Field(description="List of {title, url, snippet, score}")
    found: bool

@function_tool
def hybrid_search(query: str, k: int = 20) -> str:
    '''Hybrid vector + BM25 search. Returns JSON list of docs.'''
    return json.dumps(my_search_backend(query, k))   # your impl

@function_tool
def rerank(query: str, docs: list[dict]) -> str:
    '''Re-rank documents by relevance. Returns JSON list.'''
    return json.dumps(my_reranker(query, docs))      # your impl

retrieval_agent = Agent(
    name="RetrievalAgent",
    instructions='''You retrieve sources for a query.
    1. Call hybrid_search with the query.
    2. Call rerank on the results.
    3. Return the top-N sources as JSON.
    If no sources found, return {"sources": [], "found": false}.''',
    tools=[hybrid_search, rerank],
    model="gpt-6.1-sol",   # mechanical job: cheap tier works; test before assuming
    output_type=RetrievalOutput,
)
```

Note the design: typed failure (`found: false`), fixed tool set (2), bounded iterations implied by the numbered procedure, output schema the parent branches on. This agent is independently evaluable — feed it queries, assert on `RetrievalOutput` — which is the whole point of the contract pattern.

## Production concerns

- **Latency:** Sub-agent = full LLM call. Don't sub-agent trivial work — a tool call returns in milliseconds; a sub-agent returns in seconds. Rule of thumb: a job needs *multiple tool calls with judgment between them* before it earns sub-agent status.
- **Cost:** Each sub-agent call multiplies token cost — but context isolation can *reduce* total cost: the parent doesn't pay for the sub-agent's reading. The accounting: sub-agent is cheaper when (sub-agent's context noise) × (parent's per-token rate) > (sub-agent's fixed overhead). Run the numbers per workload.
- **Failure modes:** (1) malformed output — structured outputs fix this (`output_type`); (2) *confident garbage* — the sub-agent found wrong sources and returned them well-formatted; only evals catch this (golden-set accuracy per sub-agent, `../07-evals/01-golden-datasets.md`); (3) scope creep at runtime — the agent improvises beyond its job ("I also drafted the report"); instructions + output schema constrain it.
- **Security:** Sub-agent only gets the tools it needs — least privilege. This is also your injection defense topology: the sub-agent that reads untrusted content gets *no* write/send tools, so a successful injection has nothing to take (`02-context-engineering/04-prompt-injection-defense.md`).

## Anti-patterns

- ❌ **Sub-agent with 30 tools.** Split — or add a tool router.
- ❌ **Sub-agent that calls other sub-agents that call back.** Cycles.
- ❌ **Sub-agent without an output schema.** Untestable.
- ❌ **"And" in the job description.** Two jobs, two agents (or one tool).
- ❌ **Sub-agenting trivial work.** Millisecond tool calls don't need second LLM hops.
- ❌ **Free-text failure responses.** Typed failure modes make parents robust; vibes don't.
- ❌ **Frontier models everywhere "for safety."** Tier per error cost; measure the cheap tier before assuming it fails.

## References

- [Anthropic: Building effective agents](https://www.anthropic.com/research/building-effective-agents) — verified 2026-10-20
- [Claude Code sub-agents](https://platform.claude.com/docs/en/claude-code/sub-agents) — verified 2026-10-20
- [OpenAI: Multi-agent systems](https://platform.openai.com/docs/guides/multi-agent) — verified 2026-10-20
