# Changelog

All notable changes to this repository are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [v1.1] — 2026-10-20

Full audit-driven refresh. Every factual claim re-verified against primary sources (see `LAST_VERIFIED.md`); 45 commits, each pushed individually.

### Fixed — fabricated or broken code (P0)

- `agents/02`: both code blocks used a nonexistent Claude Agent SDK API (`Agent()`, `.run()`, `.final_message`); rewritten against the real `query()` / `ClaudeSDKClient` / `create_sdk_mcp_server` surface.
- `realtime-voice/01`: the `conversation.item.interruption` event does not exist; replaced with the real barge-in pair (`speech_started` + `response.cancel`).
- `fine-tuning-and-self-hosting/05`: breakeven example added per-1M input and output prices together (dimensionally invalid) against wrong GPT-5 pricing; recomputed with a correct blended example and the honest open-weight baseline.
- `projects/*` (15 skeletons): `make install` failed for all 15 (`promptfoo>=0.100` is not on PyPI); `make run` and the Docker CMD failed (no `__main__`). Both fixed and verified end-to-end on Project 01.
- Code-level bugs: `handdoff` typo (agents/01), undefined `JudgeOutput`/`EvalScore` schemas (evals), `MemorySaver` missing import (agents/03), FAISS dimension mismatch (agents/06), `min_items` removed in Pydantic v2 (agents/04), pymupdf xref crash (rag/07), critic double-registration in LangGraph (multi-agent/04), Gemini Live auth/field-casing (realtime-voice/02), `hash()` for forensics (safety/05).

### Fixed — false claims about the repo itself

- README badge, CHANGELOG, and CONTRIBUTING referenced CI (markdownlint, lychee, freshness reminder) and issue templates that did not exist; `.github/` is now real.
- Duplicate `LICENSE.md` removed; broken `../prereqs.md` link fixed with a new `docs/prereqs.md`; per-project README trees listed a nonexistent `.gitignore`.

### Changed — currency (2026-07-30 → 2026-10-20)

- Model rosters everywhere: GPT-6 family (Astra/Sol/Luna), GPT-5.6 line, Claude 5.5 family (Opus/Sonnet/Haiku), Gemini 3.x line, DeepSeek V4, o3 sunset.
- Pricing: all cost math recomputed from verified October 2026 rate cards; prompt-caching economics corrected (Anthropic 0.1x reads / 1.25x-2x writes; OpenAI ~10x cached).
- Protocols: MCP pinned to spec revision 2026-07-28 (HTTP+SSE removed, OAuth 2.1, Registry, sampling/elicitation); FastMCP examples; A2A added to handoffs.
- Frameworks: LangChain/LangGraph 1.0; AutoGen → Microsoft Agent Framework; Claude Agent SDK real API; PyRIT 1.x; Ragas 0.2+; graphrag CLI.
- Tooling: vLLM v0.30.x, TGI archived, llama.cpp/garak/presidio/instructor/ragas org moves, MXFP4/NVFP4 quantization, gpt-oss in the open-weight lineup.
- Open-weight selection guide rewritten for the Qwen/DeepSeek/GLM/Kimi/gpt-oss era; salary bands re-based on 2026 data; EU AI Act timeline added.

### Added

- `docs/prereqs.md`; AI Weekly newsletter (closes #1); 2025-26 papers (DeepSeek-R1, Kimi K2, test-time scaling, s1, Building Effective Agents, MCP, A2A); books (Raschka, LLM Engineer's Handbook); courses (CS336); coding-agents and LLM-gateway tool sections; attention-variants (GQA/MLA) and 2025-26 MoE roster; MCP-era failure modes; agent-specific incident response; missing Decision-framework sections across topic files; Sources headers where absent.
- CI: markdownlint-cli2 (blocking) + lychee link-check (advisory) + monthly freshness-reminder issue; content-correction / broken-link / propose-topic issue templates; markdownlint config; root `.gitignore`.

### Verified

- Full-repo markdownlint passes; all internal links resolve; install/test/eval pipeline verified on Project 01 in a clean venv; every new/changed external URL live-checked (bot-blocked domains noted in CI config).

## [v1.0-alpha] — 2026-07-30

### Added

- Initial rebuild from v0.1-legacy.
- 12-rung skill ladder with file-per-topic structure.
- 15 portfolio project skeletons.
- 6 learning paths branched by background.
- 6 decision guides.
- LAST_VERIFIED.md discipline.
- GitHub Actions: link-check, markdownlint, freshness-reminder.
- Per-topic file template enforced via CONTRIBUTING.md.

### Removed

- Hallucinated model names: GPT-5.5, Claude Opus 4.7, Claude Mythos, Project Glasswing, Capybara tier, Gemini 3.1 Pro.
- Hallucinated version numbers: LangChain v1.2.16, LangChain-Core v1.3.2, LangGraph v1.1.10, DeepAgents v0.5.0 alpha.
- Hallucinated events: Interrupt 2026 with Jensen Huang keynote.
- Hallucinated rebrands: LangSmith Fleet, Polly GA.

## [v0.1-legacy] — 2026-05-20

- The pre-rebuild state. Tagged for historical reference only. Do not use.
