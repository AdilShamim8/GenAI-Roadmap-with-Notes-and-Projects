import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import Asset, MultimodalIndex, handle, triage


def make_index():
    idx = MultimodalIndex()
    idx.add(Asset("img1", "image", caption="error dialog screenshot", ocr_text="ERR_CONN_REFUSED 4421"))
    idx.add(Asset("doc1", "document", text="refund policy: 30 days, over $500 needs approval"))
    return idx


def test_triage_by_task_type():
    assert triage("where is my order", False) == "billing"
    assert triage("how to install", False) == "howto"
    assert triage("hello", False) == "general"
    assert triage("look at this", True) == "multimodal_lookup"


def test_ocr_route_finds_exact_code():
    idx = make_index()
    hits = idx.search("ERR_CONN_REFUSED")
    assert hits and hits[0].id == "img1"  # found via OCR, not caption


def test_text_route_finds_policy():
    idx = make_index()
    hits = idx.search("refund policy")
    assert any(h.id == "doc1" for h in hits)


def test_attachment_fetch_by_id_keeps_original():
    idx = make_index()
    out = handle("what is this error", idx, attachment_id="img1")
    assert out["route"] == "multimodal_lookup:image" and out["context_ids"] == ["img1"]


def test_missing_attachment_reported():
    out = handle("what is this", make_index(), attachment_id="nope")
    assert out["route"].endswith("missing")
