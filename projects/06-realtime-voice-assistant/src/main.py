"""Realtime voice assistant — VAD + turn-taking state machine over mock audio.

Encodes 11-realtime-voice/03: energy VAD with silence_duration end-of-turn,
barge-in on speech while model speaks, cancelled-audio accounting (cancel
ratio = UX health metric). Frame-level, deterministic, testable."""
from __future__ import annotations

from dataclasses import dataclass, field

SPEECH, SILENCE = 1, 0


@dataclass
class VoiceSession:
    silence_duration_ms: int = 500
    max_cancelled_audio_s: float = 5.0
    state: str = "listening"  # listening | model_speaking
    _silence_run_ms: int = field(default=0, init=False)
    _had_speech: bool = field(default=False, init=False)
    delivered_s: float = field(default=0.0, init=False)
    cancelled_s: float = field(default=0.0, init=False)

    def on_frame(self, is_speech: bool, frame_ms: int = 30) -> str | None:
        """Feed one VAD frame; returns 'end_of_turn' | 'barge_in' | None."""
        if self.state == "model_speaking" and is_speech:
            self.state = "listening"
            self.cancelled_s += 1.0  # in-flight audio discarded unseen
            self._silence_run_ms, self._had_speech = 0, False
            return "barge_in"
        if is_speech:
            self._had_speech, self._silence_run_ms = True, 0
            return None
        if self._had_speech:
            self._silence_run_ms += frame_ms
            if self._silence_run_ms >= self.silence_duration_ms:
                self._had_speech, self._silence_run_ms = False, 0
                return "end_of_turn"
        return None

    def model_starts(self) -> None:
        self.state = "model_speaking"

    def model_finishes(self, spoken_s: float) -> None:
        self.state = "listening"
        self.delivered_s += spoken_s

    @property
    def cancel_ratio(self) -> float:
        total = self.delivered_s + self.cancelled_s
        return self.cancelled_s / total if total else 0.0
