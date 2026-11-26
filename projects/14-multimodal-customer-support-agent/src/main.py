"""Multimodal support agent — triage + multi-route retrieval (caption + OCR +
text), per 03-rag/07: no single route anticipates every query; the original
asset stays retrievable by ID."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Asset:
    id: str
    kind: str  # image | document
    text: str = ""        # extracted text (page/caption)
    caption: str = ""     # VLM caption
    ocr_text: str = ""    # OCR of embedded text


class MultimodalIndex:
    def __init__(self):
        self.assets: dict[str, Asset] = {}

    def add(self, asset: Asset) -> None:
        self.assets[asset.id] = asset

    def search(self, query: str) -> list[Asset]:
        """Search ALL routes (text + caption + OCR) — the multi-route rule."""
        q = query.lower().split()
        scored = []
        for a in self.assets.values():
            score = sum(
                t in a.text.lower() or t in a.caption.lower() or t in a.ocr_text.lower()
                for t in q
            )
            if score:
                scored.append((score, a))
        scored.sort(key=lambda x: -x[0])
        return [a for _, a in scored[:5]]


def triage(message: str, has_attachment: bool) -> str:
    """Task-type routing (08-production/01): route by WHAT it is, not difficulty."""
    m = message.lower()
    if has_attachment:
        return "multimodal_lookup"
    if "invoice" in m or "order" in m or "refund" in m:
        return "billing"
    if "how" in m or "setup" in m or "install" in m:
        return "howto"
    return "general"


def handle(message: str, index: MultimodalIndex, attachment_id: str | None = None) -> dict:
    route = triage(message, attachment_id is not None)
    context = []
    if route == "multimodal_lookup" and attachment_id:
        # direct asset fetch — original retrievable by ID (never caption-only)
        a = index.assets.get(attachment_id)
        context = [a] if a else []
        route = f"multimodal_lookup:{a.kind}" if a else "multimodal_lookup:missing"
    elif route in ("billing", "howto", "general"):
        context = index.search(message)
    return {"route": route, "context_ids": [a.id for a in context], "context_kinds": [a.kind for a in context]}
