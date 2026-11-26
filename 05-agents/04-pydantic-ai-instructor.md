# Pydantic AI & Instructor

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [Instructor](https://github.com/567-labs/instructor), [Pydantic AI](https://ai.pydantic.dev/)

## Why this matters

Not every agent needs a full framework. If you want type-safe structured outputs with minimal abstraction, Pydantic AI (from the Pydantic team) and Instructor (from jxnl) are the lightest-weight options. They're ideal for: extraction pipelines, classification, deterministic single-turn tools. The expert position: these libraries are where *most LLM features should live*. The agent-loop frameworks get the attention, but the majority of production LLM calls are single-turn with a schema — and for those, a thin typed layer beats a framework every time: less to audit, less to break, easier to test.

## Core concepts

### The design distinction (choose by shape of problem)

- **Instructor** — a *patch* over any OpenAI-compatible client that swaps text responses for Pydantic-validated objects. It adds: schema→JSON-schema conversion, retry-on-validation-failure, and streaming partial objects. No loop, no tools, no state. It is a function-call type-checker.
- **Pydantic AI** — a thin *agent* framework (1.x stable since late 2025) built around: type-safe inputs and outputs, dependency injection (pass DB connections, etc.), multi-provider support, and evals hooks + Logfire observability. It has an agent loop and tools — but the loop stays visible and small.

The dividing line: does your call need to *decide* (loop: call tool, look, decide again)? Then you need loop semantics — Pydantic AI minimal, or a full SDK if it grows. Is it *extract/transform/classify* (one shot, one schema)? Instructor (or raw provider structured outputs). Misplacing a problem on this line is how teams end up running a 5-agent framework for what is a typed function call — or hand-rolling retry loops for what Instructor already solved.

### The validation-retry loop (the part worth understanding)

Instructor's signature move: on `ValidationError`, it re-sends the request with the error message appended, letting the model correct itself. This is a *conversation* with the schema, and its properties matter:

- **It converges fast on syntax, slow on semantics.** Wrong enum value or missing field: usually fixed in one retry. "Confidence: 0.9 but reasoning contradicts it": retries don't help — that's a schema-design or eval problem (`01-llm-calling/04-structured-outputs.md`).
- **Each retry is a full API call** — cost multiplies by failure rate. At 5% invalid-first-try with 1 avg retry, that's 1.05x; at 30% (bad schema), 1.3x plus latency. Monitor the retry rate: it's a schema-quality signal, and a budget leak.
- **Native constrained decoding makes most retries unnecessary.** With `strict` mode (OpenAI) or guided JSON (vLLM), invalid JSON is ungenerable — Instructor's retries then only catch *semantic* violations (your Field constraints, not syntax). Use both: constrained decoding for syntax, Instructor for semantic validation.

### Schema design is prompt design

The Pydantic model is the prompt. What you require, describe, and constrain *is* the instruction the model optimizes for:

- **Field names and descriptions carry semantics.** `risk_level: Literal["low","medium","high"]` with `Field(description="Probability the customer churns within 90 days")` outperforms paragraphs of prompt prose asking for "a risk assessment."
- **Constraints are the cheapest quality lever.** `ge`/`le` bounds, `min_length`, enums over free strings, `Optional` only where truly optional. Every unconstrained field is a place the model can wander.
- **Nested depth costs accuracy.** Deeply nested schemas multiply the ways a response can be *valid but wrong*. Two sequential calls with shallow schemas beat one call with a 4-level tree — and are independently retryable.
- **Beware "fields the model can't know."** If you require `confidence: float` on a task where the model has no calibration, you get theater. Prefer derivable fields; require uncertainty as `reasoning: str` if you need it at all.

### Dependency injection (Pydantic AI's quiet superpower)

`RunContext` gives tools typed access to injected dependencies — DB pools, config, request-scoped user identity — without globals. In practice this is what keeps thin agents *testable*: unit tests inject fakes, prod injects real clients; the agent code never knows. It's the difference between a framework that scales to a team and one that becomes a monolith of closures.

## Code: Instructor

```python
import instructor
from pydantic import BaseModel, Field
from openai import OpenAI

class Recipe(BaseModel):
    name: str
    ingredients: list[str] = Field(min_length=1)
    steps: list[str] = Field(min_length=1)

client = instructor.create(OpenAI())

recipe = client.chat.completions.create(
    model="gpt-6.1-sol",
    response_model=Recipe,
    messages=[{"role": "user", "content": "Give me a recipe for carbonara."}],
)
# recipe is a Recipe instance, validated.
```

## Code: Pydantic AI agent

```python
from pydantic_ai import Agent, RunContext
from typing import Literal
from pydantic import BaseModel

class Output(BaseModel):
    summary: str
    sentiment: Literal["positive", "neutral", "negative"]  # enum > free string

agent = Agent("openai:gpt-6.1-sol", output_type=Output, system_prompt="You analyze reviews.")

@agent.tool
def lookup_order(ctx: RunContext[None], order_id: str) -> dict:
    '''Look up an order by ID.'''
    return {"order_id": order_id, "total": 49.99}

result = agent.run_sync("Summarize review for order 12345.")
print(result.output.summary, result.output.sentiment)
```

## Production concerns

- **Latency:** Minimal overhead vs raw API calls (Instructor adds nothing but retries; Pydantic AI adds one loop layer). Retry latency is the tail risk: budget for (1 + retry_rate) × base latency.
- **Cost:** Retries (Instructor) can double cost on validation failures. Use native structured outputs where available, then Instructor retries only catch semantics. Track retry rate per schema — it's both a quality and cost metric.
- **Failure modes:** (1) hallucinated-but-valid fields — passes your schema, wrong content; only evals catch this (`../07-evals/`); (2) silent field-stripping — Pydantic drops extra fields by default; log `model_fields_set` vs schema to see what the model tried to add (a prompt-signal); (3) schema drift — the provider's response changed shape after a model swap; your types catch it (good) but the run breaks (have a fallback).
- **Security:** Validate ranges (`Field` constraints) — never trust LLM-generated numbers unchecked, especially anything that flows into pricing, permissions, or SQL. Treat extracted fields as untrusted input to the *next* stage, not as verified facts.

## Anti-patterns

- ❌ **Using Instructor when the provider supports native structured outputs.** Use native (constrained decoding), layer Instructor for semantic validation.
- ❌ **Huge nested schemas.** Split into multiple calls.
- ❌ **Skipping Field constraints.** Always set `ge`, `le`, `min_length`, etc.
- ❌ **Reaching for an agent framework on extract/classify workloads.** A typed single-call with Instructor is cheaper to build, run, and audit.
- ❌ **Optional fields without a plan.** "Everything optional" means "nothing enforced" — the model learns your schema doesn't mean it.
- ❌ **Globals for tool dependencies.** Use RunContext injection; keep the agent testable.

## Decision framework

| Need | Use |
|------|-----|
| Structured output only, any provider | Instructor (with native structured-output mode where available) |
| Lightweight agent with tools + typed outputs | Pydantic AI |
| Full agent loop, handoffs, guardrails, tracing | OpenAI Agents SDK (`01-openai-agents-sdk.md`) |
| Deeper comparison | `../docs/decision-guides/choosing-an-agent-sdk.md` |

## References

- [Instructor](https://github.com/567-labs/instructor) — verified 2026-10-20
- [Pydantic AI](https://ai.pydantic.dev/) — verified 2026-10-20
