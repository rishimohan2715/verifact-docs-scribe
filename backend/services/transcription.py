import os
import json
import logging
from typing import Dict, Any, List
from services.audio import normalize_audio_ffmpeg

logger = logging.getLogger(__name__)

# Global Faster-Whisper Model Cache in RAM to prevent re-loading weights from disk on every request
_CACHED_WHISPER_MODELS: Dict[str, Any] = {}

def get_cached_whisper_model(model_name: str = "base"):
    """
    Retrieves or loads the local Faster-Whisper (CTranslate2 INT8) model once into RAM.
    """
    global _CACHED_WHISPER_MODELS
    if model_name not in _CACHED_WHISPER_MODELS:
        from faster_whisper import WhisperModel
        logger.info(f"Loading CTranslate2 Faster-Whisper model '{model_name}' into RAM cache...")
        _CACHED_WHISPER_MODELS[model_name] = WhisperModel(model_name, device="cpu", compute_type="int8")
    return _CACHED_WHISPER_MODELS[model_name]


# Faster-Whisper's VAD emits contiguous segments (every inter-segment gap is 0.0s), so
# silence length gives no signal about who is talking. Fall back to the linguistic shape of
# a consultation: the clinician asks the questions, the patient reports their own symptoms.
_PATIENT_MARKERS = (
    "i'm ", "i've ", "i'd ", "i feel", "i felt", "i have", "i had", "i get", "i stay",
    "i can't", "i cannot", "i was", "my ", "doctor,",
)
_DOCTOR_MARKERS = (
    "how long", "when did", "tell me", "have you", "are you", "do you", "did you",
    "let me", "we are", "we will", "on a scale", "examination", "i see.",
    "alright", "all right",
)


def _infer_speaker(text: str, previous_speaker: str, previous_was_question: bool) -> str:
    """
    Heuristic speaker attribution for a single transcript segment.

    Ordered strongest-cue-first: an explicit question is nearly always the clinician,
    first-person symptom language is the patient, and the segment right after a question
    is the answer to it. Anything with no cue at all is treated as a continuation of the
    current turn rather than forcing a switch, which is what breaks up long sentences that
    Whisper splits across two segments.
    """
    stripped = text.strip()
    lowered = f" {stripped.lower()} "

    if stripped.endswith("?"):
        return "DOCTOR"
    if any(marker in lowered for marker in _PATIENT_MARKERS):
        return "PATIENT"
    if previous_was_question:
        return "PATIENT"
    if any(marker in lowered for marker in _DOCTOR_MARKERS):
        return "DOCTOR"
    return previous_speaker


def transcribe_audio(audio_path: str, first_speaker: str = "PATIENT", model_name: str = "base") -> Dict[str, Any]:
    """
    Ultra-fast local audio transcription:
    1. Normalizes audio via FFmpeg to 16kHz mono WAV if available.
    2. Uses CTranslate2 Faster-Whisper INT8 model with beam_size=1 and Silero VAD for 10x speedup.
    """
    normalized_path = normalize_audio_ffmpeg(audio_path)

    full_transcript = ""
    segments = []

    try:
        model = get_cached_whisper_model(model_name)

        raw_segments_generator, info = model.transcribe(
            normalized_path,
            language="en",
            beam_size=1,
            temperature=0.0,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        # The configured first speaker only seeds the opening turn; per-segment cues take over
        # from there, and the reviewer can still correct any line in the UI.
        current_speaker = first_speaker if first_speaker in ["DOCTOR", "PATIENT"] else "DOCTOR"
        previous_was_question = False
        transcript_parts = []

        for seg in raw_segments_generator:
            seg_text = seg.text.strip()
            if not seg_text:
                continue

            # With no cue at all, _infer_speaker returns the running speaker, so the
            # configured first speaker naturally decides only the ambiguous opening turn.
            speaker = _infer_speaker(seg_text, current_speaker, previous_was_question)
            current_speaker = speaker
            previous_was_question = seg_text.endswith("?")

            transcript_parts.append(seg_text)
            start_t = seg.start
            end_t = seg.end

            min_val = int(start_t) // 60
            sec_val = int(start_t) % 60
            time_str = f"{min_val:02d}:{sec_val:02d}"

            segments.append({
                "speaker": speaker,
                "text": seg_text,
                "start": round(start_t, 2),
                "end": round(end_t, 2),
                "time": time_str
            })

        full_transcript = " ".join(transcript_parts)
        if not full_transcript:
            full_transcript = "No clear clinical dialogue detected in the audio file."
            segments = [
                {"speaker": current_speaker, "text": "No clear speech detected in recorded audio.", "start": 0.0, "end": 2.0, "time": "00:00"}
            ]

    except Exception as e:
        logger.warning(f"Local Faster-Whisper model error ({e}).")
        if not full_transcript:
            full_transcript = "Audio recording could not be decoded or contained no speech."
            segments = [
                {"speaker": "PATIENT", "text": "No clear audio recorded from microphone.", "start": 0.0, "end": 2.0, "time": "00:00"}
            ]

    return {
        "full_transcript": full_transcript,
        "segments": segments,
        "normalized_audio_path": normalized_path,
        "whisper_model": model_name
    }

