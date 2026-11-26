# DeepEval & Ragas

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [Ragas](https://github.com/explodinggradients/ragas), [DeepEval](https://github.com/confident-ai/deepeval)

## Why this matters

For RAG-specific evals (faithfulness, relevance, context recall), DeepEval and Ragas are the standard libraries. They implement research-backed metrics that go beyond simple matching. The expert framing: these libraries don't just *score* RAG — they implement a **decomposition diagnosis**. The RAG triad (faithfulness, answer relevance, context relevance) locates *which stage failed*: bad answer because bad context (retrieval problem) vs. bad answer with good context (generation problem) is a completely different fix, and the triad is the fastest way to tell them apart.

## Core concepts

### RAG-specific metrics — as a diagnostic, not a scoreboard

| Metric | What it measures | If it's low, the problem is... |
|--------|-----------------|-------------------------------|
| **Faithfulness** | Is the answer grounded in the retrieved context? | Generation — the model invented or extrapolated |
| **Answer relevance** | Does the answer actually address the question? | Generation or query understanding |
| **Context precision** | Are the retrieved chunks relevant? | Retrieval ranking — noise in the top-K |
| **Context recall** | Did we retrieve enough to answer? | Retrieval coverage — the answer isn't in the context |
| **Context entity recall** | Did we retrieve the entities the answer needs? | Retrieval on entity-heavy queries |

Reading the *combination* is the expert move:

- Low context recall + high faithfulness = the model stayed honest but couldn't answer — fix retrieval (better chunking, more candidates, hybrid search).
- High context recall + low faithfulness = the right docs were there and the model ignored/misused them — fix generation (prompt, model tier) or context placement (`../03-rag/01-chunking-strategies.md`).
- High everything but bad user feedback = your metrics measure what users don't care about — recalibrate against user signals, not library defaults.

This is why the triad exists as a triad: each metric is cheap alone but nearly meaningless alone — the diagnosis is in the pattern.

### The cost

All of these use LLM-as-judge under the hood. A 100-example RAG eval with 4 metrics = 400+ LLM calls. Budget accordingly — and note the *decomposition* structure of faithfulness-style metrics: the judge first decomposes the answer into claims, then verifies each claim against context. That's 2+ judge calls per metric per example, not 1 — the real multiplier is 600-1000 calls for that 100×4 run, and estimating it as 400 is how eval budgets get blown.

### Metric validity — know what the number means

These metrics are themselves LLM approximations of constructs (Ragas's faithfulness is a claim-verification chain; DeepEval's is a similar judge pipeline). Two validity caveats worth internalizing:

1. **The metrics disagree with each other and with humans at a known rate.** Treat library scores as *signals with error bars* (`06-statistical-rigor.md`), not ground truth. A 0.82 vs 0.78 faithfulness difference on 100 examples is inside the noise.
2. **The metric inherits the judge's blind spots.** A judge that can't detect subtle numerical hallucinations will report high faithfulness on numerically-wrong answers. Validate the metric itself once per judge version: hand-check 20-30 outputs against the metric's score; if agreement with your eyes is poor, the metric isn't measuring your failure mode.

## Code: Ragas

```python
from ragas import evaluate, EvaluationDataset   # ragas >= 0.2 API
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from datasets import Dataset

data = Dataset.from_dict({
    "question": ["What is MoE?"],
    "answer": ["MoE is a model architecture where..."],
    "contexts": [["MoE is a model architecture..."]],
    "ground_truth": ["MoE routes tokens to a subset of experts."],
})

result = evaluate(data, metrics=[faithfulness, answer_relevancy, context_precision, context_recall])
print(result)  # {faithfulness: 0.9, answer_relevancy: 0.85, ...}
```

Note `context_recall` needs `ground_truth` — reference answers. Metrics split on this requirement: faithfulness/relevancy work reference-free (judge against retrieved context), recall metrics need ground truth (can't know "did we retrieve enough" without the answer). Reference-free metrics scale to production traffic sampling; ground-truth metrics stay on curated golden sets — plan data collection accordingly (`01-golden-datasets.md`).

## Code: DeepEval (pytest-style)

```python
from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase

def test_billing_answer():
    case = LLMTestCase(
        input="I want a refund for order 123",
        actual_output="I've issued refund r_456 for order 123.",
        retrieval_context=["Order 123 was placed on 2026-07-01 for $49.99."],
    )
    assert_test(case, [FaithfulnessMetric(threshold=0.7), AnswerRelevancyMetric(threshold=0.7)])
```

Run with `pytest`.

### DeepEval vs Ragas (the comparison the title promises)

DeepEval is **pytest-native**: metrics assert inside your existing test suite, best for regression gating in CI. Ragas is **dataset-native**: RAG-triad metrics computed over evaluation datasets, best for offline RAG-quality measurement and corpus experiments. They compose: Ragas to find weak spots, DeepEval to lock improvements in.

The composition workflow, end to end: Ragas on a corpus change (new chunking strategy, new embedder) → read the *pattern* (which of the triad moved) → fix the right stage → DeepEval cases (with thresholds) added to CI so the improvement stays locked → quarterly human spot-check of both libraries' outputs because both are judge-based.

## Production concerns

- **Latency:** 100 examples × 4 metrics = 400+ LLM calls = ~5 min (parallelize; both libraries support it).
- **Cost:** ~$5–$15 per run. With the claim-decomposition multiplier, budget $15-30 for a full 100×4 run — and run the *cheap* triad (2 reference-free metrics) on every PR, the full set on corpus changes only.
- **Failure modes:** (1) LLM-judge metrics are noisy — report confidence intervals; (2) judge version drift moves both libraries' scores silently — pin judge models in each library's config; (3) metric gaming — optimizing faithfulness to 1.0 by making answers that copy context verbatim (faithful but useless); thresholds should be targets, not maximization goals.
- **Security:** Datasets contain production queries; anonymize. Both libraries also send your contexts to their configured judge provider — a data-flow consideration for regulated content: self-host the judge or restrict to approved providers.

## Anti-patterns

- ❌ **Running all metrics on every example.** Pick metrics per use case — reference-free on PRs, full set on corpus changes.
- ❌ **No human spot-check.** LLM-judge metrics drift; audit monthly.
- ❌ **Treating Ragas scores as ground truth.** They're signals with error bars.
- ❌ **Reading one metric alone.** The diagnosis is in the triad pattern.
- ❌ **Maximizing faithfulness.** Verbatim-copy answers are perfectly faithful and perfectly useless; target thresholds, don't optimize to 1.0.
- ❌ **Forgetting ground-truth requirements.** Recall metrics need reference answers; collect them or skip those metrics honestly.

## References

- [Ragas](https://github.com/explodinggradients/ragas) — verified 2026-10-20
- [DeepEval](https://github.com/confident-ai/deepeval) — verified 2026-10-20
