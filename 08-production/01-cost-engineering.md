# Cost Engineering

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [OpenAI pricing](https://developers.openai.com/api/docs/pricing), [Claude pricing](https://platform.claude.com/docs/en/pricing)

## Why this matters

LLM costs scale linearly with usage and quadratically with prompt length (attention). A naive implementation can cost 10–100× more than an optimized one for the same outcome. Cost engineering is the difference between a sustainable product and a budget crisis.

## Core concepts

### The six levers

| Lever | Savings | Effort |
|-------|---------|--------|
| **Prompt caching** | 50–90% on cached input | Trivial |
| **Model routing** | 50–80% on simple queries | Medium |
| **Prompt compression** | 20–40% on long prompts | Medium |
| **Smaller models for sub-tasks** | 60–90% on sub-tasks | Medium |
| **Batch APIs** | 50% on async workloads | Low |
| **Self-hosting steady state** | 70%+ at high volume | High |

### The routing pattern

```mermaid
graph TD
    Q[User query] --> Classifier[Lightweight classifier]
    Classifier -->|Simple| Small[Small model]
    Classifier -->|Complex| Large[Large model]
    Classifier -->|Reasoning| Reasoning[Reasoning model]
    Small --> Out[Response]
    Large --> Out
    Reasoning --> Out
```

A classifier (small fine-tuned model, embedding similarity, or even rules) routes queries by complexity.

### The 2026 price ladder (per 1M tokens, input/output, verified 2026-10-20)

| Tier | OpenAI | Anthropic | Google |
|------|--------|-----------|--------|
| Cheap | GPT-6 Luna $0.10/$0.50 | Haiku 5.5 $0.10/$0.50 (≤100K) | 3.5 Flash-Lite $0.30/$2.50 |
| Balanced | GPT-6.1 Sol $2/$10 | Sonnet 5.5 $2/$10 | 3.8 Flash $0.75/$3.75 |
| Flagship | GPT-6 Astra $10/$50 | Opus 5.5 $4/$20 | 3.1 Pro $2/$12 |

The spread from cheap to flagship is ~100x on output — routing is your single biggest cost lever. Cached input runs ~10x cheaper across all three vendors; Batch APIs are 50% off everywhere. (Source: vendor pricing pages.)

## Code: token budgeting per request

```python
from openai import OpenAI
client = OpenAI()

class BudgetExceeded(Exception): pass

def call_with_budget(messages, model: str, max_input_tokens: int, max_output_tokens: int):
    input_tokens = sum(len(m["content"]) // 4 for m in messages)
    if input_tokens > max_input_tokens:
        raise BudgetExceeded(f"Input {input_tokens} > budget {max_input_tokens}")
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=max_output_tokens,  # NOT max_tokens on GPT-5.x/6
    )
    PRICING = {"gpt-6.1-sol": (2.0, 10.0), "gpt-6-luna": (0.10, 0.50)}
    cost = (input_tokens / 1e6) * PRICING[model][0] + \
           (resp.usage.completion_tokens / 1e6) * PRICING[model][1]
    metrics.gauge("llm.request.cost_usd", cost, tags=[f"model:{model}"])
    return resp, cost
```

## Code: simple classifier routing

```python
from openai import OpenAI
client = OpenAI()

def route(query: str) -> str:
    '''Returns model name based on query complexity.'''
    resp = client.chat.completions.create(
        model="gpt-6-luna",
        messages=[
            {"role": "system", "content": "Classify the query difficulty. Reply with one word: simple, complex, or reasoning."},
            {"role": "user", "content": query},
        ],
        max_completion_tokens=5,
    )
    cls = resp.choices[0].message.content.strip().lower()
    return {"simple": "gpt-6-luna",
            "complex": "gpt-6.1-sol",
            "reasoning": "gpt-6.1-sol"}.get(cls, "gpt-6-luna")
```

## Production concerns

- **Latency:** Routing adds a small call; worth it.
- **Cost:** Track cost per request, per user, per workflow. Alert on anomalies.
- **Failure modes:** Misrouting to small model degrades quality. Watch evals.
- **Security:** Cost telemetry should not log prompt content.

## Anti-patterns

- ❌ **Using one model for everything.** Always route.
- ❌ **No cost dashboards.** You can't optimize what you don't measure.
- ❌ **Ignoring prompt caching.** The lowest-hanging fruit.

## References

- [OpenAI Batch API](https://platform.openai.com/docs/guides/batch) — verified 2026-10-20
- [Anthropic prompt caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) — verified 2026-10-20
- [LiteLLM (proxy + routing)](https://github.com/BerriAI/litellm) — verified 2026-10-20
