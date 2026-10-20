# DeepEval & Ragas

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [Ragas](https://github.com/vibrantlabsai/ragas), [DeepEval](https://github.com/confident-ai/deepeval)

## Why this matters

For RAG-specific evals (faithfulness, relevance, context recall), DeepEval and Ragas are the standard libraries. They implement research-backed metrics that go beyond simple matching.

## Core concepts

### RAG-specific metrics

| Metric | What it measures | Library |
|--------|-----------------|---------|
| **Faithfulness** | Is the answer grounded in the retrieved context? | Both |
| **Answer relevance** | Does the answer actually address the question? | Both |
| **Context precision** | Are the retrieved chunks relevant? | Both |
| **Context recall** | Did we retrieve enough to answer? | Ragas |
| **Context entity recall** | Did we retrieve the entities the answer needs? | Ragas |

### The cost

All of these use LLM-as-judge under the hood. A 100-example RAG eval with 4 metrics = 400+ LLM calls. Budget accordingly.

## Code: Ragas

```python
from ragas import evaluate, EvaluationDataset   # ragas >= 0.2 API
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

data = Dataset.from_dict({
    "question": ["What is MoE?"],
    "answer": ["MoE is a model architecture where..."],
    "contexts": [["MoE is a model architecture..."]],
    "ground_truth": ["MoE routes tokens to a subset of experts."],
})

result = evaluate(data, metrics=[faithfulness, answer_relevancy, context_precision, context_recall])
print(result)  # {faithfulness: 0.9, answer_relevancy: 0.85, ...}
```

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

## Production concerns

- **Latency:** 100 examples × 4 metrics = 400 LLM calls = ~5 min.
- **Cost:** ~$5–$15 per run.
- **Failure modes:** LLM-judge metrics are noisy; report confidence intervals.
- **Security:** Datasets contain production queries; anonymize.

## Anti-patterns

- ❌ **Running all metrics on every example.** Pick metrics per use case.
- ❌ **No human spot-check.** LLM-judge metrics drift; audit monthly.
- ❌ **Treating Ragas scores as ground truth.** They're signals.

## References

- [Ragas](https://github.com/explodinggradients/ragas) — verified 2026-10-20
- [DeepEval](https://github.com/confident-ai/deepeval) — verified 2026-10-20
