# VAD & Interruption Handling

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [Silero VAD](https://github.com/snakers4/silero-vad), [OpenAI Realtime VAD](https://developers.openai.com/api/docs/guides/voice-activity-detection)

## Why this matters

Voice UX lives or dies on VAD (voice activity detection) and interruption handling. Get it wrong and the model either talks over the user (bad) or pauses awkwardly at every breath (also bad). This is the part of voice agents that takes the most tuning. The expert framing: VAD is a *turn-taking policy encoded as signal processing*. Human turn-taking is predictive — we hand off conversations on grammar, prosody, and gaze, not just silence — and every VAD parameter is a compromise trying to approximate that with energy/feature thresholds. The tuning pain everyone reports is real: you're approximating a social behavior with a DSP pipeline.

## Core concepts

### The VAD tradeoff

| Setting | Effect |
|---------|--------|
| **Low threshold** | Catches quiet speech; false-triggers on background noise |
| **High threshold** | Misses quiet speech; better in noisy environments |
| **Short silence_duration_ms** | Quick turn-taking; cuts off users who pause |
| **Long silence_duration_ms** | Patient; feels slow |

Typical 2026 defaults: threshold 0.5, silence_duration_ms 500ms.

The two error classes are *asymmetric in user perception*: cutting off a mid-thought user (short silence → premature end-of-turn) feels broken immediately and gets remembered; an extra 300ms of patience feels like the agent "thinking." When in doubt, bias patient — *except* in the one place impatience pays: responsiveness after the user clearly finished (declarative sentences, falling prosody). Which is the argument for semantic turn detection (below).

### Beyond energy: the VAD hierarchy

1. **Energy/feature VAD** (webrtcvad, Silero): is there speech-shaped sound in this frame? Fast, dumb, no language awareness. Silero is the modern pick — a small neural net, far more robust to non-speech noise (music, HVAC, keyboard) than classic energy detectors.
2. **Semantic turn detection** (provider-side, e.g. OpenAI's semantic_vad): does this *sound like a completed thought*? Uses the model's language understanding to distinguish "I want to book..." (continuing) from "I want to book a table for two." (done). Eliminates the breath-cutoff / slow-response dilemma — the two errors energy VAD trades between — because it doesn't have to guess from silence.
3. **Hybrid**: client energy VAD for barge-in *detection* (must be instant, can be dumb) + provider semantic VAD for turn *completion* (can take 200ms, should be smart). This is the production sweet spot: instant interruption response, intelligent handoff.

### Interruption handling

When the user starts speaking while the model is talking:

1. Stop playing model audio immediately.
2. Cancel the in-flight model generation.
3. Discard any buffered model audio.
4. Start listening for the new turn.

Step 3 has a subtlety: the *discarded* audio and the cancelled response's *text* remain in the session context on some providers — the model "remembers what it was saying" when interrupted, which is usually desirable (the user's interruption often refers to it: "no, the *second* one"). Know your provider's semantics here; a session where interrupted content vanishes entirely produces agents that lose the thread of their own half-sentences.

### Double-talk

User talks *while* model is talking (not after). Harder case. Options:

- **Ignore** — let model finish, then respond to user's interrupt.
- **Stop model** — model stops mid-sentence, listens to user.
- **Barge-in** — model acknowledges ("yes?") and continues after user finishes.

The "right" answer depends on context. Customer support: stop model. Casual chat: ignore.

Double-talk is also where *false* interruptions bite: background speech (TV, another person) triggers barge-in and the agent loses its sentence to nobody. The defenses stack: AEC (kill the echo of its own voice), directional mics / beamforming where hardware allows, and a *minimum-energy floor* for barge-in (louder than ambient, not just any speech) — interruption should require intent-shaped audio, not incidental noise.

### The barge-in interaction with generation economics

Every cancelled response still *generated* tokens up to the cancellation — you paid for audio the user never heard. Heavy-interruption traffic (impatient users, chatty interfaces) can push 20-40% of output spend into cancelled audio. Mitigations: shorter sentence-pacing (the model emits smaller complete units — cheaper to cancel), and measuring *cancel ratio* (cancelled/delivered audio) as a UX-health metric: high cancel ratio means your agent talks too much or too long — a *product* problem showing up as a *cost* symptom.

## Code: client-side VAD

```python
import webrtcvad, collections

vad = webrtcvad.Vad(3)  # aggressiveness 0-3
frame_duration_ms = 30

def vad_audio_stream(mic_stream):
    '''Yields (frame_bytes, is_speech) tuples.'''
    frame_size = 16000 * frame_duration_ms // 1000  # 16kHz mono
    frames = collections.deque(maxlen=int(1000 / frame_duration_ms))  # 1 sec window

    async for frame in mic_stream:
        is_speech = vad.is_speech(frame, 16000)
        frames.append(is_speech)

        # Detect end-of-utterance: 500ms of silence after speech
        if any(frames) and not is_speech and len(frames) >= int(500 / frame_duration_ms):
            if not any(list(frames)[-int(500 / frame_duration_ms):]):
                yield frame, "end_of_utterance"
                frames.clear()
                continue

        yield frame, "speech" if is_speech else "silence"
```

## Code: interruption handling

```python
async def realtime_session(ws):
    model_speaking = False

    async def receive():
        nonlocal model_speaking
        async for msg in ws:
            event = json.loads(msg)
            if event["type"] == "response.audio.delta":
                model_speaking = True
                speaker.play(base64.b64decode(event["delta"]))
            elif event["type"] == "response.done":
                model_speaking = False

    async def send_audio():
        async for frame, state in vad_audio_stream(mic_stream()):
            await ws.send(audio_buffer_msg(frame))
            if state == "end_of_utterance" and model_speaking:
                # User interrupted
                await ws.send(json.dumps({"type": "response.cancel"}))
                speaker.stop()
                model_speaking = False

    await asyncio.gather(receive(), send_audio())
```

### Model choice

Prefer **Silero VAD** as your local default — tiny, accurate, actively maintained. `py-webrtcvad` is unmaintained (dormant since ~2019) and builds break on newer Pythons; treat it as legacy (the demo code above is shape-illustrative). Provider-side turn detection (`server_vad` / semantic options on OpenAI) removes the local VAD entirely if you accept its tuning.

Also: without **acoustic echo cancellation**, your mic hears your own speaker output and false-triggers barge-in. AEC before VAD, always.

## Production concerns

- **Latency:** Client-side VAD adds 20–50ms. Worth it for control.
- **Cost:** None — except the cancelled-audio economics above.
- **Failure modes:** (1) background music triggers VAD — Silero-class neural VADs resist this far better than energy VADs; (2) multiple speakers confuse it — speaker diarization is a separate problem (who should the agent *listen to*?), and multi-party voice agents need an explicit speaker policy, not just VAD; (3) threshold drift across environments — car vs office vs kitchen; tune per deployment profile and expose the profile in config, not a single global.
- **Security:** VAD has no security implications — but *always-on* microphones do: local VAD with a hard mute (hardware or OS level) is the privacy story your users actually care about; cloud-streaming-everything is not.

## Anti-patterns

- ❌ **Trusting server VAD blindly.** Tune for your environment.
- ❌ **No interruption handling.** Model talks over user.
- ❌ **Cancelling model too aggressively.** User pauses; model stops mid-sentence.
- ❌ **No AEC.** The agent interrupts itself; you'll chase the bug for days.
- ❌ **Energy-only VAD in 2026.** Silero-class neural VAD is small, fast, free — use it.
- ❌ **One VAD profile for all environments.** Car ≠ office; profile per deployment.

## References

- [Silero VAD](https://github.com/snakers4/silero-vad) — verified 2026-10-20
- [OpenAI Realtime: VAD](https://developers.openai.com/api/docs/guides/voice-activity-detection) — verified 2026-10-20
- [py-webrtcvad (legacy)](https://github.com/wiseman/py-webrtcvad) — verified 2026-10-20
