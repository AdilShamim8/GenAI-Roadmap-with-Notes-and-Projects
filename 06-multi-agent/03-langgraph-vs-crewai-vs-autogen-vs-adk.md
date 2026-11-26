# LangGraph vs CrewAI vs AutoGen vs Google ADK

> **Level:** ADV · **Last verified:** 2026-10-20

## Why this matters

These are the multi-agent frameworks you'll see in 2026 job postings. Note the big 2025-26 shift: Microsoft retired AutoGen (Oct 2025) in favor of the unified **Microsoft Agent Framework**, and the OpenAI Agents SDK + Claude Agent SDK joined the top of the hiring list (see `../05-agents/`). Each has a distinct philosophy. Picking one is a 6-month commitment; understanding the trade-offs upfront saves rewrites. The expert lens for comparing frameworks: look at where each puts **control flow** (code vs prompts), how it treats **state** (explicit vs ambient), and what **failure mode** its abstraction makes easy — those three predict your experience better than any feature matrix.

## The comparison

| Dimension | LangGraph | CrewAI | Microsoft Agent Framework | Google ADK |
|-----------|-----------|--------|---------------------------|------------|
| **Philosophy** | Explicit graphs | Role-based crews | Async event-driven | Vertex-native |
| **Abstraction** | State graph | Crew + agents + tasks | Agents + topics/workflows | Agents + tools + sessions |
| **Control flow lives** | Your code (edges) | Framework (task sequence) | Your code (workflow graph) | Framework + code callbacks |
| **State** | Typed, checkpointed | Per-task | Distributed | Session-scoped |
| **Multi-vendor** | Yes | Yes | Yes | Gemini-first |
| **Human-in-loop** | First-class | Add-on | First-class | First-class |
| **Streaming** | First-class | Limited | First-class | First-class |
| **Maturity** | High | Medium | Growing (AutoGen successor) | Medium |
| **Best for** | Production workflows | Rapid prototyping | Async, distributed, Azure shops | Google Cloud shops |

## The philosophy layer (what the table can't say)

- **LangGraph — "the graph is the product."** Control flow is *your* code: edges are Python functions on state. You can unit-test routing without an LLM, and every branch is visible in the source. The cost: you write the plumbing. Choose when the workflow itself is the product and must be exact, auditable, and durable. The "verbose" complaint is real but is the flip side of "explicit."
- **CrewAI — "roles are the product."** You describe *who* works on *what* (role, goal, backstory per agent; tasks in sequence), and the framework choreographs. Fastest 0-to-demo of any framework — and the control you give up is exactly the control production eventually demands (its task sequencing is convention-driven; debugging "why did the crew do that" is interpretive work). Use for prototypes, pilots, internal tools where iteration speed > rigor.
- **Microsoft Agent Framework — "distribution is the product."** The AutoGen successor keeps AutoGen's async, actor-model DNA (agents communicating over a runtime) and adds the typed Workflow graph — the best of event-driven + explicit orchestration, plus first-class Azure wiring. Choose when you're invested in the MS stack or genuinely need distributed multi-process agents. The event model is more to learn than a graph; it pays off at distributed scale, not before.
- **Google ADK — "the platform is the product."** Model-agnostic but best-in-class when you want Gemini + Vertex ecosystems: managed sessions, evaluation tooling, deployment paths are the draw. The framework itself is competent; the moat is the surrounding platform. Choose when Google Cloud is your home and you want the hosted agent lifecycle end-to-end.

### The graveyard factor (choosing for longevity)

Framework risk is a real selection criterion in a fast-moving field: AutoGen's 2025 retirement stranded projects on an unmaintained core (its GitHub now points to the successor). Mitigations regardless of choice: keep your *domain logic* framework-free (tools, prompts, schemas as plain Python); treat the framework as the orchestration shell you can replace; pin versions and read the roadmap before committing. A team that keeps 90% of its code framework-agnostic can migrate orchestration shells in weeks, not months.

