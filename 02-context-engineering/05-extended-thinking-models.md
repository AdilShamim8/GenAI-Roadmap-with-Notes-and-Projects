# Extended Thinking Models

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning), [Anthropic extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)

## Why this matters

Thinking models spend extra tokens "reasoning" before answering — and since 2025, reasoning is no longer a separate product line: it is a dial on almost every frontier model (GPT-5.x/6 thinking tiers, Claude 5.5's always-on thinking with `effort`, Gemini 3.x thinking levels, DeepSeek's thinking modes, open reasoners like Qwen3 and GLM). The engineering questions have shifted from "which model do I pick" to "how much thinking do I buy per call" — a routing problem with a 10–50x cost/latency spread between its extremes.

## Core concepts

### Prompted CoT vs trained CoT — know which you have

"Let's think step by step" (prompted) elicits surface CoT from a base model. Reasoning models are *RL-trained* to generate long internal chains before answering (the DeepSeek-R1 lineage, arXiv 2501.12948; the minimal-recipe counterpoint s1, arXiv 2501.19393, which got strong results from 1K curated examples + budget forcing on a base Qwen). The difference matters operationally:

- Trained thinking is **budget-controllable** (you can cap it) and shows in usage telemetry as its own token class.
- Prompted CoT is billed as ordinary output tokens, can't be capped, and disappears if you remove the phrase — a fragile dependency.
- The s1 result's practical echo: on many mid-complexity tasks, a small set of high-quality examples with strong verification gets you most of the reasoning gain — you don't always need the flagship model, but you do need *some* verification signal (tests, judges, ground truth).

### What thinking tokens actually are

Hidden tokens the model generates before the visible answer. You pay for them as **output tokens** (the expensive class), they're counted in usage telemetry (OpenAI `reasoning_tokens`; Anthropic reports thinking inside output token counts), and on API responses they are separate content blocks you can inspect (Anthropic `thinking` blocks) or summary-only (OpenAI). They are not cacheable as ordinary input across turns on all providers — on Anthropic, thinking blocks from previous turns can be preserved in multi-turn tool use (needed for the model to use its own scratchpad), and caching them follows the prefix rules like any other content.

### The overthinking tax

Reasoning models over-generate on easy tasks: "Do NOT Think That Much for 2+3=?" (arXiv 2412.21187) measured o1-class models burning thousands of tokens on trivial arithmetic — 3x-5x the cost with zero accuracy gain. The fix is never "use a dumber prompt"; it's **routing by task complexity** (below) and **budget caps**. Chain of Draft (arXiv 2502.18600) is the prompting-side counterpoint: constraining the model to ≤5-word reasoning steps per stage cut reasoning tokens ~85% with comparable accuracy on tested tasks — the useful idea is that verbosity of reasoning is partly a style prior, not a necessity.

### The test-time scaling curve — and where it flattens

More thinking helps on verifiable tasks (math, code with tests) roughly log-linearly at first, then flattens; on fuzzy tasks (creative writing, open-ended product judgment) extra thinking mostly buys *different* answers, not *better* ones. The engineering discipline: identify which of your call sites are in the verifiable regime, and spend thinking budget only there — with an eval that proves the spend (accuracy at effort=low vs medium vs high on your golden set, `../07-evals/05-online-vs-offline.md`).

### The thinking budget, per provider

- **OpenAI** — `reasoning_effort` on GPT-5.x/6 thinking models (`low | medium | high`, plus `none` on some tiers for latency-sensitive paths). Reasoning tokens appear in `usage` details.
- **Anthropic** — Claude 5.5 models think by default; the `effort` parameter (low → max) trades thoroughness for cost. Explicit `thinking` budgets (`budget_tokens`, minimum 1024, must be < `max_tokens`) still work for hard caps.
- **Google** — `thinking_config` with a thinking budget on Gemini 3.x, including 0 to disable on models that allow it.
- **Interleaved thinking** — on Claude, thinking blocks appear between tool calls during agentic loops, not just once at the start: the model thinks, calls a tool, reads the result, thinks again. Budget applies across the whole turn — a long tool loop can exhaust the budget mid-loop, truncating later reasoning.

### Thinking in agentic loops — the failure nobody warns you about

An agent that thinks between every tool call multiplies thinking cost by tool-call count. A 10-step loop at 2K thinking tokens/step is 20K output-priced tokens *per user request* before any visible output. Also: thinking content conditioned on untrusted tool output is an injection surface (`04-prompt-injection-defense.md`) — the model reasons *about* attacker text at length, which increases the attacker's influence budget.

