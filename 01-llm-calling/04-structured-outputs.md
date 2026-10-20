# Structured Outputs

> **Level:** BEG · **Last verified:** 2026-10-20 · **Sources:** [OpenAI Structured Outputs](https://developers.openai.com/api/docs/), [Instructor](https://github.com/567-labs/instructor)

## Why this matters

Free-text responses break the moment you try to use them programmatically. Structured outputs turn an LLM into a typed function: input prompt → output JSON conforming to your schema. This is the foundation of reliable tool use, agent state, and evals.

## Core concepts

### Three approaches

1. **JSON mode** — guarantees valid JSON, but not the schema.
2. **Schema-constrained** (OpenAI, Anthropic, Gemini) — the model is constrained to emit JSON matching your JSON Schema at decode time.
3. **Library-wrapped** (Instructor, Pydantic AI) — Pydantic schema → retry loop → typed object.

### What "constrained" actually means

Schema-constrained decoding is not a prompt trick — the provider runs a grammar (a state machine compiled from your schema) alongside the sampler and **masks every token that would step outside it**, so invalid JSON is ungenerable by construction. Two expert-level consequences:

- The failure mode moves, it doesn't disappear: output is always *syntactically* valid, so your residual risk is *semantic* — a well-formed enum choice that's wrong, a confident number where the source said nothing. Evals must check values, not just parseability.
- The same machinery exists self-hosted: vLLM's `guided_json` (xgrammar backend) and llama.cpp grammars (GBNF) give you schema-constrained decode on open weights. Same idea, different knob.

### The choice

| Approach | JSON validity | Residual risk | Cost | Vendor lock-in |
|----------|--------------|---------------|------|----------------|
| JSON mode | ~95% | schema drift | Baseline | None |
| Schema-constrained | 100% by construction | semantic errors | Baseline (+10-30% decode time) | Per-vendor syntax |
| Instructor / Pydantic AI | ~99%+ | retry cost on failure | Retry overhead | Library |

## Code: Pydantic + Instructor (cross-provider)

```python
from pydantic import BaseModel, Field
import instructor
from openai import OpenAI

class Person(BaseModel):
    name: str
    age: int = Field(ge=0, le=150)
    occupation: str

client = instructor.create(OpenAI())

person = client.chat.completions.create(
    model="gpt-6.1-sol",
    response_model=Person,
    messages=[{"role": "user", "content": "Extract: 'Maria, 34, marine biologist'"}],
)
# person is a Person instance, guaranteed.
print(person.name, person.age, person.occupation)
```

## Native schema-constrained (OpenAI)

```python
from openai import OpenAI
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int
    occupation: str

client = OpenAI()
# chat.completions.parse (out of beta) or responses.parse:
resp = client.responses.parse(
    model="gpt-6.1-sol",
    input=[{"role": "user", "content": "Extract: 'Maria, 34, marine biologist'"}],
    text_format=Person,  # schema-constrained decoding
)
person = resp.output_parsed  # Person instance
```

## Production concerns

- **Latency:** Schema-constrained decoding adds 10-30% to decode time (the grammar mask runs per token).
- **Cost:** Retries (Instructor) double cost on failure. Use schema-constrained native APIs when available.
- **Schema design *is* prompting.** Under constrained decoding, `Field(description=...)` text is the only signal the model gets about what a field means — write descriptions like prompts, use `Literal`/enums for classification targets, and bound strings (`max_length`) and numbers (`ge`/`le`). An undescribed field gets a plausible-looking invention.
- **Optional fields backfire.** The grammar forces the model to emit every field, so a field you marked optional still gets filled — with a hallucinated value if the source is silent. Prefer required + a `null`-able sentinel the model can justify, and design the schema so "not present in source" is an expressible answer.
- **Failure modes:** Models will sometimes hallucinate fields not in your schema; Pydantic strips them but logs should flag this. Validity is guaranteed; correctness is not — evals assert values.
- **Security:** Validate every field post-parse. Never trust LLM-generated IDs, dates, or monetary amounts without range checks.

## Anti-patterns

- ❌ **Asking the model to "respond in JSON" without a schema.** ~5% of responses will be invalid.
- ❌ **Using regex to parse LLM output.** Use a schema.
- ❌ **Huge nested schemas.** Models degrade past ~20 fields. Split into multiple calls.
- ❌ **Unsupported JSON-Schema keywords.** Native constrained decoding rejects some keywords (`$ref`/`$defs` limits vary by provider) — keep schemas flat and explicit; Pydantic `model_json_schema()` output is a safe baseline.

## Decision framework

| Need | Use |
|------|-----|
| One vendor, max reliability | Native schema-constrained API |
| Multi-vendor portability | Instructor + Pydantic |
| Streaming partial JSON | OpenAI `delta` parsing or `partial_json` lib |

## References

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) — verified 2026-10-20
- [Instructor](https://github.com/567-labs/instructor) — verified 2026-10-20
- [Pydantic AI](https://ai.pydantic.dev/) — verified 2026-10-20
