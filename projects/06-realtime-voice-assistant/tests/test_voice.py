import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import SILENCE, SPEECH, VoiceSession


def feed(sess, frames):
    events = []
    for f in frames:
        e = sess.on_frame(f == SPEECH)
        if e:
            events.append(e)
    return events


def test_end_of_turn_after_silence():
    s = VoiceSession(silence_duration_ms=150)
    ev = feed(s, [SPEECH] * 5 + [SILENCE] * 10)
    assert ev == ["end_of_turn"]


def test_no_end_of_turn_without_speech():
    s = VoiceSession()
    assert feed(s, [SILENCE] * 50) == []


def test_barge_in_cancels_and_resets():
    s = VoiceSession()
    feed(s, [SPEECH, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE, SILENCE])  # one turn
    s.model_starts()
    ev = feed(s, [SPEECH])
    assert ev == ["barge_in"]
    assert s.cancelled_s > 0 and s.state == "listening"


def test_cancel_ratio_tracks_health():
    s = VoiceSession()
    feed(s, [SPEECH] + [SILENCE] * 20)
    s.model_starts(); feed(s, [SPEECH])  # cancel 1s
    feed(s, [SPEECH] + [SILENCE] * 20)
    s.model_starts(); s.model_finishes(4.0)
    assert 0 < s.cancel_ratio < 1
