# promptfoo

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [promptfoo docs](https://www.promptfoo.dev/docs/intro/), [promptfoo releases](https://github.com/promptfoo/promptfoo/releases)

## Why this matters

promptfoo is the easiest way to start with evals. YAML config, runs in CLI or CI, supports all major providers, has built-in LLM-as-judge. If you're not doing evals yet, start here this week. The expert reading of its design: promptfoo is a *matrix engine* — it crosses prompts × providers × test cases and makes the comparison first-class. That shape is exactly what prompt/model selection work looks like, which is why it dominates the "which prompt, which model" workflow even for teams that use heavier tooling for everything else.

## Core concepts

### The config

A single YAML file declares:

- **Prompts** — one or more prompt templates to compare.
- **Providers** — one or more models to test against.
- **Tests** — assertions: exact match, regex, LLM-rubric, javascript function.

The matrix semantics are the core: 3 prompts × 3 providers × 50 tests = 450 executions per run, and the UI's value is *spotting the interactions* — prompt A wins on GPT-6.1 Sol but loses on Claude Sonnet 5.5; a test that passes everywhere except one provider. This is information a single-config runner structurally can't show you, and it's why promptfoo's comparison view (not its assertions) is the killer feature for selection work.

### The assertions

| Assertion | Use |
|-----------|-----|
| `equals` | Exact match |
| `icontains` | Case-insensitive contains |
| `regex` | Pattern |
| `is-json` | Valid JSON |
| `llm-rubric` | LLM judges against a rubric |
| `javascript` | Custom function |
| `similar` | Embedding similarity to expected |
| `latency` / `cost` (per-provider) | Performance gates |

The `javascript` assertion is the escape hatch that makes promptfoo sufficient for most custom grading: any deterministic check (does the JSON parse against *our* schema? are all cited doc IDs real? is the refund amount ≤ policy cap?) is a few lines of JS in the config. Teams underuse it — they leave for a custom runner when they hit the first assertion type not in the table, when a `javascript` block would have kept them in the matrix engine.

### CI as the point

promptfoo's real product is *regression gating in CI*. The eval that runs only when someone remembers is a dashboard, not a gate. The `--fail-under` flag converts eval scores into pass/fail — which converts PR review from "looks fine, the prompt changed" into "the eval caught a 4-point drop on category X."

## Code: a promptfoo config

```yaml
# promptfooconfig.yaml
description: Billing agent evals

prompts:
  - file://prompts/billing_v1.txt
  - file://prompts/billing_v2.txt

providers:
  - id: openai:gpt-6.1-sol
  - id: anthropic:claude-sonnet-5-5

tests:
  - description: Simple refund
    vars:
      query: "I want a refund for order 123"
    assert:
      - type: icontains
        value: "refund"
      - type: llm-rubric
        value: "Mentions the order ID 123 and provides next steps."
      - type: latency
        threshold: 5000  # ms

  - description: High-value refund escalates
    vars:
      query: "I want a refund for $5000"
    assert:
      - type: icontains
        value: "escalate"
      - type: llm-rubric
        value: "Does NOT promise the refund directly."
```

## Run

```bash
npx promptfoo eval
npx promptfoo view  # opens web UI with results
```

## CI integration

```yaml
# .github/workflows/evals.yml
- name: Run evals
  run: npx promptfoo eval -c promptfooconfig.yaml --no-cache
- name: Fail on regression
  run: npx promptfoo eval --fail-under 0.85   # fail CI below 85% pass rate
```

The CI pattern has two gates worth separating: *absolute* (`--fail-under 0.85` — is the prompt good enough) and *relative* (did this PR's score drop vs main — the regression gate; promptfoo's output artifacts support diffing). The relative gate is the one that changes review behavior; absolute thresholds go stale as the set grows harder.

promptfoo also ships a **red-teaming module** (`npx promptfoo redteam`) that generates injection/jailbreak/datamarking attacks against your target — the lightest way to wire agent-security checks into CI (see `../10-safety/02-garak-pyrit.md` for deeper scanners).

## Production concerns

- **Latency:** Evals are offline; latency is fine — but *matrix* latency matters: 3×3×50 with llm-rubric assertions is 450 generations + judge calls; parallelism config is the difference between a 5-minute and 45-minute CI job.
- **Cost:** LLM-rubric assertions are 2× prompt cost. Use sparingly on cheap models; and cache (`--no-cache` only in the gating step — exploratory runs should cache aggressively).
- **Failure modes:** (1) LLM-rubric judges drift — pin a specific model version (`02-llm-as-judge.md`); (2) flaky assertions in CI — same case flips across runs; find and fix or the team learns to ignore red builds (the *worst* outcome of CI evals); (3) config sprawl — eval configs per team per prompt with no shared assertions; extract shared test files (`file://tests/common.yaml`) so policy tests are written once.
- **Security:** Test cases may contain PII; don't commit them. promptfoo configs also carry provider API keys via env in CI — scope CI credentials to eval-only keys with spend limits; an eval runaway is a bill, and a capped key turns it into a failed job.

## Anti-patterns

- ❌ **Only exact-match assertions.** LLMs rarely produce exact matches.
- ❌ **No CI integration.** Evals that don't run on PRs are useless.
- ❌ **Comparing prompts without a control.** Always have a baseline.
- ❌ **Leaving for a custom runner at the first custom check.** The `javascript` assertion covers deterministic grading.
- ❌ **Absolute threshold only, no relative gate.** Regression diffing is what changes review behavior.
- ❌ **Tolerating flaky assertions.** Red builds that mean nothing train the team to click through.

## References

- [promptfoo docs](https://www.promptfoo.dev/docs/) — verified 2026-10-20
- [promptfoo GitHub](https://github.com/promptfoo/promptfoo) — verified 2026-10-20
