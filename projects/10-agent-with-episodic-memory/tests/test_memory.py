import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import EpisodicMemory


def test_write_dedupes_and_updates_recency():
    m = EpisodicMemory()
    m.write_from_turn(["likes tea"], now=0)
    m.write_from_turn(["likes tea"], now=500)
    assert len(m.store) == 1 and m.store[0]["ts"] == 500


def test_recall_ranked_by_overlap_and_recency():
    m = EpisodicMemory()
    m.write_from_turn(["prefers dark mode"], now=0)
    m.write_from_turn(["prefers dark mode in editor"], now=50)
    got = m.recall(["dark", "mode"], now=60)
    assert got and "editor" in got[0]  # fresher, more specific wins


def test_decay_purges_stale():
    m = EpisodicMemory(ttl_s=100)
    m.write_from_turn(["old fact"], now=0)
    assert m.purge_expired(now=200) == 1
    assert m.recall(["old"], now=200) == []


def test_facts_are_hints_only_by_contract():
    m = EpisodicMemory()
    m.write_from_turn(["user on Pro plan"], now=0)
    # recall returns strings — the caller is responsible for verifying against
    # the system of record (memory-as-hints rule from 05-agents/06)
    assert isinstance(m.recall(["plan"])[0], str)
