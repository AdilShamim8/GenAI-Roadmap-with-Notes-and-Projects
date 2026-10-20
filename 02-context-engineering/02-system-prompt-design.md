# System Prompt Design

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [Claude: system prompts](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/system-prompts), [OpenAI prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering)

## Why this matters

The system prompt is the single highest-leverage piece of context you control. It's cached, it's prepended to every call, and it sets the operating envelope for the model. Yet most system prompts are bloated, contradictory, and untested.

## Core concepts

### The four-part system prompt

A production system prompt should have, in order:

1. **Role** — one sentence. "You are a customer-support agent for Acme Corp."
2. **Policies** — what you must and must not do. Bullet list, ≤10 items.
3. **Tone & format** — voice, length, structure.
4. **Tools available** — names, when to use each.

### Why this order

Models attend most strongly to the **start** and **end** of a context. Role → policies → tone → tools puts the most important (policies) near the start and the most-referenced (tools) near the end.

### Cache-friendly structure

Put the most stable content first (role, policies, tone). Put the most volatile content last (current user, current tool outputs). This maximizes prompt-cache hit rate.

## Code: a template

```python
SYSTEM_PROMPT = '''You are a tier-1 customer-support agent for Acme Corp, a SaaS analytics company.

# Policies
- Never make commitments about refunds exceeding $500; escalate to tier-2.
- Always cite the help-center article you used.
- If the user mentions a security incident, immediately route to the security team via the `escalate_security` tool.
- Do not discuss competitors by name.
- If you don't know, say so. Never fabricate feature names.

# Tone & format
- Friendly, concise, professional.
- Maximum 3 sentences per response unless the user asks for detail.
- Use bullet lists for steps.

# Tools
- `search_help_center(query)`: search Acme's help center.
- `lookup_account(email)`: fetch account details.
- `escalate_security(reason)`: route to security team.
- `escalate_tier2(reason)`: route to tier-2 support.
'''
```

## Production concerns

- **Latency:** A cached system prompt skips most prefill: cache reads bill at ~10% of fresh input (Anthropic 0.1x; OpenAI ~10x-cheaper cached rates).
- **Cost:** Cache it.
- **Failure modes:** Conflicting policies ("be concise" + "explain in detail") produce inconsistent behavior.
- **Security:** System prompts are visible in traces. Don't put secrets in them.

## Anti-patterns

- ❌ **300-line system prompts.** Model attends poorly past ~2K tokens of static instructions.
- ❌ **Prescriptive output formats in the system prompt.** Use structured outputs instead.
- ❌ **Putting examples in the system prompt.** Use a separate `examples` section or few-shot in user turns.

## Decision framework

| Need | Approach |
|------|----------|
| Stable policy across all requests | Long system prompt + prompt caching (`../01-llm-calling/06-prompt-caching.md`) |
| Per-user or per-tenant behavior | Small shared core + dynamic block appended after the cacheable prefix |
| Output must be machine-parseable | Structured outputs (`../01-llm-calling/04-structured-outputs.md`), not format prose |
| Behavior changes between model versions | Version prompts and regression-test them (`../07-evals/01-golden-datasets.md`) |

## References

- [Claude: system prompts](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/system-prompts) — verified 2026-10-20
- [OpenAI prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering) — verified 2026-10-20
