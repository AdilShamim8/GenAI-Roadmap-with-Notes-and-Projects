"""Eval-driven prompt refinement — golden set, variant comparison, best-pick.

Encodes 07-evals/06 discipline: same cases, paired comparison, no shipping on
noise (a variant wins only if it beats baseline on a majority, not by 1 case)."""
from __future__ import annotations


def run_variant(prompt: str, case: str, call_fn) -> str:
    return call_fn(prompt, case)


def score(output: str, expected: dict) -> bool:
    out = output.lower()
    return all(k.lower() in out for k in expected.get("must_mention", [])) and not any(
        k.lower() in out for k in expected.get("must_not_mention", [])
    )


def compare(baseline: str, variant: str, cases: list[dict], call_fn) -> dict:
    """Paired comparison on identical cases. Winner needs a strict majority win
    (wins > losses); ties go to baseline (don't ship on noise)."""
    wins = losses = 0
    for c in cases:
        b_ok = score(run_variant(baseline, c["input"], call_fn), c["expected"])
        v_ok = score(run_variant(variant, c["input"], call_fn), c["expected"])
        if v_ok and not b_ok:
            wins += 1
        elif b_ok and not v_ok:
            losses += 1
    return {"wins": wins, "losses": losses, "ship_variant": wins > losses}


def main() -> None:
    def fake_call(prompt, case):
        # deterministic fake: 'v2' prompts pass everything, baseline half
        return "gold answer" if "v2" in prompt else ("gold answer" if len(case) % 2 else "miss")
    cases = [{"input": f"case{i}", "expected": {"must_mention": ["gold"]}} for i in range(10)]
    print(compare("baseline prompt", "v2 prompt", cases, fake_call))
