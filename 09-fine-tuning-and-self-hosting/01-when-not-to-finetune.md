# When NOT to Fine-Tune

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [Chip Huyen: AI Engineering](https://www.oreilly.com/library/view/ai-engineering/9781098166298/), [LoRA paper](https://arxiv.org/abs/2106.09685)

## Why this matters

The default answer to "should I fine-tune?" is no. Most teams that fine-tune shouldn't have. Fine-tuning is expensive, slows iteration, and rarely beats well-engineered prompting + RAG + structured outputs. This file exists to talk you out of it. The expert framing: fine-tuning changes *model weights* to solve problems that are usually *system* problems (what knowledge is available, what format is required, what behavior is preferred). Weights are the most expensive, slowest-iterating, hardest-to-audit component in your stack — they should be the last lever, not the first.

## The decision matrix

| Symptom | Don't fine-tune. Instead... |
|---------|----------------------------|
| "Model doesn't know X" | Use RAG |
| "Model hallucinates" | RAG + structured outputs + faithfulness evals |
| "Model wrong format" | Structured outputs (JSON schema) |
| "Model too verbose" | Better system prompt; max_tokens |
| "Model can't use our API" | Tools / MCP |
| "Model is too slow" | Route to smaller model |
| "Model is too expensive" | Prompt caching + routing |
| "Model style is off" | Few-shot examples in context |

| Symptom | Fine-tune |
|---------|-----------|
| Latency budget <50ms, can't afford a frontier model | Distill to 7B |
| Domain vocab not in pretraining (medical, legal, internal codenames) | Continued pretraining or LoRA |
| Need consistent output style across millions of calls | Style alignment LoRA |
| Cost: prompt too expensive at scale, can't cache | Smaller fine-tuned model |

### The diagnostic question the table encodes

Each row of the "don't" column maps a symptom to the *cheapest layer* that can fix it: knowledge → retrieval (context), format → decoding constraints, behavior → instructions+examples, cost → routing/caching. Fine-tuning becomes right when the fix genuinely lives in weights: the *knowledge is not retrievable* (it's tacit — style, judgment, pattern — not documents), the *context can't carry it* (your prompt is 8K tokens of few-shots on every call), or the *latency/cost envelope* demands a small model that must match a big model's behavior on a narrow task. If you can name which of those three conditions you're in, fine-tune; if you can't, you're about to spend GPU-weeks moving a system problem into weights.

## The hidden costs

- **Iteration speed:** Each fine-tune run = hours to days. Prompt iteration = minutes. This compounds: a product iterating on prompts weekly ships 50 improvements in the time a fine-tuning team ships 2.
- **Eval burden:** You need evals BEFORE fine-tuning to measure improvement — and evals that detect the *specific* improvement you want, not just general quality (a fine-tune can score better on faithfulness while getting worse at formatting).
- **Maintenance:** Fine-tunes need re-training when base models update — and base models update on the provider's schedule. Every Llama/Qwen point release re-opens the question "do we re-run our pipeline?" A fine-tune is a *fork* of model evolution, and forks require merging.
- **Talent:** Fine-tuning done wrong produces worse-than-base models — a bad LoRA run quietly degrades capabilities your evals don't cover.
- **Lock-in:** A fine-tune ties you to one base model. It's the strongest form of vendor/model lock-in in the stack: your behavioral improvements are hostage to that checkpoint's availability.

## The 2026 reality

One nuance that changed since 2024: if you *do* fine-tune for reasoning, the interesting frontier moved from SFT/LoRA to **RL post-training** (GRPO-style RLVR — reinforcement learning with verifiable rewards). For most product teams the decision matrix below still lands on "don't fine-tune" — but "improve reasoning on a small model" is now an RL problem, not a DPO problem.

Frontier models (GPT-6 family, Claude 5.5, Gemini 3.x) are so strong that 95% of "I should fine-tune" use cases are better served by:

1. Better prompting.
2. RAG.
3. Structured outputs.
4. Few-shot examples.

If you've done all four and the model still fails your evals, then consider fine-tuning.

The reason frontier strength keeps raising the bar: fine-tuning a *smaller* model to match a *frontier* model's behavior is a moving target — you're distilling yesterday's frontier into a model that today's frontier beats anyway. Distillation-based fine-tuning makes sense when the task is *narrow and stable* (classify support tickets, extract entities in your schema) — the narrowness means the small model can win, and the stability means your investment doesn't depreciate with each frontier release. A fine-tune chasing a broad, moving capability is depreciation on wheels.

## Production concerns

- **Latency:** Self-hosted fine-tunes can be faster than API (no network). But a fine-tuned 8B you self-host vs a cached-prefix frontier call — run *that* comparison; caching moved the goalposts (`01-llm-calling/06-prompt-caching.md`).
- **Cost:** Fine-tune cost = compute + storage + serving infra + ops — the full self-hosting stack (`05-breakeven-math.md`), not just the training run.
- **Failure modes:** Catastrophic forgetting (the fine-tune improved X and silently degraded Y — your eval suite's *breadth* is what protects you); over-fitting to eval set (train/test leakage via LLM-generated eval data is the common form).
- **Security:** Fine-tunes on internal data need the same access controls as the data — plus a new one: the adapter weights *memorize* training data; membership-inference and extraction attacks apply to adapters, so treat adapters as data artifacts, not code.

## Anti-patterns

- ❌ **Fine-tuning to add knowledge.** Use RAG — knowledge in weights is expensive to update and impossible to cite.
- ❌ **Fine-tuning without an eval set.** You can't measure improvement.
- ❌ **Fine-tuning a frontier model.** Distill to a smaller one — you pay frontier training rates to keep frontier lock-in.
- ❌ **Fine-tuning to fix a prompt problem.** If you can't name your condition (tacit knowledge / context overflow / latency envelope), it's a system problem.
- ❌ **Fine-tuning toward a moving capability.** Narrow-and-stable tasks only.

## References

- [Chip Huyen: AI Engineering (book)](https://www.oreilly.com/library/view/ai-engineering/9781098166298/) — verified 2026-10-20
- [Fine-tune or not — decision guide in this repo](../docs/decision-guides/fine-tune-or-not.md) — verified 2026-10-20
- [LoRA](https://arxiv.org/abs/2106.09685) — verified 2026-10-20
