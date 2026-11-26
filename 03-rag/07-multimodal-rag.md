# Multimodal RAG

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [Cohere Embed 5](https://docs.cohere.com/v2/reference/embed), [CLIP](https://openai.com/research/clip)

## Why this matters

Real corpuses aren't text-only. They're PDFs with embedded charts, slide decks with images, screenshots, video. Multimodal RAG retrieves across all of them so users can ask "show me the slide where revenue growth was forecast." The expert framing: the hard part isn't the embedding — it's that *the answer to a question may live in a modality the question never names*, and chunk-text-only pipelines structurally can't return it. Every text-only RAG system over a visual corpus is silently missing recall.

## Core concepts

### Three architectures

1. **Text-only with image captions (caption-then-embed)** — extract images, caption with a VLM, embed the caption. Cheapest; the corpus becomes text-searchable with zero image infrastructure. Loses: anything the caption didn't mention (a chart's axis values, a screenshot's error code). The caption is a *lossy summary written before you know the question* — it can't anticipate every query. Works when images are decorative or simple.
2. **Multi-vector (per-modality indexes)** — embed text with a text embedder, images with an image embedder, store both. Retrieve from either, merge. Gains: each modality gets its best encoder. Loses: cross-modal queries ("the slide about Q3 revenue" → a *text* query that must find an *image*) need either a shared space or a text bridge (captions again). Operationally: two indexes, two recall curves, harder evals.
3. **Unified multimodal embedding** — Cohere Embed 5, Voyage multimodal, CLIP-style models: embed text and images into the same space. Direct cross-modal retrieval. This is the 2026 default for image-heavy corpora. Trade-off: unified spaces are jack-of-both — a dedicated text embedder still beats them on text-only recall, so hybrid stacks often keep the text embedder for text chunks and add the multimodal model only for images.

### CLIP and what its training implies

CLIP was trained on image–caption pairs with a contrastive objective: matching pairs pull together, mismatched pairs push apart. Two consequences that still govern unified embedders: (1) retrieval quality is bounded by caption-style supervision — the model is good at "what is this a picture of" and weaker at fine-grained text-in-image (a screenshot's stack trace) or dense quantitative content (a chart's values); (2) text *rendered inside* images often needs OCR as a separate extraction pass, not just an image embedding — the embedding knows there's "text-ish stuff," not what it says.

So the practical stack for screenshot/diagram corpora: image embedding (visual similarity) + OCR text (embedded as text) + captions (VLM-generated semantic summary), all pointing at the same parent asset. Three retrieval routes into one artifact — expensive at index time, excellent at query time.

### The PDF special case

PDFs need special handling because they're a *container* of mixed modality, not a document format:

- Extract text with `pymupdf` or `unstructured` (layout-aware extraction preserves reading order; naive extraction interleaves columns and footers into garbage).
- Extract images per page (a page's chart, logo, and signature are different assets with different retrieval value — filter logos/signatures at extraction).
- Extract tables as structured data — tables embedded as text lose alignment; as images they lose exact values. Store the parsed structure (rows/columns) as text *plus* keep the page image for citation rendering.
- Embed each modality separately, link them with page coordinates. Coordinates give you the citation overlay (highlight the region in the source PDF) — the feature that makes multimodal RAG *verifiable* by users, which drives trust more than any accuracy metric.

### Query-time generation over images

Retrieved images can be passed directly to multimodal generation (the model *sees* the chart, not a caption of it) — strictly better answer quality for visual questions, at image-token cost (`01-llm-calling/07-multimodal.md` has the billing mechanics). Caption-based systems can't do this: the caption lost the pixels. Design the pipeline so the *original* image is retrievable by ID even when the index only stores its caption.

## Code: unified multimodal retrieval (CLIP-style)

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("clip-ViT-L-14")  # text + image in same space

# Index
text_emb = model.encode("a chart showing revenue growth")
img_emb = model.encode(Image.open("chart.png"))
# Store both in the same vector collection.

# Query with text
q_emb = model.encode("revenue growth chart")
results = collection.query(query_embeddings=q_emb, n_results=5)
```

## Code: PDF extraction (text + images + coordinates)

```python
import fitz  # pymupdf

def extract_pdf(path: str):
    doc = fitz.open(path)
    pages = []
    for page in doc:
        pages.append({
            "text": page.get_text(),
            # get_images returns xref tuples, not Pixmaps — wrap them:
            "images": [fitz.Pixmap(doc, img[0]).tobytes("png") for img in page.get_images(full=True)],
            "page_num": page.number,
        })
    return pages
```

## Production concerns

- **Latency:** Image embeddings are 5–20x slower than text per item (index-time concern mostly; batch them). Query-time, mixed-modality retrieval adds fan-out — run routes in parallel and merge with RRF (`03-hybrid-search.md`).
- **Cost:** VLM captioning adds up: 100K images × ~$0.001-0.005/caption = $100–500 one-time. Cache aggressively — never caption the same image twice (hash the bytes). Re-extraction (PDF→assets) is idempotent and cacheable by content hash.
- **Failure modes:** (1) OCR on scanned PDFs is unreliable — deskew and denoise first, and route scanned pages through a VLM extraction pass rather than classic OCR when quality matters; (2) caption blindness — the caption didn't mention the thing the user asked; mitigate with multi-route retrieval (caption + OCR + image embedding); (3) silent image drops — extraction pipelines that skip images they can't parse, leaving recall holes nobody notices until a user asks.
- **Security:** Image embeddings can leak visual content (logos, faces, dashboards) via inversion. Multimodal corpora also inherit image-borne prompt injection (instructions in screenshots — treat every retrieved image as untrusted text *and* pixels: `02-context-engineering/04-prompt-injection-defense.md`).

## Anti-patterns

- ❌ **Treating PDFs as text-only.** Loses charts, diagrams, signatures.
- ❌ **Embedding full-resolution images.** Resize to the embedder's expected input (≤512-896px typical); beyond that you pay compute for pixels the encoder downsamples anyway.
- ❌ **Mixing text and image embeddings from different model families.** They're not in the same space.
- ❌ **Caption-only retrieval for screenshot corpora.** Captions can't anticipate every query; add OCR + image routes.
- ❌ **Discarding the original image after captioning.** You lose direct multimodal generation and coordinate-based citation.

## References

- [Cohere Embed 5 (embed-v5.0)](https://docs.cohere.com/v2/reference/embed) — verified 2026-10-20
- [Unstructured](https://github.com/Unstructured-IO/unstructured) — verified 2026-10-20
- [CLIP](https://openai.com/research/clip) — verified 2026-10-20
