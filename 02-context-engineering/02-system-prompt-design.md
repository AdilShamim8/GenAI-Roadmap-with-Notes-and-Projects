# System Prompt Design

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [Claude: system prompts](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/system-prompts), [OpenAI prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering)

## Why this matters

The system prompt is the single highest-leverage piece of context you control. It's cached, it's prepended to every call, and it sets the operating envelope for the model. Yet most production system prompts are bloated, contradictory, and untested — and every failure mode shows up intermittently, which makes it look like a model problem instead of a prompt problem.

## Core concepts

### The four-part system prompt

A production system prompt should have, in order:

1. **Role** — one sentence. "You are a tier-1 customer-support agent for Acme Corp, a SaaS analytics company." Role anchoring works because it narrows the distribution the model samples from; specificity beats personality ("you are a helpful assistant" does nothing).
2. **Policies** — what you must and must not do. Bullet list, ≤10 items, each testable.
3. **Tone & format** — voice, length, structure.
4. **Tools available** — names, when to use each. (On structured APIs, tool schemas are serialized into the prompt — the prose here is *when/why*, the schema is *what*.)

### Why this order

Models attend most strongly to the **start** and **end** of a context (primacy/recency — Lost in the Middle, arXiv 2307.03172). Role → policies → tone → tools puts the most important (policies) near the start and the most-referenced (tools) near the end. The attention-sink effect (arXiv 2309.17453) gives the first tokens outsized weight — never waste position 1 on boilerplate.

### Instruction-following is probabilistic, not enforced

The model doesn't "obey" your system prompt; it conditions on it. Consequences experts internalize:

- Two conflicting policies ("be concise" + "explain each step in detail") produce **bimodal output** — the model flips between them across calls. Fix by resolving the conflict, not by adding a third instruction saying "don't be contradictory."
- Negative instructions ("never mention X") are weaker than positive reframes ("only discuss Acme products"). You've raised X's salience by naming it.
- Instruction strength decays with context length. A 5-line policy at position 0 of a 100K-token conversation is not the same policy by turn 40. Re-anchor critical rules near the working end of long sessions (platform compaction and re-statement patterns in `03-context-distillation.md`).
- "≤10 policies" isn't aesthetic: every policy competes in the same softmax attention pool, and eval-measured compliance drops as instruction count grows. If you need 30 rules, you need either a policy document the agent retrieves from (RAG for your own rules), or a redesign.

### Cache-friendly structure

Put the most stable content first (role, policies, tone); most volatile last (current user, current tool outputs). This isn't style advice — prompt caches match a **prefix-exact token sequence** (`01-llm-calling/06-prompt-caching.md`). Every volatile token in the middle kills caching for everything after it. Structurally: `[static core] → [per-tenant block] → [per-request block]`, with the cache breakpoint placed between core and tenant.

### Structured outputs replace format prose

Don't prescribe JSON in prose ("respond with a JSON object with keys..."). Constrained decoding makes syntactic compliance *guaranteed* by masking invalid tokens (`01-llm-calling/04-structured-outputs.md`). Prose format instructions spend attention budget on what the API can enforce for free.

## Code: a template

```python
SYSTEM_PROMPT = '''You are a tier-1 customer-support agent for Acme Corp, a SaaS analytics company.

# Policies
- Refunds over $500: state you will escalate to tier-2, then call `escalate_tier2`.
- Cite the help-center article ID for every factual claim about Acme features.
- Security-incident mentions (breach, stolen credentials, ransomware): call `escalate_security` immediately, before any other reply content.
- If unsure about a feature, say so. Do not invent feature names.
- Do not discuss competitor products.

# Tone & format
- Concise: 3 sentences max unless the user asks for detail.
- Steps as bullet lists.

# Tools
- `search_help_center(query)`: search Acme's help center. Use for any product question.
- `lookup_account(email)`: fetch account details. Use before discussing the user's plan.
- `escalate_security(reason)`: route to security team. Highest priority tool.
- `escalate_tier2(reason)`: route to tier-2 support.
'''
```

Note the design choices: policies are phrased as *trigger → action* pairs (testable one by one in an eval); the escalation rule has an explicit priority ordering; the refund rule encodes the dollar threshold the policy team actually set. Every line here can become a golden test case (`../07-evals/01-golden-datasets.md`).

## Production concerns

- **Latency:** A cached system prompt skips most prefill: cache reads bill at ~10% of fresh input (Anthropic 0.1x; OpenAI ~10x-cheaper cached rates).
- **Cost:** The system prompt is paid on every call — it's the most-read text in your system. An unneeded 2K tokens at $2/1M input on 1M calls/day = $4/day *uncached*; the same prompt cached costs ~$0.40. Small prompt, huge multiplier.
- **Failure modes:** (1) Instruction conflicts → bimodal behavior; (2) policy drift at depth — compliance decays as conversation grows; (3) silent edits — two teams editing the same system prompt without versioning produce "the model got worse" mysteries. Version prompts like code (`../08-production/06-model-versioning-migration.md`).
- **Security:** System prompts are visible in traces and extractable via prompt injection — treat them as public-by-default. Never place secrets, credentials, or API keys in them. Assume an attacker will read yours and design policies that survive that.
- **Testability:** A system prompt change is a behavioral deployment. Gate it behind the same eval suite as a model swap, not a text edit.

## Anti-patterns

- ❌ **300-line system prompts.** Attention dilution + cache-unfriendly + untestable. Move stable domain knowledge into retrieval.
- ❌ **Prescriptive output formats in prose.** Use structured outputs — the constraint is enforced by the decoder, not hoped for.
- ❌ **Conflicting policies left in place.** "Be brief" + "explain thoroughly" = coin-flip behavior across calls.
- ❌ **Naming what you forbid in vague terms.** "Never do anything harmful" is untestable; "call `escalate_security` on breach/stolen-credential/ransomware mentions" is a test case.
- ❌ **Examples in the system prompt.** Few-shot examples belong in a stable block (cacheable) or user turns — and watch them: they steer output format more strongly than your prose rules.

## Decision framework

| Need | Approach |
|------|----------|
| Stable policy across all requests | Long system prompt + prompt caching (`../01-llm-calling/06-prompt-caching.md`) |
| Per-user or per-tenant behavior | Small shared core + dynamic block appended after the cacheable prefix |
| Output must be machine-parseable | Structured outputs (`../01-llm-calling/04-structured-outputs.md`), not format prose |
| 30+ policies | Stop growing the prompt: policy-RAG (agent retrieves applicable rules) or split agents |
| Behavior changes between model versions | Version prompts and regression-test them (`../07-evals/01-golden-datasets.md`) |

## References

- [Claude: system prompts](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/system-prompts) — verified 2026-10-20
- [OpenAI prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering) — verified 2026-10-20
- [Lost in the Middle](https://arxiv.org/abs/2307.03172) — verified 2026-10-20
- [Efficient Streaming Language Models with Attention Sinks](https://arxiv.org/abs/2309.17453) — verified 2026-10-20
