# Last Verified

> Every factual claim in this repo must appear in the table below with a source URL and verification date.
> A monthly GitHub Action opens an issue reminding maintainers to re-verify.

## Model & provider facts

| Claim | Source URL | Last verified |
|-------|------------|---------------|
| OpenAI GPT-6 family current: Astra ($10/$1/$50 per 1M in/cached/out), Sol and 6.1 Sol ($2/$10), Luna ($0.10/$0.50), 1.05M-token context | https://developers.openai.com/api/docs/pricing | 2026-10-20 |
| OpenAI GPT-5.6 line still served: Sol ($4/$20, promotional), Terra ($2/$12), Luna ($0.20/$1.20); GPT-5.5 ($5/$30); GPT-5.4 ($2.50/$15); GPT-5.5 Pro ($30/$180) | https://developers.openai.com/api/docs/pricing | 2026-10-20 |
| OpenAI Batch API is 50% off input and output; cached input priced separately per model | https://developers.openai.com/api/docs/pricing | 2026-10-20 |
| OpenAI open-weight models gpt-oss-120b and gpt-oss-20b released August 5, 2025 (Apache-2.0) | https://openai.com/index/introducing-gpt-oss/ | 2026-10-20 |
| OpenAI o-series (o1, o3, o4-mini) superseded within the GPT-5.x/6 thinking lines; o3 sunset in 2025 | https://developers.openai.com/codex/whats-new/ | 2026-10-20 |
| Anthropic Claude Opus 5.5 released September 22, 2026 ($4/$20 per 1M in/out; cache reads $0.20) | https://www.anthropic.com/claude-opus-5-5 | 2026-10-20 |
| Anthropic Claude Sonnet 5.5 released September 28, 2026 ($2/$10; cache reads $0.20; 1M context) | https://www.anthropic.com/claude-sonnet-5-5 | 2026-10-20 |
| Anthropic Claude Haiku 5.5 released October 7, 2026 ($0.10/$0.50 up to 100K tokens, then $0.50/$2.50; effort parameter) | https://www.anthropic.com/claude-haiku-5-5 | 2026-10-20 |
| Anthropic prompt caching: cache writes 1.25x base (5 min) or 2x (1 hour); cache reads 0.1x; Batch API 50% off | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | 2026-10-20 |
| Google Gemini 3.8 Flash ($0.75/$3.75), 3.5 Flash-Lite ($0.30/$2.50), 3.1 Pro Preview ($2/$12; $4/$18 beyond 200K) | https://ai.google.dev/gemini-api/docs/pricing | 2026-10-20 |
| Google limited new-project access to Gemini 2.5 (Sept 18, 2026); directs new projects to 3.5 Flash-Lite / 3.8 Flash | https://ai.google.dev/gemini-api/docs/changelog | 2026-10-20 |
| DeepSeek V4 line (2026): V4-Pro (1.6T, `deepseek-v4-pro`) and V4.1-Flash (`deepseek-flash`); `deepseek-chat`/`deepseek-reasoner` retired 2026-07-24; R2 unreleased as of Oct 2026 | https://api-docs.deepseek.com/updates | 2026-10-20 |
| Meta Llama 4 family (Scout, Maverick; Behemoth preview-only) | https://ai.meta.com/blog/llama-4-multimodal-intelligence/ | 2026-10-20 |
| Open-weight ecosystem (per vLLM model roster, Oct 2026): Qwen 3.5–3.8, GLM-5.x, Kimi K3/K2.x, MiniMax M3, Mistral Small 4 / Large 3 / Medium 3.5, Gemma 4, Nemotron 3 | https://vllm.ai/ | 2026-10-20 |

## Realtime & voice

| Claim | Source URL | Last verified |
|-------|------------|---------------|
| gpt-realtime-2.1: $32/1M audio input ($0.40 cached), $64/1M audio output; text $4/$24; gpt-realtime-2.1-mini: $10/$0.30/$20 | https://developers.openai.com/api/docs/pricing | 2026-10-20 |
| Realtime API supports WebSocket, WebRTC, and SIP/telephony transports | https://developers.openai.com/api/docs/realtime | 2026-10-20 |
| Gemini Live API models and native-audio tradeoffs (AI Studio vs Vertex endpoints) | https://ai.google.dev/gemini-api/docs/live | 2026-10-20 |

## Framework & SDK versions

