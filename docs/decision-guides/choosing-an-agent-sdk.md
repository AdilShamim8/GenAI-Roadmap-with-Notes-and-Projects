# Choosing an Agent SDK

> **Last verified:** 2026-10-20

## The decision

You're building an agent. Which framework do you reach for?

## The candidates

| SDK | Vendor | Best for | Watch out for |
|-----|--------|----------|---------------|
| OpenAI Agents SDK | OpenAI | Fastest path to a working agent; handoffs, guardrails, tracing | Model-agnostic via custom clients/LiteLLM |
| Anthropic Claude Agent SDK | Anthropic | Long-horizon agents, computer use, file sandboxing | Anthropic-only |
| LangGraph | LangChain | Stateful multi-agent graphs, complex orchestration | Steeper learning curve |
| CrewAI | CrewAI | Role-based multi-agent, rapid prototyping | Less control over execution |
| Microsoft Agent Framework | Microsoft | AutoGen's successor (Oct 2025): typed workflows, MCP clients, Responses API | Younger ecosystem |
| Google ADK | Google | Model-agnostic agent toolkit + hosted tooling | Google-tooling gravity |
| Pydantic AI | Pydantic | Type-safe structured outputs, minimal abstraction | Less out-of-the-box agent logic |
| Instructor | jxnl | Pure structured output extraction | Not an agent framework |
| LlamaIndex | LlamaIndex | RAG-first; agents as a secondary concern | Less polished for pure-agent work |
| Mastra | Mastra | TypeScript-native, Vercel-style | TS-only |
| Vercel AI SDK | Vercel | Streaming UIs in Next.js | TS-only, less backend depth |

## The decision tree

```mermaid
graph TD
    A[Need an agent framework?] -->|No, just structured output| B[Instructor or Pydantic AI]
    A -->|Yes| C{Single vendor?}
    C -->|OpenAI| D[OpenAI Agents SDK]
    C -->|Anthropic| E[Claude Agent SDK]
    C -->|Multi-vendor| F{Need stateful multi-agent graphs?}
    F -->|Yes| G[LangGraph]
    F -->|No| H{Team preference?}
    H -->|Python, simple| I[CrewAI]
    H -->|Python, type-safe| J[Pydantic AI]
    H -->|TypeScript| K[Mastra or Vercel AI SDK]
```

## Default recommendation

If you don't know, ask first whether you need a framework at all — a plain agent loop over your provider SDK is ~50 lines and zero magic, and senior interviewers increasingly respect that answer. When you do want one: **OpenAI Agents SDK** (Python) for greenfield single/multi-agent work in 2026 — the simplest path to production. Switch to **LangGraph** when you need durable, multi-agent state machines. Also consider Hugging Face **smolagents** and **Agno** if you want lightweight, code-first agents; per-SDK notes live in `../../agents/` and the framework comparison in `../../multi-agent/03-langgraph-vs-crewai-vs-autogen-vs-adk.md`.

## References

- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) — verified 2026-10-20
- [Anthropic Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) — verified 2026-10-20
- [LangGraph](https://github.com/langchain-ai/langgraph) — verified 2026-10-20