## Code: Claude 5.5 with effort control

```python
import anthropic
client = anthropic.Anthropic()

resp = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=16000,
    thinking={"type": "enabled", "budget_tokens": 8000},  # or set effort in 5.5
    messages=[{"role": "user", "content": "Design a rate-limiter for a multi-tenant API. Justify your design."}],
)

for block in resp.content:
    if block.type == "thinking":
        print(f"[thinking: {block.thinking[:80]}...]")
    elif block.type == "text":
        print(block.text)
```

## Code: OpenAI reasoning effort + telemetry

```python
from openai import OpenAI
client = OpenAI()

resp = client.responses.create(
    model="gpt-6.1-sol",
    reasoning={"effort": "medium"},  # low | medium | high
    input="Prove that the sum of two odd numbers is even.",
)
print(resp.output_text)

u = resp.usage
print(f"input={u.input_tokens} output={u.output_tokens} "
      f"reasoning={u.output_tokens_details.reasoning_tokens}")
```

Track that `reasoning` number per route: it's the line item that silently turns a "$0.02 average call" into "$0.50" when a model upgrade flips a default effort level.

## Production concerns

- **Latency:** Thinking adds seconds to minutes before the first visible token. Plan UX around it (stream thinking-status, show a "thinking..." state, or summarize the thinking later). For interactive paths, budget caps are your TTFT control.
- **Cost:** Thinking tokens are billed as output — the 2-5x more expensive class (e.g. GPT-6.1 Sol: $2 in / $10 out per 1M). A high-effort call can cost 10–50x a low-effort one. Route by task complexity and alert on reasoning-token p95 per route.
- **Failure modes:** (1) overthinking trivial tasks — route down or cap; (2) under-thinking hard tasks after someone "optimized" cost — gate with evals; (3) budget exhaustion mid-agentic-loop (above); (4) prompting the model to hide its thinking ("just answer directly") on a trained reasoner — you pay latency anyway and get worse answers.
- **Security:** Thinking traces can contain scraped training data echoes and are an injection amplifier. Never display raw thinking to users; don't parse it for decisions — parse the answer.
- **Model swaps:** Effort semantics differ across providers; a "medium" on one model ≠ "medium" on another. Re-run the effort ladder eval on every model migration (`../08-production/06-model-versioning-migration.md`).

## Anti-patterns

- ❌ **Defaulting to high-effort thinking for every call.** Route by task complexity; measure the accuracy-vs-cost curve per route.
- ❌ **Showing raw thinking to users.** Often confused, includes backtracking, erodes trust — and leaks context.
- ❌ **Disabling thinking for hard tasks because "it's slow."** You get silence or wrong answers faster; use a cheaper model with *appropriate* thinking instead.
- ❌ **Setting budget_tokens ≥ max_tokens.** The thinking budget must leave room for the answer (min 1024, strictly less than max_tokens).
- ❌ **Unbounded thinking inside agent loops.** Multiply budget by tool-call count before approving the design.
- ❌ **Treating "it reasoned for 10K tokens" as evidence of quality.** Length is spend, not accuracy — verify with tests or judges.

## Decision framework

| Task | Model |
|------|-------|
| Simple extraction / classification | GPT-6 Luna / Claude Haiku 5.5 (low effort) / Gemini 3.5 Flash-Lite — thinking off or minimal |
| Coding, math, planning | GPT-6.1 Sol (medium effort) / Claude Sonnet 5.5 / DeepSeek thinking mode |
| Frontier-hard agentic | Claude Opus 5.5 (high effort) / GPT-6 Astra |
| High-volume verifiable tasks (tests exist) | Mid-tier + CoD-style constrained reasoning; verify with the tests |
| Interactive latency-sensitive | Hard budget caps; consider effort=none tiers where offered |

## References

- [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning) — verified 2026-10-20
- [Anthropic extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking) — verified 2026-10-20
- [DeepSeek-R1](https://arxiv.org/abs/2501.12948) — verified 2026-10-20
- [s1: Simple test-time scaling](https://arxiv.org/abs/2501.19393) — verified 2026-10-20
- [Do NOT Think That Much for 2+3=?](https://arxiv.org/abs/2412.21187) — verified 2026-10-20
- [Chain of Draft: Thinking Faster by Writing Less](https://arxiv.org/abs/2502.18600) — verified 2026-10-20
- [Stop Overthinking: A Survey on Efficient Reasoning](https://arxiv.org/abs/2503.16419) — verified 2026-10-20
