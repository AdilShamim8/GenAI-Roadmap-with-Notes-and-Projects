# Interview Prep — Topic Q&A

> **Last verified:** 2026-10-20

This directory is the **content-side** interview prep: per-topic question banks with model answers, keyed to the ladder's 12 rungs. The *career-side* prep (loop anatomy, take-home strategy, portfolio, salary) lives in [`field-guide/`](../../field-guide/README.md) — use both: this page for what to know, the field guide for how to run the process.

## How to use these files

1. **Answer before reading.** Read the question, say your answer out loud or write it in one paragraph, *then* compare. Passive reading feels like studying; it isn't.
2. **Calibrate depth to level.** Each answer has a "what makes it senior" note — the difference between an acceptable answer and a hire-signal one is usually the trade-off reasoning, not the facts.
3. **Anchor to the notes.** Every Q&A links the rung note with the full detail — if you can't answer the question, that's the note to re-read, not something to memorize from this file.

## The files

| File | Rung | Covers |
|------|------|--------|
| [01-foundations-questions.md](./01-foundations-questions.md) | 00 | Transformers, tokenization, KV cache, MoE, inference arithmetic |
| [02-context-questions.md](./02-context-questions.md) | 02 | Context budgeting, system prompts, distillation, injection, thinking models |
| [03-rag-questions.md](./03-rag-questions.md) | 03 | Chunking, embeddings, hybrid, reranking, GraphRAG, long-context |
| [04-tools-mcp-questions.md](./04-tools-mcp-questions.md) | 04 | Function calling, MCP, computer use, sandboxes |
| [05-agents-questions.md](./05-agents-questions.md) | 05 | SDKs, LangGraph, guardrails, memory |
| [06-multi-agent-questions.md](./06-multi-agent-questions.md) | 06 | Topologies, handoffs, frameworks, sub-agents, long-horizon |
| [07-evals-questions.md](./07-evals-questions.md) | 07 | Golden sets, judges, statistics, online evals |
| [08-production-questions.md](./08-production-questions.md) | 08 | Cost, latency, observability, incidents, migrations |
| [09-finetuning-questions.md](./09-finetuning-questions.md) | 09 | When not to, LoRA/QLoRA/DPO, serving, quantization, breakeven |
| [10-safety-questions.md](./10-safety-questions.md) | 10 | Injection taxonomy, red-teaming, filtering, compliance |
| [11-realtime-questions.md](./11-realtime-questions.md) | 11 | Realtime APIs, VAD, interruption |
| [12-system-design-walkthroughs.md](./12-system-design-walkthroughs.md) | all | Four full system-design walkthroughs with the trade-off script |

Rung 01 (LLM calling) questions are folded into the context and tools files — provider API mechanics are covered where they're used.

## The interview signal hierarchy

What separates candidate levels, consistently, across 2026 AI-engineer loops:

| Level | What their answers look like |
|-------|------------------------------|
| Junior | Names the technique ("we used RAG with pgvector") |
| Mid | Names the technique + why ("hybrid search because product codes need exact match") |
| Senior | Names the technique + why + the trade it made + the number ("hybrid + rerank cut our bad-answer rate 30% but added 300ms p95; we made it a config flag per route") |
| Staff | All of that + what they'd do differently + where the industry is wrong |

Every model answer in these files is written at the senior/staff level on purpose. If a piece of it isn't true of your experience, don't perform it — say "I'd expect X, but I haven't measured it" — calibrated honesty scores better than depth theater, and interviewers probe until they find the edge of your knowledge anyway.
