"""Eval runner — retrieval-quality evals over a fixed demo corpus.

Scored without any LLM: a case passes when the correct *document* is cited
and the gold answer string is present in the retrieved parent context. This
measures the retrieval stage (recall + right-doc precision) exactly as
07-evals/01 prescribes: cheapest flavor that captures correctness.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from main import HybridRAG, default_llm  # noqa: E402

CORPUS = {
    "pricing": (
        "Pricing\n\nThe Pro plan costs $49 per seat per month. Enterprise pricing "
        "is custom and starts at $10,000 annually.\n\nThe Free tier supports up to "
        "3 projects and community support only."
    ),
    "security": (
        "Security\n\nData is encrypted at rest with AES-256 and in transit with "
        "TLS 1.3. SOC 2 Type II certification was obtained in 2025.\n\nSingle "
        "sign-on via SAML is available on Enterprise plans only."
    ),
}

THRESHOLD = 0.85


def load_golden(path: str | Path | None = None) -> list[dict]:
    path = Path(path) if path else ROOT / "evals" / "golden.jsonl"
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def score(result: dict, expected: dict) -> tuple[bool, list[str]]:
    failures = []
    must_doc = expected.get("must_cite_doc")
    if must_doc and not any(must_doc in c for c in result["citations"]):
        failures.append(f"expected doc {must_doc!r} not cited; got {result['citations']}")
    for kw in expected.get("must_mention", []):
        in_contexts = any(kw.lower() in c.text.lower() for c in result["contexts"])
        in_answer = result.get("answer") and kw.lower() in result["answer"].lower()
        if not (in_contexts or in_answer):
            failures.append(f"gold token {kw!r} in neither contexts nor answer")
    return (not failures), failures


def main() -> int:
    rag = HybridRAG()
    rag.index(CORPUS)

    use_llm = bool(__import__("os").environ.get("OPENAI_API_KEY"))
    results = []
    for case in load_golden():
        result = rag.answer(case["input"], llm_fn=default_llm if use_llm else None)
        passed, failures = score(result, case["expected"])
        results.append({"id": case["id"], "passed": passed, "failures": failures, "citations": result["citations"]})
        print(f"  [{'PASS' if passed else 'FAIL'}] {case['id']}")
        for f in failures:
            print(f"          - {f}")

    passed = sum(r["passed"] for r in results)
    total = len(results)
    pass_rate = passed / total if total else 0
    mode = "retrieval-only" if not use_llm else "retrieval+generation"
    print(f"\n{passed}/{total} passed ({pass_rate:.1%}) [{mode} mode]")

    (ROOT / "evals" / "report.json").write_text(json.dumps(results, indent=2))
    if pass_rate < THRESHOLD:
        print(f"FAIL: below threshold {THRESHOLD}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
