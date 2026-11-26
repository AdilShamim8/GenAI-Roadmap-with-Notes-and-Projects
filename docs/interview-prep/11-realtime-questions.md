# Realtime Voice — Interview Questions

> **Rung:** [11-realtime-voice](../../11-realtime-voice/01-openai-realtime-api.md) · **Last verified:** 2026-10-20

## Q1 — Why is speech-to-speech architecture more than "ASR + LLM + TTS glued together"?

**Model answer:** The glued pipeline is three models serialized — each adds latency (1.5-3s total typical) and each *discards information*: ASR strips prosody and tone (the model literally cannot hear that the user sounded frustrated), TTS invents the affect back. Speech-to-speech consumes and emits audio tokens natively: one model, one pass, ~500-800ms, and the model *hears* tone — it can respond to hesitation, speed up when interrupted, match energy. That perceptual richness is the product argument beyond raw speed.

The trade you accept: **inspectability**. In the pipeline you can read the transcript before it's spoken, filter it, branch on it. In native audio the audio *is* the output — text-level output filters don't see it until the transcript event. High-stakes voice deployments manage this with session configuration (topic restrictions, tool-gated actions) rather than output filtering.

**Senior note:** VAD time is the largest *controllable* term in the ~700ms budget — the model's 400ms is mostly fixed; turn-detection silence_duration_ms is what you tune. This is why voice teams obsess over VAD: it's the tunable third of perceived responsiveness.

## Q2 — Users complain your voice assistant "interrupts itself." Diagnose

**Model answer:** Self-interruption is almost always an echo problem: the mic hears the assistant's own speaker output, the VAD registers it as speech, barge-in fires, playback cancels. Check **AEC first** — without acoustic echo cancellation before VAD, every deployment self-triggers, especially on speakerphone. If AEC is present: check the *threshold* (background noise — HVAC, music — false-triggers energy VADs; Silero-class neural VADs resist this far better) and whether another person's speech in the room is triggering (that's a *speaker policy* problem — who should the agent listen to? — which is diarization territory, not VAD tuning).

Also verify the interruption *semantics*: client-side, on speech_started you must duck playback immediately (server cancellation takes a round-trip; local duck is instant).

**Senior note:** know the error asymmetry — cutting off a mid-thought user feels broken immediately and gets remembered; 300ms extra patience feels like thinking. Bias patient, except after clear completions — which is the argument for *semantic* turn detection (provider-side models that distinguish "I want to book..." from "I want to book a table for two.") over pure silence-timers. The production sweet spot is hybrid: instant dumb client VAD for barge-in detection + smart semantic VAD for turn completion.

## Q3 — What's different about cost and UX economics in voice?

**Model answer:** Cost is per *audio token* (or per-second), and the shape differs from text: audio tokens are expensive relative to text tokens, which is why cached audio input matters enormously — keep the session prefix stable (same session config, same voice, append-only) and cached input runs ~80x cheaper on OpenAI's realtime models (~$0.05/min all-in with caching vs multiples without). Session-config drift on reconnect silently reprices you by invalidating the prefix.

The UX-specific economics: **cancelled audio is spent money** — every interruption cancels a response that already generated tokens. Heavy-interruption traffic can push 20-40% of output spend into unheard audio; measure *cancel ratio* (cancelled/delivered) — high values mean the agent talks too long, a product problem showing up as a cost symptom. Fixes: shorter sentence pacing (cheaper to cancel), tool-fill during silent tool calls (a 5-second silent lookup feels broken; let the model speak a holding line).

**Senior note:** billing model differences between vendors (per-audio-token vs per-token-plus-per-audio-second) mean per-minute comparisons lie — model *your* conversation shape (turn lengths, interruptions) through both calculators before choosing. And voice is an authentication surface: "cancel my account" spoken by someone else in the room has no text filter in the loop to catch it — destructive actions need spoken confirmation, and the identity story is the session's, not the voice's.

## Q4 — Design a voice agent for phone-based customer support. Key decisions?

**Model answer:** (1) **Transport:** telephony means SIP/PSTN termination — the API's SIP interface or a gateway; WebRTC is for apps, not phone numbers. (2) **Turn detection:** phone audio is narrowband, noisy, with no AEC on the *caller's* side (their environment bleeds in) — bias patient on silence timers, prefer semantic turn detection, and expect background-speech false triggers. (3) **Mode/pricing:** support flows are often read-heavy and script-shaped — DSP mode (cheeper, higher latency) can fit IVR-replacement use; conversational support wants native audio (DSP's prosody loss reads as "robot" to callers who are already frustrated). (4) **Fallback and containment:** phone users can't see error states — every failure needs a spoken path ("let me connect you to a specialist") and a DTMF/menu fallback for the cases where voice fails. (5) **Compliance:** call recording disclosures and audio retention policy — telephony recording is regulated territory (two-party consent states), and your audio logs are PII concentrates.

**Senior note:** the interruption contract on phones is sharper — callers *will* talk over the agent (it's normal phone behavior, not rudeness), so barge-in isn't optional polish; it's core UX. And the hold-time pattern: telephony has decades of expectations (music, position-in-queue, callbacks) that a voice agent either honors or pays for in abandonment.
