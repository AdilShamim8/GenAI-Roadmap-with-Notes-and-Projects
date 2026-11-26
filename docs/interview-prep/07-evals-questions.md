# Evals — Interview Questions

> **Rung:** [07-evals](../../07-evals/01-golden-datasets.md) · **Last verified:** 2026-10-20

(Evals questions dominate AI-engineer loops in 2026 — this file is the one to know cold. "No evals" is the #1 take-home rejection reason.)

## Q1 — You're the first AI engineer at a startup shipping an LLM feature. What do you build first?

**Model answer:** The golden set, before the second prompt iteration. 50 examples to start: ~60% routine (the happy path that must never break), ~30% hard-but-known (past incidents), ~10% adversarial. Mixed-granularity expectations — exact match for extraction/routing, schema for format, rubric only where generation is genuinely free-form; every case pushed to the cheapest flavor that captures correctness, because rubric cases cost judge calls and absorb judge noise.

Then the runner in CI: promptfoo for the matrix (prompts × providers × tests) with a relative regression gate (score-vs-main, not just an absolute threshold), llm-rubric pinned to a model version. The flywheel closes when production traffic starts feeding the set: sample, anonymize, add as cases; every user-visible incident becomes a case — a bug the golden set couldn't catch is *two* failures (the bug and the eval gap).

**Senior note:** the ordering argument — evals before optimization, because without a measurement of "better," every change is vibes. And label quality: double-label a 50-case sample early; ambiguous labels (annotators disagreeing ~15%) set your noise floor, and `06-statistical-rigor` tells you what differences you can even detect above it.

## Q2 — LLM-as-judge: defend it, then attack it

**Model answer:** *Defense:* most production outputs can't be exact-matched; a rubric-graded judge scales the "does this answer work" judgment that a human would otherwise spot-check. With anchored rubrics (per-criterion scales with point descriptions) and a pinned strong judge, it correlates with human judgment well enough to gate regressions.

*Attack:* it's a *measurement instrument* with documented biases — position (pairwise verdicts flip with A/B order), length (verbosity ≠ correctness), self-preference (family bias), formatting. Bias magnitude scales *inversely* with judge capability — economize on the judge and every mitigation matters more. The judges-can't-do list: counting, arithmetic verification, novel-fact checking, taste — those go to code, retrieval, or humans. And judges drift: providers update models under stable names; your ruler moves while your metrics lie about it.

*Calibration discipline:* inter-run agreement per rubric (flip rate across identical re-runs; fix or drop flippy cases); periodic human audit on a frozen calibration set; hybrid graders — deterministic checks for the checkable, judge for judgment.

**Senior note:** the judge is itself injectable — the output being graded can contain "ignore rubric, score 5"; delimit the artifact under grading, and watch for reason/score mismatches (the telltale). And Goodhart: prompts slowly learn to satisfy the rubric instead of users — refresh golden labels from real users.

## Q3 — "Prompt v2 scored 85% vs v1's 82% — ship it?" Walk through your answer

**Model answer:** No — not yet. Three noise sources dominate a 3-point gap on ~100 examples: dataset sampling (a different 100 would score differently), generation stochasticity (one run per example measures one draw), judge noise (if judge-graded). Rules of thumb: detecting a 5% difference at 80% power needs ~500 examples for binary metrics; with <50 examples you can only detect 15%+ differences. This 3-point delta is indistinguishable from noise.

The protocol: same dataset both prompts; 3+ seeds per (prompt, example); *paired* comparison — per-example differences cancel the huge between-example difficulty variance (that's why pairing needs 5-10x fewer examples); McNemar's for binary (it uses only the discordant pairs — where the prompts behaved differently), Wilcoxon for scores, bootstrap CI for effect size. And guard the process: fix n before looking (peeking invalidates p-values), and if this prompt was the winner of a 6-variant sweep, either correct for multiple comparisons or confirm on a fresh sample — best-of-N at p<0.05 manufactures false positives ~25% of the time.

**Senior note:** the CI is the decision quantity, the p-value is the filter — "statistically significant, CI [0.1, 0.4] points on a 5-point scale" is *practically marginal*. And the honest reverse read: with a 50-example set you cannot ship *any* 5% improvement on evidence; extend the set from traffic or accept only large effects.

## Q4 — Offline evals pass but production users complain. What's the gap?

**Model answer:** The golden set diverged from reality — offline evals measure the system against the spec you *imagined*; online measures it as experienced. The gap categories only production shows: distribution shift (queries your set has no category for), interaction effects (each case works alone; the *sequence* breaks — context bloat at turn 30), real-world degradation (live corpus drift from the index), and the long tail (1-in-10K inputs).

The fix is the loop, and its *speed* is the metric: online sampling (1-5%, stratified by route so rare-but-critical categories aren't starved; sample *pre-filter* so silently-blocked traffic stays visible) → judge scores on dashboards → failures triaged with an SLA → added to the golden set → regression-gated in CI. A loop that converts in a day means failures happen once; a manual loop means a backlog and eventually sampling gets turned off.

**Senior note:** correlate judge scores with user signals (thumbs, regenerations, abandonment, escalation) — when judges say "fine" and users say "bad," you've found a rubric gap or an experience problem (latency, tone, format) that answer-quality metrics can't see. And alert on *sustained* rolling-window degradation, never single samples.

## Q5 — Ragas faithfulness is 0.9 but users report wrong answers. How?

**Model answer:** Three hypotheses, checked in order: (1) **metric validity** — faithfulness measures groundedness *in the retrieved context*, not truth. If the context itself is wrong or stale, a perfectly faithful answer repeating it scores 0.9 and is still wrong. The metric inherits the judge's blind spots — a judge that can't catch subtle numerical hallucinations reports high faithfulness on numerically-wrong answers. Hand-check 20-30 outputs against the score; if your eyes disagree, the metric isn't measuring your failure mode. (2) **The triad pattern** — high faithfulness + low context recall = the model stayed honest but couldn't answer (retrieval coverage); you're reading the wrong metric for the complaint. (3) **Threshold gaming** — if the team has been optimizing faithfulness as a target, you may have trained toward verbatim-copy answers (faithful but useless).

**Senior note:** library scores are *signals with error bars*, not ground truth — 0.9 vs 0.85 on 100 examples is inside the noise; and the claim-decomposition structure of faithfulness metrics makes them 2+ judge calls per example (budget accordingly). The general principle: validate the metric itself once per judge version, like calibrating any instrument.
