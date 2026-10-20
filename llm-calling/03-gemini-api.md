# Google Gemini API

> **Level:** BEG · **Last verified:** 2026-10-20 · **Sources:** [Gemini API Docs](https://ai.google.dev/gemini-api/docs)

## Why this matters

Gemini is the third frontier pillar. Its differentiators: very long context, strong multimodal (including native audio and video), a generous free tier, and tight integration with Vertex AI for enterprise. Note the September 2026 change: Google limited new-project access to the Gemini 2.5 generation and directs new work to the 3.x line (3.5 Flash-Lite, 3.8 Flash, 3.1 Pro).

## Core concepts

- **`generate_content`** — the unified entry point. Takes a list of `Content` objects (text, images, audio, video).
- **System instructions** — separate parameter, similar to Anthropic.
- **Model tiers** — 3.5 Flash-Lite ($0.30/$2.50 per 1M), 3.8 Flash ($0.75/$3.75), 3.1 Pro ($2/$12; higher beyond 200K input). The Flash line is the volume workhorse; Pro is the deep-reasoning tier.
- **Context caching** — explicit `cached_content` objects for reused corpora; cache storage bills per token-hour plus cheaper read pricing.
- **Thinking budgets** — `thinking_config` controls how much the model reasons before answering; dial it down for latency.
- **Vertex AI** — Google Cloud's hosted Gemini with VPC, IAM, and enterprise compliance.

## Code: minimal chat

```python
from google import genai
client = genai.Client()  # reads GOOGLE_API_KEY / GOOGLE_CLOUD_PROJECT

resp = client.models.generate_content(
    model="gemini-3.8-flash",
    contents="Summarize the KV-cache in one sentence.",
)
print(resp.text)
```

## Multimodal in one call

```python
from google.genai import types

resp = client.models.generate_content(
    model="gemini-3.8-flash",
    contents=[
        types.Part.from_text("What's in this image?"),
        types.Part.from_bytes(data=open("photo.jpg", "rb").read(), mime_type="image/jpeg"),
    ],
)
```

## Production concerns

- **Latency:** The Flash line is competitive with other vendors' small tiers on TTFT; use `thinking_config` to trim reasoning latency.
- **Cost:** Free tier (rate-limited) and paid tier. Long-context requests get expensive fast — Pro doubles its rate beyond 200K input tokens.
- **Failure modes:** Safety filters can be aggressive; check `prompt_feedback` in the response.
- **Security:** For HIPAA/PCI workloads, use Vertex AI, not the AI Studio API.

## Anti-patterns

- ❌ **Stuffing the whole corpus into every request** — slow, expensive, and recall degrades. Retrieve instead; see `rag/08-long-context-vs-rag.md`.
- ❌ **Mixing AI Studio API keys with Vertex auth.** Pick one path per environment.
- ❌ **Starting new projects on Gemini 2.5.** Access is limited to legacy users as of Sept 2026; build on the 3.x line.

## Decision framework

| Situation | Use |
|-----------|-----|
| High-volume classification/extraction | 3.5 Flash-Lite ($0.30/$2.50) |
| Default agentic + multimodal workhorse | 3.8 Flash ($0.75/$3.75) |
| Hard reasoning / long-context analysis | 3.1 Pro ($2/$12, 2x past 200K) |
| Reused corpora across many requests | Context caching (`cached_content`) |
| Enterprise compliance (HIPAA/PCI) | Vertex AI endpoint |

## References

- [Gemini API reference](https://ai.google.dev/gemini-api/docs) — verified 2026-10-20
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) — verified 2026-10-20
- [Vertex AI Gemini](https://cloud.google.com/vertex-ai/generative-ai/docs) — verified 2026-10-20
