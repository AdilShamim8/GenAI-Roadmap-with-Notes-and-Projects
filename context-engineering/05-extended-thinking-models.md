# Extended Thinking Models

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning), [Anthropic extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)

## Why this matters

Thinking models spend extra tokens "reasoning" before answering — and since 2025, reasoning is no longer a separate product line: it is a dial on almost every frontier model (GPT-5.x/6 thinking tiers, Claude 5.5's always-on thinking with `effort`, Gemini 3.x thinking levels, DeepSeek's thinking modes, open reasoners like Qwen3 and GLM). They're dramatically better at multi-step reasoning, math, coding, and agentic tasks — and dramatically more expensive per call if used wrong.

## Core concepts

### How they work

The model generates hidden "thinking" tokens that aren't shown to the user but inform the final answer. You pay for these tokens.

### When they win

- Multi-step math or logic.
- Coding tasks with non-trivial debugging.
- Agent planning (when to call which tool).
- Anything where you'd previously say "let me think step by step".

### When they lose

- Simple classification or extraction (use a smaller model).
- Creative writing (no benefit, more cost).
- High-throughput, low-latency UX (thinking takes time).

### The thinking budget

- **OpenAI** — `reasoning_effort` on GPT-5.x/6 thinking models (`low | medium | high`, plus `none` on some tiers for latency-sensitive paths).
- **Anthropic** — Claude 5.5 models think by default; the `effort` parameter (low → max) trades thoroughness for cost. Explicit `thinking` budgets (`budget_tokens`, minimum 1024, must be < `max_tokens`) still work for hard caps.
- **Google** — `thinking_config` with a thinking budget on Gemini 3.x.
- **Interleaved thinking** — on Claude, thinking blocks appear between tool calls during agentic loops, not just once at the start.

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

## Code: OpenAI reasoning effort

```python
from openai import OpenAI
client = OpenAI()

resp = client.responses.create(
    model="gpt-6.1-sol",
    reasoning={"effort": "medium"},  # low | medium | high
    input="Prove that the sum of two odd numbers is even.",
)
print(resp.output_text)
```

## Production concerns

- **Latency:** Thinking models add 5–60s to TTFT. Plan UX around it (show a "thinking..." state).
- **Cost:** Thinking tokens are billed as output. A max-effort call can cost 10–50x a cheap-tier call. Track thinking-token spend per route.
- **Failure modes:** Over-using reasoning models for trivial tasks burns budget.
- **Security:** Thinking content can leak training data or be manipulated by prompt injection — never display raw thinking to users.

## Anti-patterns

- ❌ **Defaulting to high-effort thinking for every call.** Route by task complexity.
- ❌ **Showing raw thinking to users.** It's often confused, includes backtracking, and erodes trust.
- ❌ **Disabling thinking for hard tasks because "it's slow."** Use a smaller model instead.
- ❌ **Setting budget_tokens ≥ max_tokens.** The thinking budget must leave room for the answer (min 1024, strictly less than max_tokens).

## Decision framework

| Task | Model |
|------|-------|
| Simple extraction / classification | GPT-6 Luna / Claude Haiku 5.5 (low effort) / Gemini 3.5 Flash-Lite |
| Coding, math, planning | GPT-6.1 Sol (medium effort) / Claude Sonnet 5.5 / DeepSeek thinking mode |
| Frontier-hard agentic | Claude Opus 5.5 (high effort) / GPT-6 Astra |

## References

- [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning) — verified 2026-10-20
- [Anthropic extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking) — verified 2026-10-20
- [DeepSeek R1](https://github.com/deepseek-ai/DeepSeek-R1) — verified 2026-10-20
