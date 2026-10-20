# Prompt Injection Defense

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [OWASP LLM Top 10 (2025 ed.)](https://genai.owasp.org/), [Prompt Injection papers](https://arxiv.org/abs/2310.12815)

## Why this matters

Prompt injection is the #1 security risk in production GenAI. Any untrusted text that enters the context — retrieved docs, tool outputs, user uploads — can override your system prompt. There is no perfect defense; the goal is layered mitigation.

## Core concepts

### The threat taxonomy

| Type | Example | Vector |
|------|---------|--------|
| **Direct injection** | "Ignore previous instructions and..." | User input |
| **Indirect injection** | Malicious instructions hidden in a retrieved webpage | RAG corpus |
| **Tool-output injection** | Tool returns text containing "system: ..." | Tool result |
| **Multimodal injection** | Instructions embedded in image pixels | Image upload |
| **Token smuggling** | Unicode tricks, zero-width chars | Anywhere |

### The defense stack

No single defense suffices. Layer these:

1. **Input filtering** — strip control characters, normalize unicode, scan for known injection patterns.
2. **Spotlighting / data-marking** — wrap every piece of untrusted content in explicit delimiters (`<untrusted>...</untrusted>`) and tag it as data, never instructions. The standard containment technique.
3. **Classifier-based detection** — a dedicated injection classifier (Prompt Guard–class models, provider moderation endpoints) catches what regex misses; run it on retrieved docs before they enter context.
4. **Output filtering** — block responses that match forbidden patterns (PII exfiltration, code execution).
5. **Privilege separation** — low-privilege agent handles untrusted input; high-privilege agent executes tools, with explicit handoff.
6. **Tool allowlists + capability scoping** — never let the model pick arbitrary tools; constrain to a fixed set per agent state; scope credentials per tool.
7. **Human-in-the-loop** — for destructive or expensive tools, require human approval.
8. **Constitutional patterns** — second model checks the first's output for policy violations before execution.

## Code: a basic input filter

```python
import re, unicodedata

INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"disregard (the )?(above|previous)",
    r"you are now (a |an )?[A-Z]",
    r"<\|system\|>",
    r"\[system\]",
]

def sanitize_input(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)  # normalize homoglyphs
    text = "".join(c for c in text if unicodedata.category(c)[0] != "Cf")  # strip zero-width
    for pat in INJECTION_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            raise ValueError(f"Potential prompt injection detected: pattern {pat}")
    return text
```

## Production concerns

- **Latency:** Filter passes add <10ms.
- **Cost:** Constitutional patterns double LLM calls. Use only for high-risk actions.
- **Failure modes:** Deterministic filters have false positives and false negatives. Treat as defense-in-depth, not a silver bullet.
- **Security:** Audit logs must record every blocked input.

## Anti-patterns

- ❌ **Trusting the model to "ignore instructions in retrieved docs."** It can't reliably.
- ❌ **Allowing arbitrary tool selection.** Always constrain.
- ❌ **Putting untrusted input in the system prompt slot.** Always user role.
- ❌ **Deploying with no injection evals.** Run Garak/PyRIT against your agent in CI (`../10-safety/02-garak-pyrit.md`).

## Decision framework

| Risk surface | Primary defense |
|--------------|-----------------|
| RAG corpus / web content | Spotlighting + classifier scan before indexing or at retrieval time |
| User chat input | Input filter + privilege separation |
| Tool outputs | Output filtering + tool allowlist + scoped credentials |
| Destructive tools | Human approval gate — no exceptions |
| Whole system | Red-team harness in CI + audit logging |

The deeper taxonomy of injection classes lives in `../10-safety/01-prompt-injection-taxonomy.md`.

## References

- [OWASP LLM Top 10 (2025 edition)](https://genai.owasp.org/) — verified 2026-10-20
- [Not what you've signed up for: Compromising Real-World LLM Apps](https://arxiv.org/abs/2302.12173) — verified 2026-10-20
- [Simon Willison: Prompt injection](https://simonwillison.net/series/prompt-injection/) — verified 2026-10-20