| Claim | Source URL | Last verified |
|-------|------------|---------------|
| LangChain 1.0, LangGraph 1.0, and langchain-core 1.0 released October 2025 (`create_agent`, middleware, standard content blocks) | https://blog.langchain.com/langchain-langgraph-1dot0/ | 2026-10-20 |
| OpenAI Agents SDK (Python), current stable line | https://github.com/openai/openai-agents-python | 2026-10-20 |
| Anthropic Claude Agent SDK (Python) | https://github.com/anthropics/claude-agent-sdk-python | 2026-10-20 |
| Model Context Protocol spec revision 2026-07-28 (revisions: 2024-11-05 → 2025-03-26 → 2025-06-18 → 2025-11-25 → 2026-07-28); HTTP+SSE transport removed in favor of Streamable HTTP; OAuth 2.1 authorization; MCP Registry | https://modelcontextprotocol.io/specification/2026-07-28/basic/ | 2026-10-20 |
| Microsoft retired AutoGen (Oct 1, 2025) in favor of Microsoft Agent Framework (`pip install agent-framework`) | https://learn.microsoft.com/en-us/agent-framework/ | 2026-10-20 |
| A2A (Agent2Agent) protocol under Linux Foundation governance | https://a2a-protocol.org/ | 2026-10-20 |
| Pydantic AI 1.x stable | https://ai.pydantic.dev/ | 2026-10-20 |
| Instructor (567-labs) | https://github.com/567-labs/instructor | 2026-10-20 |
| CrewAI | https://github.com/crewAIInc/crewAI | 2026-10-20 |
| Google ADK (model-agnostic Agent Development Kit) | https://github.com/google/adk-python | 2026-10-20 |
| LlamaIndex | https://pypi.org/project/llamaindex/ | 2026-10-20 |

## Inference & serving

| Claim | Source URL | Last verified |
|-------|------------|---------------|
| vLLM v0.30.0 (Sept 22, 2026); Python 3.10+ (3.12 recommended) | https://github.com/vllm-project/vllm/releases | 2026-10-20 |
| Hugging Face TGI repository archived (2025); vLLM/SGLang are the maintained OSS paths | https://github.com/huggingface/text-generation-inference | 2026-10-20 |
| SGLang | https://github.com/sgl-project/sglang | 2026-10-20 |
| llama.cpp moved to the ggml-org organization | https://github.com/ggml-org/llama.cpp | 2026-10-20 |
| E2B code sandbox | https://e2b.dev/ | 2026-10-20 |

## Evals & observability

| Claim | Source URL | Last verified |
|-------|------------|---------------|
| promptfoo v0.124.1 (Oct 8, 2026); npm-distributed, includes red-teaming module | https://github.com/promptfoo/promptfoo/releases | 2026-10-20 |
| DeepEval | https://github.com/confident-ai/deepeval | 2026-10-20 |
| Ragas (vibrantlabsai org) | https://github.com/vibrantlabsai/ragas | 2026-10-20 |
| LangSmith | https://docs.smith.langchain.com/ | 2026-10-20 |
| Arize Phoenix | https://github.com/Arize-ai/phoenix | 2026-10-20 |
| Langfuse (open-source LLM observability) | https://langfuse.com/ | 2026-10-20 |
| OpenLLMetry / OpenTelemetry for LLMs | https://github.com/traceloop/openllmetry | 2026-10-20 |

## Safety & governance

| Claim | Source URL | Last verified |
|-------|------------|---------------|
| Garak (NVIDIA org) LLM vulnerability scanner | https://github.com/NVIDIA/garak | 2026-10-20 |
| PyRIT (Microsoft red-teaming) | https://github.com/Azure/PyRIT | 2026-10-20 |
| OWASP Top 10 for LLM Applications, 2025 edition (latest as of Oct 2026) | https://genai.owasp.org/ | 2026-10-20 |
| EU AI Act timeline: in force 2024-08-01; prohibitions 2025-02-02; GPAI obligations 2025-08-02; high-risk obligations phase in from 2026-08-02 | https://artificialintelligenceact.eu/implementation-timeline/ | 2026-10-20 |

## Salary & job market

| Claim | Source URL | Last verified |
|-------|------------|---------------|
| US AI engineer bands 2026: senior base $180-280K / TC $220-350K+; staff base $250-400K+ / TC $350-600K+; frontier labs senior $700K+ TC | https://www.kore1.com/ai-engineer-salary-guide | 2026-10-20 |
| Levels.fyi AI engineer median base ~$211K (Big Tech skew); OpenAI median total comp ~$795K | https://www.levels.fyi/t/software-engineer/focus/ai-engineer | 2026-10-20 |
| Robert Half 2026: AI/ML roles took the largest 2026 starting-salary gains of any tech specialty (+4.1%) | https://www.pin.com/blog/ai-compensation-salary-guide | 2026-10-20 |

## Re-verification protocol

1. Every month, a GitHub Action opens a "Re-verify claims" issue.
2. Maintainers walk through this file, click each source, and update the `Last verified` date.
3. Any claim whose source is dead or contradicted must be fixed in a follow-up PR within 7 days.
4. The `LAST_VERIFIED` badge in the README is updated to the most recent verification date.
