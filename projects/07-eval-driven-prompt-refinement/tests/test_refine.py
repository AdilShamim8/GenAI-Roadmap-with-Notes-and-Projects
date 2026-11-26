import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import compare, score


def test_ship_needs_majority_not_one_case():
    cases = [{"input": f"c{i}", "expected": {"must_mention": ["gold"]}} for i in range(10)]
    # variant wins exactly 1, loses 0 -> not a ship (noise)
    r = compare("base", "var", cases, lambda p, c: "gold" if p == "var" and c in ("c0","c1") else "miss")
    assert r == {"wins": 1, "losses": 0, "ship_variant": False}


def test_clear_win_ships():
    cases = [{"input": f"c{i}", "expected": {"must_mention": ["gold"]}} for i in range(6)]
    r = compare("base", "var", cases, lambda p, c: "gold" if p == "var" else "miss")
    assert r["ship_variant"] and r["wins"] == 6


def test_regression_blocks_ship():
    cases = [{"input": f"c{i}", "expected": {"must_mention": ["gold"]}} for i in range(4)]
    # 2 wins 2 losses -> tie goes to baseline
    r = compare("base", "var", cases,
                lambda p, c: "gold" if (p == "var") == (c in ("c0", "c1")) else "miss")
    assert not r["ship_variant"]


def test_score_rubric():
    assert score("the GOLD answer", {"must_mention": ["gold"]})
    assert not score("wrong", {"must_mention": ["gold"]})
    assert not score("gold but mentions evil", {"must_mention": ["gold"], "must_not_mention": ["evil"]})
