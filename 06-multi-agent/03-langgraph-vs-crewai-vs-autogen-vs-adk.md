# LangGraph vs CrewAI vs AutoGen vs Google ADK

> **Level:** ADV · **Last verified:** 2026-10-20

## Why this matters

These are the multi-agent frameworks you'll see in 2026 job postings. Note the big 2025-26 shift: Microsoft retired AutoGen (Oct 2025) in favor of the unified **Microsoft Agent Framework**, and the OpenAI Agents SDK + Claude Agent SDK joined the top of the hiring list (see `../05-agents/`). Each has a distinct philosophy. Picking one is a 6-month commitment; understanding the trade-offs upfront saves rewrites.

## The comparison

| Dimension | LangGraph | CrewAI | AutoGen v0.4+ | Google ADK |
|-----------|-----------|--------|---------------|------------|
| **Philosophy** | Explicit graphs | Role-based crews | Async event-driven | Vertex-native |
| **Abstraction** | State graph | Crew + agents + tasks | Agents + topics | Agents + tools + sessions |
| **State** | Typed, checkpointed | Per-task | Distributed | Session-scoped |
| **Multi-vendor** | Yes | Yes | Yes | Gemini-first |
| **Human-in-loop** | First-class | Add-on | Add-on | First-class |
| **Streaming** | First-class | Limited | First-class | First-class |
| **Maturity** | High | Medium | Moderate (typed Workflow graph) | Medium |
| **Best for** | Production workflows | Rapid prototyping | Async, distributed | Google Cloud shops |

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

- **Latency:** Each framework adds overhead; LangGraph is the leanest.
- **Cost:** All multi-agent frameworks multiply token cost. Budget accordingly.
- **Failure modes:** Framework abstractions hide token usage; instrument your own.
- **Security:** Each framework has different sandboxing stories. Verify.

## Anti-patterns

- ❌ **Starting with CrewAI for production.** Fine for prototypes; rewrite in LangGraph for prod.
- ❌ **Starting new projects on AutoGen.** It stopped active development in Oct 2025; use Microsoft Agent Framework.
- ❌ **Assuming Google ADK is Vertex-only.** It is model-agnostic; judge it on the workflow tooling.

## References

- [LangGraph](https://docs.langchain.com/oss/python/langgraph/) — verified 2026-10-20
- [CrewAI](https://docs.crewai.com/) — verified 2026-10-20
- [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/) — verified 2026-10-20
- [Google ADK](https://google.github.io/adk-docs/) — verified 2026-10-20
