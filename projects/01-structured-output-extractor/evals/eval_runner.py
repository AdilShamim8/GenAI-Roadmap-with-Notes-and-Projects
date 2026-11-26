"""Eval runner. Loads golden.jsonl, runs the extractor, scores field accuracy,
prints a report, and gates at a threshold.

Scoring is field-level (not keyword): each golden case carries ``schema`` and
``expected_fields``; a case passes when every expected field matches the
extracted object. This is stricter than must_mention rubrics and matches how
extraction products are judged in production.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import SCHEMAS, extract  # noqa: E402

THRESHOLD = 0.85


def load_golden(path: str = "evals/golden.jsonl") -> list[dict]:
    """Load the golden dataset."""
    cases = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            cases.append(json.loads(line))
    return cases


def run_agent(case: dict, client=None) -> dict:
    """Run the extractor for a golden case; returns the extracted dict."""
    obj = extract(case["input"], case["schema"], client=client)
    return obj.model_dump()


def score(output: dict, expected_fields: dict) -> tuple[bool, list[str]]:
    """Field-level scoring; returns (passed, list_of_failures)."""
    failures = []
    for field, want in expected_fields.items():
        got = output.get(field)
        if isinstance(want, list):
            # compare lists element-wise on dict fields we care about
            if len(got or []) != len(want):
                failures.append(f"{field}: length {len(got or [])} != {len(want)}")
                continue
            for i, (g, w) in enumerate(zip(got, want)):
                for k, v in w.items():
                    if g.get(k) != v:
                        failures.append(f"{field}[{i}].{k}: {g.get(k)!r} != {v!r}")
        elif got != want:
            failures.append(f"{field}: {got!r} != {want!r}")
    return (not failures), failures


def main():
    cases = load_golden()
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set — cannot run live evals.")
        print("Set the key (see .env.example) and re-run `make eval`.")
        return 1

    results = []
    for case in cases:
        try:
            output = run_agent(case)
            passed, failures = score(output, case["expected_fields"])
            results.append({"id": case["id"], "passed": passed, "failures": failures})
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {case['id']}")
            for f in failures:
                print(f"          - {f}")
        except Exception as e:  # noqa: BLE001 — eval must survive per-case errors
            results.append({"id": case["id"], "passed": False, "error": str(e)})
            print(f"  [ERROR] {case['id']}: {e}")

    passed = sum(r["passed"] for r in results)
    total = len(results)
    pass_rate = passed / total if total else 0
    print(f"\n{passed}/{total} passed ({pass_rate:.1%})")

    Path("evals/report.json").write_text(json.dumps(results, indent=2))

    if pass_rate < THRESHOLD:
        print(f"FAIL: pass rate below threshold ({THRESHOLD})")
        sys.exit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
