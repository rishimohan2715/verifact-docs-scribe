"""
Tests for services.audio.generate_audio_filename.

Context: filenames used to be `{timestamp-to-the-second}.{ext}` with no other
entropy. Two recordings started in the same second silently overwrote each
other's saved audio on disk — this was caught by comparing a consultation's
stored transcript/duration against the audio file actually sitting at its
audio_path, which turned out to hold a completely different, longer recording.
"""
from datetime import datetime

from services.audio import generate_audio_filename


def test_same_second_uploads_never_collide():
    same_instant = datetime(2026, 8, 7, 17, 12, 27)
    filenames = {generate_audio_filename("recording.webm", now=same_instant) for _ in range(500)}
    assert len(filenames) == 500, "two uploads landing in the same second must not produce the same filename"


def test_extension_is_derived_from_the_uploaded_filename():
    name = generate_audio_filename("consultation_recording.mp4")
    assert name.endswith(".mp4")


def test_missing_extension_falls_back_to_webm():
    name = generate_audio_filename("consultation_recording")
    assert name.endswith(".webm")


def test_no_uploaded_file_falls_back_to_webm():
    name = generate_audio_filename(None)
    assert name.endswith(".webm")


def test_filename_stays_human_readable_with_a_timestamp_prefix():
    fixed_time = datetime(2026, 8, 7, 17, 12, 27)
    name = generate_audio_filename("clip.webm", now=fixed_time)
    assert name.startswith("20260807_171227_")
    # timestamp_suffix.ext, suffix is an 8-char hex token
    stem, ext = name.rsplit(".", 1)
    timestamp_part, suffix = stem.rsplit("_", 1)
    assert timestamp_part == "20260807_171227"
    assert len(suffix) == 8
    assert ext == "webm"
