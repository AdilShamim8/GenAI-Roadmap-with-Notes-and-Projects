# Tools

> Verified 2026-10-20.

## APIs

- [OpenAI Platform](https://developers.openai.com/) — GPT-6 family (Astra / Sol / Luna), GPT-5.6 line, Realtime.
- [Anthropic Console](https://platform.claude.com/) — Claude Opus 5.5, Sonnet 5.5, Haiku 5.5, Fable 5.1.
- [Google AI Studio](https://aistudio.google.com/) — Gemini 3.x line.
- [Together AI](https://www.together.ai/) — Open-weight API.
- [Groq](https://groq.com/) — Fastest inference for open weights.
- [Fireworks](https://fireworks.ai/) — Open-weight API, fine-tunes.

## LLM gateways & routers

- [LiteLLM](https://github.com/BerriAI/litellm) — OpenAI-compatible proxy to 100+ providers; the standard self-hosted gateway (see Project 08).
- [OpenRouter](https://openrouter.ai/) — One API key, every major model; usage-based routing and fallbacks.

## Frameworks

- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
- [Anthropic Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python)
- [LangGraph](https://github.com/langchain-ai/langgraph) — 1.x stable since October 2025.
- [CrewAI](https://github.com/crewAIInc/crewAI)
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) — Successor to AutoGen (retired for active development, Oct 2025); typed workflows + MCP clients.
- [Google ADK](https://github.com/google/adk-python) — Agent Development Kit; model-agnostic.
- [Pydantic AI](https://ai.pydantic.dev/) — 1.x stable.
- [Instructor](https://github.com/567-labs/instructor)
- [LlamaIndex](https://github.com/run-llama/llama_index)
- [Vercel AI SDK](https://ai-sdk.dev/docs/introduction)

## Vector DBs

- [pgvector](https://github.com/pgvector/pgvector)
- [Qdrant](https://qdrant.tech/)
- [Pinecone](https://www.pinecone.io/)
- [Weaviate](https://weaviate.io/)
- [Chroma](https://www.trychroma.com/)
- [LanceDB](https://lancedb.com/)

## Embeddings & Rerankers

- [Cohere Embed 4 + Rerank 3.5](https://cohere.com/)
- [Voyage AI](https://www.voyageai.com/)
- [BGE-M3 + BGE Reranker](https://huggingface.co/BAAI/bge-m3)
- [Qwen Embedding + Reranker series](https://huggingface.co/Qwen) — Open-weight, top of the open MTEB/BTEB boards in 2025-26.
- [Jina v3](https://jina.ai/)

## Evals & Observability

- [promptfoo](https://www.promptfoo.dev/) — v0.124.x; evals plus the red-teaming module.
- [DeepEval](https://github.com/confident-ai/deepeval)
- [Ragas](https://github.com/vibrantlabsai/ragas) — Moved to the vibrantlabsai org.
- [LangSmith](https://smith.langchain.com/)
- [Arize Phoenix](https://github.com/Arize-ai/phoenix)
- [Langfuse](https://langfuse.com/) — Open-source LLM observability; OpenTelemetry-native.
- [OpenLLMetry](https://github.com/traceloop/openllmetry)

## Self-hosting

- [vLLM](https://github.com/vllm-project/vllm) — v0.30.x line.
- [SGLang](https://github.com/sgl-project/sglang)
- [TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM) — NVIDIA-tuned serving for maximum throughput.
- [llama.cpp](https://github.com/ggml-org/llama.cpp) — Moved to the ggml-org org; still the CPU/Mac default.
- [Ollama](https://ollama.com/)
- Hugging Face TGI — archived in 2025; use vLLM or SGLang instead.

## Safety

- [Garak](https://github.com/NVIDIA/garak) — Moved to the NVIDIA org.
- [PyRIT](https://github.com/Azure/PyRIT)
- [Microsoft Presidio](https://github.com/data-privacy-stack/presidio) — Moved to the data-privacy-stack org.

## Sandboxes

- [E2B](https://e2b.dev/)
- [Modal](https://modal.com/)
- [Daytona](https://www.daytona.io/)

## Browser automation

- [Browser-Use](https://github.com/browser-use/browser-use)
- [Stagehand](https://github.com/browserbase/stagehand)
- [Playwright](https://playwright.dev/) — Also the basis of the official Playwright MCP server, the common way to give agents a browser.

## Coding agents

The biggest new tool class of 2025-26 — worth knowing even if you build rather than use them.

- [Claude Code](https://claude.com/claude-code) — Anthropic's terminal coding agent; the Claude Agent SDK is its exposed internals.
- [OpenAI Codex](https://openai.com/codex) — CLI, IDE extension, and cloud agent.
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) — Open-source terminal agent.
