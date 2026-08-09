"""
Tests for services.transcription.transcribe_audio.

The real faster-whisper model is never loaded here — get_cached_whisper_model
is patched with a fake model whose .transcribe() yields plain segment objects,
so these tests run in milliseconds with no model weights on disk.
"""
from dataclasses import dataclass
from unittest.mock import patch

from services.transcription import transcribe_audio


@dataclass
class FakeSegment:
    text: str
    start: float
    end: float


class FakeWhisperModel:
    def __init__(self, segments):
        self._segments = segments

    def transcribe(self, *args, **kwargs):
        return iter(self._segments), object()


# The exact turn-by-turn content recovered from a real recording during debugging
# (backend/storage/audio/20260807_171227.webm), used as a golden-path regression:
# the old alternate-only-in-AUTO-mode logic mislabeled every one of these 19
# segments "DOCTOR" because the app's default first-speaker mode is "DOCTOR".
REAL_CONSULTATION_SEGMENTS = [
    FakeSegment("I'm not a state doctor. I'm having some trouble with my breathing.", 0.43, 10.41),
    FakeSegment("You can ask me what are you need?", 10.41, 13.10),
    FakeSegment("So when did this issue actually start, Mr. Ravine?", 13.10, 18.27),
    FakeSegment("I'd say about a week ago, but it got worse in the last two days.", 18.27, 26.19),
    FakeSegment("And for how long have you been having these issues?", 26.19, 32.94),
    FakeSegment("It's been a while, breathing trouble, often on for maybe two years", 32.94, 40.75),
    FakeSegment("This time it hasn't.", 40.75, 44.02),
    FakeSegment("Okay, and what are your symptoms like?", 44.02, 47.79),
    FakeSegment("Tide chest, whistling sound when I breathe, especially at night.", 47.79, 52.59),
    FakeSegment("Short breaths and coughing. It feels heavier at night.", 52.59, 59.22),
    FakeSegment("And when did these issues actually spike up?", 59.22, 65.10),
    FakeSegment("Two days ago. It's suddenly worsened.", 65.10, 69.09),
    FakeSegment("I felt more wheezing, more tightness, harder to get a full breath.", 69.09, 76.94),
    FakeSegment("Okay, tell me one thing. How long have you noticed that these issues spike up?", 76.94, 83.26),
    FakeSegment("What kind of environment do you work in on staying?", 83.26, 86.78),
    FakeSegment("I stay in a shared apartment, sometimes dusty, and there's often smoke", 86.78, 94.22),
    FakeSegment("nearby traffic or cooking fires. It gets worse.", 94.22, 98.22),
    FakeSegment("Swenier, feel stuffy.", 98.22, 100.77),
    FakeSegment("All right.", 100.77, 102.77),
]


def _patched(segments):
    return patch(
        "services.transcription.get_cached_whisper_model",
        return_value=FakeWhisperModel(segments),
    )


def test_diarization_reconstructs_a_real_multi_turn_conversation(tmp_path):
    audio_file = tmp_path / "fake.webm"
    audio_file.write_bytes(b"not real audio, transcribe() is mocked")

    with _patched(REAL_CONSULTATION_SEGMENTS):
        result = transcribe_audio(str(audio_file), first_speaker="DOCTOR", model_name="base")

    speakers = [seg["speaker"] for seg in result["segments"]]
    assert len(result["segments"]) == 19
    assert set(speakers) == {"DOCTOR", "PATIENT"}
    # Not every segment collapsed to one speaker — the bug this regression-tests for.
    assert speakers.count("DOCTOR") > 1
    assert speakers.count("PATIENT") > 1
    # Spot-check a few turns explicitly rather than asserting the entire 19-item sequence,
    # so this test documents intent without duplicating test_speaker_attribution.py.
    assert result["segments"][0]["speaker"] == "PATIENT"  # "I'm having trouble with my breathing"
    assert result["segments"][2]["speaker"] == "DOCTOR"  # ends in "?"
    assert result["segments"][3]["speaker"] == "PATIENT"  # "I'd say about a week ago..."


def test_diarization_alternates_for_patient_first_mode_too():
    """
    Before the fix, transcribe_audio only toggled speakers when first_speaker == "AUTO";
    "PATIENT Speaks First" and "DOCTOR Speaks First" never alternated at all.
    """
    segments = [
        FakeSegment("Doctor, I have severe chest pain radiating to my left arm.", 0.0, 3.0),
        FakeSegment("How long have you had this pain?", 3.0, 6.0),
        FakeSegment("About an hour now.", 6.0, 8.0),
    ]
    with _patched(segments):
        result = transcribe_audio("irrelevant.webm", first_speaker="PATIENT", model_name="base")

    speakers = [seg["speaker"] for seg in result["segments"]]
    assert speakers == ["PATIENT", "DOCTOR", "PATIENT"]


def test_segment_timestamps_and_time_string_are_preserved():
    segments = [FakeSegment("Two days ago.", 65.1, 69.09)]
    with _patched(segments):
        result = transcribe_audio("irrelevant.webm", first_speaker="AUTO", model_name="base")

    seg = result["segments"][0]
    assert seg["start"] == 65.1
    assert seg["end"] == 69.09
    assert seg["time"] == "01:05"


def test_empty_audio_falls_back_to_no_speech_message():
    with _patched([]):
        result = transcribe_audio("irrelevant.webm", first_speaker="DOCTOR", model_name="base")

    assert result["full_transcript"] == "No clear clinical dialogue detected in the audio file."
    assert len(result["segments"]) == 1
    assert result["segments"][0]["text"] == "No clear speech detected in recorded audio."


def test_whisper_blank_segments_are_skipped_not_counted_as_turns():
    segments = [
        FakeSegment("  ", 0.0, 1.0),  # whitespace-only, e.g. a VAD false positive
        FakeSegment("Actual speech here.", 1.0, 3.0),
    ]
    with _patched(segments):
        result = transcribe_audio("irrelevant.webm", first_speaker="AUTO", model_name="base")

    assert len(result["segments"]) == 1
    assert result["segments"][0]["text"] == "Actual speech here."


def test_model_crash_falls_back_gracefully_instead_of_500ing():
    with patch("services.transcription.get_cached_whisper_model", side_effect=RuntimeError("model load failed")):
        result = transcribe_audio("irrelevant.webm", first_speaker="DOCTOR", model_name="base")

    assert "could not be decoded" in result["full_transcript"]
    assert len(result["segments"]) == 1
