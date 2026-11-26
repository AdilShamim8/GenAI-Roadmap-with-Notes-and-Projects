# Statistical Rigor for Prompt Changes

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [McNemar's test](https://en.wikipedia.org/wiki/McNemar%27s_test), [Wilcoxon signed-rank test](https://en.wikipedia.org/wiki/Wilcoxon_signed-rank_test)

## Why this matters

"Prompt v2 scored 85% vs v1's 82%, ship it" is the most common evals mistake. On a 100-example dataset, that 3-point difference is likely noise. Without statistical rigor, you'll ship regressions disguised as improvements. The expert framing: eval scores are *random variables* — sampled from the joint distribution of (dataset choice, generation stochasticity, judge noise). Once you internalize that, "is v2 better?" becomes "is the observed difference larger than the sampling noise?" — a question with established tools.

## Core concepts

### The problem

LLM outputs are stochastic. Eval scores are noisy. Small differences on small datasets are dominated by noise, not signal.

The three noise sources, ranked by how much teams underestimate them:

1. **Dataset sampling noise** — your 100 examples are a sample of the infinite space of inputs; a different 100 would score differently. This is the classical one.
2. **Generation stochasticity** — same prompt, same input, different output (temperature > 0, provider-side nondeterminism). One run per (prompt, example) measures a single draw.
3. **Judge noise** — the grader itself has inter-run variance (`02-llm-as-judge.md`); a noisy judge adds variance to every measurement, and *paired* comparisons only partially cancel it.

The design consequence: seed-replication addresses (2); paired tests address (1) by using each example as its own control; judge calibration addresses (3). Skipping any one leaves that noise term fully in your measurement.

### The minimum bar

For a prompt change A vs B:

1. **Same dataset** — both prompts run on the same golden set.
2. **Multiple seeds** — each prompt × example × 3+ seeds (temperature > 0).
3. **Paired comparison** — for each (example, seed), compare A vs B.
4. **Significance test** — McNemar's test for binary outcomes, Wilcoxon for scores.

*Why paired matters* is the part worth understanding: examples differ enormously in difficulty, and that between-example variance is huge relative to between-prompt variance. Pairing (each example graded under both A and B, difference taken per example) cancels the difficulty variance entirely — you measure only "how did the change affect this example," which is precisely the estimand. Unpaired comparisons (A's mean on the set vs B's mean on the set — or worse, on *different* sets) leave difficulty variance in the estimate, which is why they need ~5-10x more examples for the same power.

### The tests, matched to outcome type

- **McNemar's** — binary pass/fail, paired. It uses only the *discordant* pairs (A passed/B failed and A failed/B passed) — the pairs where the prompts behaved differently. This is its power secret: concordant pairs (both pass, both fail) carry no information about the difference and are discarded. For a 100-example set where 8 flipped each way, the test is about those 16, not the 100.
- **Wilcoxon signed-rank** — ordinal/score outcomes, paired. Ranks the per-example differences rather than trusting their magnitudes — robust to outlier scores from a noisy judge on one example.
- **Bootstrap CI** — the "I want a plain-English effect size" option: resample the paired differences, get a confidence interval for the *magnitude* of improvement. A significant p-value with a CI of [0.1, 0.4] points on a 5-point scale is "statistically real, practically marginal" — the CI tells you what the p-value can't.

### Sample size

Rough rules of thumb for detecting a 5% difference with 80% power:

- Binary pass/fail metric: ~500 examples per prompt.
- 1–5 score metric: ~100 examples per prompt.

If your golden set is <50, you can only detect 15%+ differences.

Read this honestly in reverse: *with 50 examples you cannot distinguish a real 5% improvement from noise — full stop.* Teams burn weeks iterating prompts against small sets, "shipping" noise, and the meta-effect is worse than any single bad ship: the eval loses credibility ("the scores move around for no reason") and people go back to vibes. If the set can't be grown, the honest options are: accept only large effects, extend the set (traffic sampling, `01-golden-datasets.md`), or don't run A/B comparisons at all — regression-gate only.

### Multiple comparisons (the trap in prompt iteration)

Run 6 prompt variants against the baseline and pick the best at p < 0.05, and you'll "find" improvements that aren't real ~25% of the time — the multiple-comparisons problem. Each comparison is a 1-in-20 chance of a false positive; six comparisons compound. Corrections exist (Bonferroni: divide α by the number of comparisons — brutally conservative; Holm: sequential, gentler), but the *practical* defense is structure: pre-register what you're testing (variant count, primary metric) before running, and treat exploratory sweeps as hypothesis-generation — confirm the winner on a *fresh* sample before shipping. The confirmation run is the step everyone skips and the step that kills false positives.

## Code: paired comparison with significance test

```python
from scipy.stats import wilcoxon
import numpy as np

# scores_a[i] and scores_b[i] are scores on the same example i
scores_a = np.array([...])
scores_b = np.array([...])

diff = scores_b - scores_a
print(f"Mean improvement: {diff.mean():.3f}")

stat, p = wilcoxon(scores_a, scores_b)
print(f"Wilcoxon p-value: {p:.4f}")

if p < 0.05 and diff.mean() > 0:
    print("B is significantly better. Ship it.")
else:
    print("No significant difference. Don't ship.")
```

## Code: bootstrap confidence interval

```python
def bootstrap_ci(scores_a, scores_b, n_boot=10000, ci=0.95):
    diffs = scores_b - scores_a
    boot_means = [np.random.choice(diffs, len(diffs)).mean() for _ in range(n_boot)]
    lower = np.percentile(boot_means, (1 - ci) / 2 * 100)
    upper = np.percentile(boot_means, (1 + ci) / 2 * 100)
    return lower, upper

lo, hi = bootstrap_ci(scores_a, scores_b)
print(f"95% CI for improvement: [{lo:.3f}, {hi:.3f}]")
```

## Production concerns

- **Latency:** More seeds = more eval time. Parallelize; eval wall-clock is the CI-budget constraint.
- **Cost:** 3 seeds × 200 examples × 2 prompts = 1200 LLM calls per eval. Judge calls roughly double it. This is why rigor is *expensive* — and why the discipline is "rigor for ship decisions, cheap gates for PRs" (`03-promptfoo.md` relative gating).
- **Failure modes:** (1) judge noise dominating — audit judges; a judge with 20% inter-run variance can mask real 10% effects; (2) peeking — running the eval, seeing p=0.07, adding examples until p<0.05; this invalidates the test (optional stopping); fix the n *before* looking; (3) significance theater — shipping on p-values while ignoring effect size; the CI is the decision quantity, the p-value is the filter.
- **Security:** No special concerns beyond standard eval hygiene.

## Anti-patterns

- ❌ **"Ship if score went up."** Statistical noise.
- ❌ **One seed per example.** Can't separate noise from signal.
- ❌ **Different datasets for A and B.** Not comparable.
- ❌ **Unpaired comparisons.** Leaves difficulty variance in; needs 5-10x the examples.
- ❌ **Best-of-N picking without correction or confirmation.** False positives at scale.
- ❌ **Peeking / optional stopping.** Fix n before the test.
- ❌ **p-value without effect size.** The CI is the decision quantity.

## References

- [Evals for LLMs — Hamel Husain](https://hamel.dev/blog/posts/evals/) — verified 2026-10-20
- [McNemar's test](https://en.wikipedia.org/wiki/McNemar%27s_test) — verified 2026-10-20
- [Wilcoxon signed-rank test](https://en.wikipedia.org/wiki/Wilcoxon_signed-rank_test) — verified 2026-10-20