## When to pick what

- **LangGraph** — you need durable, checkpointed, stateful workflows with conditional logic. The default for production.
- **CrewAI** — you want to ship a multi-agent demo in an afternoon and don't need fine control.
- **Microsoft Agent Framework** — the AutoGen successor (AutoGen stopped active development Oct 2025); typed graph workflows, MCP clients, Responses API support.
- **Google ADK** — model-agnostic (not Vertex-only); strong if you want Google's hosted agent tooling.

## Code: same task, three frameworks (LangGraph + CrewAI + Agent Framework)

### LangGraph (supervisor, condensed — full version in `01-orchestration-topologies.md`)

```python
# LangGraph multi-agent = a StateGraph whose nodes are agents
# and whose edges are the handoff policy. Durable by default.
from langgraph.graph import StateGraph, START, END
# ... build supervisor/worker nodes as in 01-orchestration-topologies.md
```

### CrewAI

```python
from crewai import Agent, Task, Crew

researcher = Agent(role="Researcher", goal="Find sources", backstory="...", llm="openai/gpt-6.1-sol")
writer = Agent(role="Writer", goal="Write report", backstory="...", llm="openai/gpt-6.1-sol")

crew = Crew(agents=[researcher, writer], tasks=[
    Task(description="Research {topic}", agent=researcher),
    Task(description="Write a 1-page report based on research", agent=writer),
])
result = crew.kickoff(inputs={"topic": "MoE architectures"})
```

### Microsoft Agent Framework (successor to AutoGen)

```python
from agent_framework import Agent
from agent_framework.openai import OpenAIChatCompletionClient

client = OpenAIChatCompletionClient(model="gpt-6.1-sol")
researcher = Agent(name="researcher", client=client,
                   instructions="Research the topic.")
writer = Agent(name="writer", client=client,
               instructions="Write a 1-page report.")

result = await researcher.run("MoE architectures")
result = await writer.run(result.text)
```

## Production concerns

- **Latency:** Each framework adds overhead; LangGraph is the leanest. But LLM calls dominate — framework overhead is noise next to a single unnecessary agent hop. Optimize topology first (`01-orchestration-topologies.md`).
- **Cost:** All multi-agent frameworks multiply token cost. Budget accordingly — and note the *attribution* problem: frameworks differ in how well they expose per-agent, per-run token accounting. If your framework can't tell you which agent burned the budget, you'll build that instrumentation yourself.
- **Failure modes:** Framework abstractions hide token usage; instrument your own. Hidden control flow is the deeper risk: when the framework decides sequencing (CrewAI especially), a run's behavior is a function of framework version + prompts — pin both, eval both (`../07-evals/`).
- **Security:** Each framework has different sandboxing stories. Verify — tool execution ultimately runs in *your* process with *your* credentials regardless of framework promises; the framework's permission hooks are conveniences, not boundaries (`05-agents/05-guardrails-retries-fallbacks.md`).

## Anti-patterns

- ❌ **Starting with CrewAI for production.** Fine for prototypes; rewrite in LangGraph for prod — or keep CrewAI but add evals and explicit state.
- ❌ **Starting new projects on AutoGen.** It stopped active development in Oct 2025; use Microsoft Agent Framework.
- ❌ **Assuming Google ADK is Vertex-only.** It is model-agnostic; judge it on the workflow tooling.
- ❌ **Letting framework idioms swallow your domain logic.** Tools, schemas, and prompts stay plain Python; the framework is a replaceable shell.
- ❌ **Comparing by feature matrix alone.** Control-flow location and state visibility predict your production experience.

## References

- [LangGraph](https://docs.langchain.com/oss/python/langgraph/) — verified 2026-10-20
- [CrewAI](https://docs.crewai.com/) — verified 2026-10-20
- [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/) — verified 2026-10-20
- [Google ADK](https://google.github.io/adk-docs/) — verified 2026-10-20
