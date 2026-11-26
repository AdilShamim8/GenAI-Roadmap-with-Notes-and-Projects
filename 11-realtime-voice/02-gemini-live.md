# Gemini Live

> **Level:** ADV · **Last verified:** 2026-10-20

## Why this matters

Google's Gemini Live is the alternative realtime API. Different pricing model, tighter integration with Google Cloud, and — for some use cases — better latency on Android. The expert framing: the *interesting* difference from OpenAI Realtime isn't the vendor — it's the **modality surface**. Gemini Live is a realtime *multimodal* API (audio + text + images in and out during a live session), which makes it the natural home for voice-plus-camera use cases (show the agent what you're seeing) that a pure-audio realtime session can't express.

## Core concepts

### Differences from OpenAI Realtime

| Dimension | OpenAI Realtime | Gemini Live |
|-----------|-----------------|-------------|
| Transport | WebSocket | WebSocket |
| Pricing | Per audio minute | Per token + per audio sec |
| Voice options | 5 voices | Multiple, locale-aware |
| Tool calls | Yes | Yes |
| Multimodal output | Audio + text | Audio + text + images |
| Best for | Cross-platform | Android-first, Google Cloud shops |

The dimensions that actually drive the choice: **multimodal output** (Live can *show* — charts, diagrams, images mid-conversation; OpenAI Realtime speaks), **Android latency** (Google's device-stack integration gives Live an edge on Android clients where the audio path is shortest), and **Cloud gravity** (if your stack is Vertex/Google Cloud, Live's integration — auth, quotas, observability — is native rather than another vendor relationship).

### Connection lifecycle

Similar to OpenAI: open session → stream audio in → receive audio out → handle interruptions → close.

The protocol-level difference worth knowing: OpenAI's realtime protocol is *event-shaped* (typed server events on a session); Live's is *request-shaped* (BidiGenerateContent — bidirectional `content` messages over the stream, closer to the Gemini generateContent model with streaming added). Practically: your OpenAI event-handling code doesn't port — the concepts (session setup, audio in, audio out, interruption) map, the message names don't.

## Code: minimal Gemini Live client

```python
import asyncio, json, websockets, base64

async def gemini_live():
    url = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
    headers = {"Authorization": "Bearer YOUR_TOKEN"}

    async with websockets.connect(url, extra_headers=headers) as ws:
        # Configure
        await ws.send(json.dumps({
            "setup": {
                "model": "gemini-2.5-flash-native-audio",  # or gemini-2.5-flash-preview; use google-genai SDK live module for current IDs
                "generationConfig": {"responseModalities": ["AUDIO"]},  # proto fields are camelCase
            }
        }))

        async def send_audio():
            async for chunk in mic_stream():
                await ws.send(json.dumps({
                    "realtime_input": {"audio_chunks": [{"data": base64.b64encode(chunk).decode(), "mime_type": "audio/pcm"}]}
                }))

        async def receive():
            async for msg in ws:
                event = json.loads(msg)
                if "server_content" in event:
                    part = event["server_content"].get("model_turn", {}).get("parts", [{}])[0]
                    if "inline_data" in part:
                        speaker.play(base64.b64decode(part["inline_data"]["data"]))

        await asyncio.gather(send_audio(), receive())
```

### Native audio vs DSP

The Live API has two audio modes: **DSP-based** (audio → text → model → text → audio; cheaper, works on any model) and **native audio** (end-to-end speech; lower latency, more natural prosody, billed per audio token). Price both per use case. Also prefer the official `google-genai` SDK's Live module over raw WebSockets unless you need protocol-level control.

The mode decision, expertly: DSP mode is the *pipeline* architecture from `01-openai-realtime-api.md` hosted server-side — it's cheaper because text tokens cost less than audio tokens and the ASR/TTS steps are commodity-priced, at the cost of pipeline latency and prosody loss. Native audio is the speech-to-speech model. The rule of thumb: **DSP for read-heavy, single-turn, cost-sensitive flows (IVR replacement, high-volume phone trees); native for conversational products where the sub-second, hears-your-tone experience is the product.** And the gap is auditable — run both modes on the same conversation set and listen to the difference; it's usually obvious within three turns.

### Context-window management (Live's distinctive feature)

Live sessions can run long — an ambient assistant hears *hours* of audio. Gemini Live's session mechanism supports explicit context management: the session carries a rolling context, and the API surfaces context-usage signals so the client can decide when to reset or compact. This matters because unlike text (where you'd compact per `02-context-engineering/03-context-distillation.md`), an ambient *audio* stream never pauses for you — context management has to happen without breaking the live conversation. The pattern: periodic session refresh at natural boundaries (task complete, long silence), preserving a distilled carry-over.

## Production concerns

- **Latency:** Competitive with OpenAI; on Android with Google's client stack, often ahead.
- **Cost:** Token-based; can be cheaper for short turns — but the pricing *shape* differs from OpenAI's per-audio-token model, so cost comparisons must be per-conversation, not per-minute: run a 50-conversation sample through both calculators with your real turn lengths; published per-minute figures assume a "typical" conversation that isn't yours.
- **Failure modes:** (1) locale-specific voices may not be available everywhere — pin voice by locale and have a fallback voice per market; (2) model-ID churn in the `v1beta` surface — the native-audio model IDs move as they graduate previews; pin IDs and watch the changelog (the SDK's Live module abstracts this — one reason to prefer it).
- **Security:** Don't log audio. Live's multimodality adds: a live *camera* feed is continuous PII (faces, screens, documents) — a video session's data-handling review is materially stricter than audio-only, and the retention question for streamed video deserves its own policy line.

## Anti-patterns

- ❌ **Mixing OpenAI and Gemini patterns.** Different APIs, different message shapes.
- ❌ **No interruption handling.**
- ❌ **Logging raw audio** (or camera frames).
- ❌ **Choosing on published per-minute prices.** Model the conversation *shape* you actually serve.
- ❌ **DSP mode for conversational products.** The latency and prosody gap is the product; don't save 60% to ship the wrong experience.
- ❌ **Unbounded ambient sessions.** Use the context-management signals; compact at natural boundaries.

## References

- [Gemini Live API](https://ai.google.dev/gemini-api/docs/live) — verified 2026-10-20
- [Vertex AI Gemini Live](https://cloud.google.com/vertex-ai/generative-ai/docs) — verified 2026-10-20
