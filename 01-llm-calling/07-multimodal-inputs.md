# Multimodal Inputs

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [OpenAI vision](https://developers.openai.com/api/docs/guides/vision), [Anthropic vision](https://platform.claude.com/docs/en/build-with-claude/vision)

## Why this matters

Most production GenAI systems in 2026 are multimodal: PDFs, screenshots, photos, audio. Treating vision as an afterthought is the difference between a working and a broken document-QA system.

## Core concepts

### Image inputs: three ways

1. **URL** — provider fetches. Easiest, requires the URL to be public.
2. **Base64 inline** — embed in the request. Bigger payload, no fetch dependency.
3. **File upload** — provider-hosted file reference. Best for repeated use.

### Resolution economics (per-provider formulas — they differ)

- **OpenAI:** `detail: "low"` = fixed ~85 tokens regardless of size. High detail: the image is resized to fit within 2048px, scaled so the short side is ≤768px, then tiled into 512×512 patches (~170 tokens each) plus a base ~85 tokens. A 4K screenshot at high detail ≈ 1,100–1,600 tokens.
- **Anthropic:** tokens ≈ (width × height) / 750. Images longer than 1568px on the long edge are downscaled first, so pre-resizing to ≤1568px saves payload without changing billed tokens.

A 4K screenshot can cost ~1,500 tokens before any text is generated. Resize deliberately — but to each provider's own thresholds, not a generic rule.

**Choosing `detail`:** `low` (fixed ~85 tokens) is for existence/classification questions — "is there a table in this screenshot?" `high` (patch-based) is for reading — dense UI text, chart axes, scanned receipts. The expensive mistake is defaulting everything to `high`; the quality mistake is asking the model to read small text at `low`, where the downscaled thumbnail genuinely doesn't contain it. When accuracy matters, ask the model to *quote* the text it read — a verbatim quote is checkable; "the image says…" is not.

### Audio inputs

Audio-in is supported natively across the big three (chat-completions audio input on OpenAI; audio parts on Gemini; note Anthropic's core models are text+image+PDF — audio goes through their dedicated voice pipeline). For transcription-scale needs, a dedicated ASR pass first is usually cheaper and more debuggable than a frontier model listening to raw audio; reserve native-audio input for tasks where paralinguistics (tone, speaker turns) matter. For real-time speech, see `11-realtime-voice/`.

### PDF handling

- **OpenAI**: PDFs supported natively (up to ~100 pages per file in 2026).
- **Anthropic**: PDFs supported, with native text + image extraction.
- **DIY**: PyMuPDF to extract text + render pages to images → send as multimodal. More control, more code.

## Code: image + text (OpenAI)

```python
from openai import OpenAI
client = OpenAI()

resp = client.chat.completions.create(
    model="gpt-6.1-sol",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {"type": "image_url", "image_url": {"url": "https://www.gstatic.com/webp/gallery3/1.png", "detail": "low"}},
        ],
    }],
)
print(resp.choices[0].message.content)
```

## Code: PDF (Anthropic)

```python
import anthropic, base64
client = anthropic.Anthropic()

with open("doc.pdf", "rb") as f:
    pdf_b64 = base64.standard_b64encode(f.read()).decode()

resp = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=4096,
    messages=[{
        "role": "user",
        "content": [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64}},
            {"type": "text", "text": "Summarize this document."},
        ],
    }],
)
```

## Production concerns

- **Latency:** Image inputs add 200-1000ms to TTFT depending on size.
- **Cost:** A single 4K image can cost more than 1000 output tokens. Resize before sending. Image tokens land inside `prompt_tokens` — segment them in billing (OpenAI breaks out image detail in usage details) or vision spend silently dominates.
- **Failure modes:** OCR quality on scanned PDFs varies; pre-extract text with `pymupdf` or `unstructured` for reliability. Multi-page PDFs multiply per-page image cost — a 30-page scanned PDF is 30 images' worth of tokens even when the question targets one page; retrieve the right pages first (see `03-rag/07-multimodal-rag.md`).
- **Security:** Vision models can read text in images — including screenshots of internal dashboards. Sanitize. And treat pasted screenshots in enterprise chat tools as the leak vector they are.

## Anti-patterns

- ❌ **Sending full-resolution images.** Resize to ≤1024px on the long edge.
- ❌ **Using OCR-then-LLM when the model supports PDFs natively.** You lose layout context.
- ❌ **Ignoring image token cost in your billing dashboard.** Vision can dominate cost silently.

## References

- [OpenAI vision](https://platform.openai.com/docs/guides/vision) — verified 2026-10-20
- [Anthropic vision](https://docs.anthropic.com/en/docs/build-with-claude/vision) — verified 2026-10-20
- [Anthropic PDF support](https://docs.anthropic.com/en/docs/build-with-claude/pdf) — verified 2026-10-20
