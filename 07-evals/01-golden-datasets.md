# Golden Datasets

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [Hamel Husain: Your AI Product Needs Evals](https://hamel.dev/blog/posts/evals/), [Anthropic: Evals guide](https://docs.anthropic.com/en/docs/build-with-claude/evals)

## Why this matters

Without a golden dataset, you're vibes-tuning prompts. Every change is a guess. A golden dataset — even 50 examples — turns prompt engineering from art to engineering. This is the single highest-leverage evals practice. The expert framing: the golden dataset is *the specification of your system's behavior* — what "correct" means, encoded as examples. Like any spec, its value is bounded by how well it represents reality, which is why dataset *composition* (not just size) is the real craft.

## Core concepts

### What's in a golden dataset

Each row contains:

- **Input** — the user query / context.
- **Expected output** — exact string, regex, or rubric.
- **Metadata** — category, difficulty, source.

### Three flavors — and choosing per-case, not per-dataset

| Flavor | What's expected | Eval method | Use when |
|--------|-----------------|-------------|----------|
| Exact match | Exact string | `output == expected` | Extraction, classification, routing — deterministic outputs |
| Regex / schema | Pattern or JSON schema | `re.match` / pydantic | Format contracts, structured outputs |
| Rubric | "Must mention X, must not mention Y" | LLM-as-judge | Free-form generation — the unavoidable case |

The expert move is *mixed-granularity expectation*: within one dataset, deterministic cases get exact match (cheap, exact, unambiguous), and only genuinely generative cases pay for judge-based grading. A dataset that's 100% rubric-graded is paying judge costs (and absorbing judge noise — `02-llm-as-judge.md`) on cases where `==` would do. Push each case to the cheapest flavor that still captures correctness.

### Dataset composition (the actual craft)

Size guidance is easy; *what's in the set* is what determines whether your eval catches regressions:

- **The difficulty pyramid.** ~60% routine cases (the happy path your system must never break), ~30% hard-but-known (the cases that motivated past fixes), ~10% adversarial (injection, ambiguity, out-of-scope). A set of only hard cases fails every PR; a set of only easy ones passes everything — both are useless gates.
- **Category coverage mirrors traffic, plus.** Mirror your production query distribution (so the pass rate *means* something), then *over-index* the tails: the 2% of production traffic that's weird (multilingual, malformed, hostile) deserves 10-15% of the set, because that's where regressions hurt most and where models differ most.
- **Every production incident becomes a case.** The postmortem discipline: a bug that reached users and wasn't catchable by your golden set is *two* failures — the bug, and the eval gap. Close both.
- **Known-tricky duplicates.** Same semantic question phrased 3 ways tests prompt-brittleness; near-miss negatives (questions that *look* like they should trigger a tool but shouldn't) test over-triggering.

### How big?

- **50 examples** — catches obvious regressions.
- **200 examples** — catches subtle ones.
- **1000+ examples** — production-grade; you'll need sampling to keep eval cost manageable.

Past ~200, marginal value per example drops while curation cost stays flat — growth should come from *traffic sampling and incident backfill* (real signal), not synthetic padding.

### Where do examples come from?

1. **Real production traffic** (sampled, anonymized) — best signal, and it *drifts with your users*: refresh quarterly or the set slowly becomes a spec for last year's product.
2. **Hand-crafted edge cases** — adversarial; catches known failure modes.
3. **LLM-generated synthetic** — useful for coverage; lower signal. Synthetic cases encode *your* imagination of failure, not users' actual creativity — fine for bootstrapping a new system, never a substitute for traffic.
4. **Public benchmarks** — good for calibration, not for production-specific behavior.

### Labels: who writes "expected," and how good are they?

Rubric labels written by one person in one sitting encode that person's assumptions; two labelers disagree on ~10-20% of generative cases (the classic inter-annotator problem). Practical discipline: double-label a 50-case sample when the set is young; measure agreement; where labelers disagree, the *case is ambiguous* — either split it into unambiguous cases or accept the case is testing judgment (and use a judge with a very specific rubric). A golden set with ambiguous labels produces noise floor that swamps real regressions (`06-statistical-rigor.md`).

## Code: a minimal golden dataset

```yaml
# 07-evals/golden.yaml
- id: refund_simple
  input: "I want a refund for order 123"
  expected:
    must_mention: ["refund_id", "order 123"]
    must_not_mention: ["competitor"]
    max_length: 100
  category: billing
  difficulty: easy

- id: refund_escalation
  input: "I want a refund for $5000"
  expected:
    must_mention: ["escalate", "tier-2"]
    must_route_to: human
  category: billing
  difficulty: medium
```

```python
# 07-evals/runner.py
import yaml

def run_evals(agent, golden_path: str):
    cases = yaml.safe_load(open(golden_path))
    results = []
    for c in cases:
        out = agent.run(c["input"])
        ok = (
            all(kw in out.lower() for kw in c["expected"]["must_mention"])
            and not any(kw in out.lower() for kw in c["expected"].get("must_not_mention", []))
        )
        results.append({"id": c["id"], "passed": ok, "output": out})
    passed = sum(r["passed"] for r in results)
    print(f"{passed}/{len(results)} passed")
    return results
```

### Format convention

This file uses YAML for readability; the repo's projects standardize on **JSONL** (`07-evals/golden.jsonl`, one case per line) so runners can stream cases. Same fields, different serialization. For execution at scale, load either into promptfoo or DeepEval rather than hand-rolling runners (see `03-promptfoo.md`, `04-deepeval-ragas.md`).

## Production concerns

- **Latency:** Eval runs are offline; latency doesn't matter, cost does.
- **Cost:** 200 examples × $0.02/call = $4/run. Run on every PR. Cheap-filter discipline (exact-match cases cost ~$0 beyond the generation call) keeps this flat as the set grows.
- **Failure modes:** (1) dataset rot — production queries drift; refresh quarterly; (2) *overfitting to the golden set* — prompts tuned against a static set start optimizing test-specific quirks; the fix is traffic refresh, not more tuning; (3) flaky rubric cases — a case that flips pass/fail across identical runs (judge noise) has a noise problem, not a signal problem; fix or remove it, and track per-case flip rate.
- **Security:** Don't put PII in golden files. Anonymize before committing — golden sets get copied into CI logs, PR comments, and vendor eval tools; treat them as public-by-default.

## Anti-patterns

- ❌ **No golden dataset.** You can't detect regressions.
- ❌ **Golden dataset with only easy cases.** Adversarial cases are the point.
- ❌ **Treating golden dataset as static.** It's a living artifact.
- ❌ **Rubric-grading everything.** Push each case to the cheapest flavor that captures correctness.
- ❌ **Growing the set with synthetic padding.** Grow from traffic and incidents.
- ❌ **Ignoring per-case flakiness.** Flipping cases are noise, not signal; fix or drop them.

## References

- [Hamel Husain: Your AI Product Needs Evals](https://hamel.dev/blog/posts/evals/) — verified 2026-10-20
- [Anthropic: Evals guide](https://docs.anthropic.com/en/docs/build-with-claude/evals) — verified 2026-10-20
