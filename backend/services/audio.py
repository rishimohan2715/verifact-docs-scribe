import os
import subprocess
import uuid
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def generate_audio_filename(original_filename: Optional[str], now: Optional[datetime] = None) -> str:
    """
    Builds a unique on-disk filename for an uploaded consultation recording.

    The timestamp component is only for readability when browsing storage/audio/ —
    it is NOT relied on for uniqueness, since two recordings started in the same
    second would otherwise silently overwrite each other's audio file (a real
    incident: a consultation's stored transcript/duration ended up describing a
    completely different, later recording that had landed on the same path).
    The random suffix is what actually guarantees uniqueness.
    """
    ext = "webm"
    if original_filename:
        _, orig_ext = os.path.splitext(original_filename)
        if orig_ext:
            ext = orig_ext.lstrip(".")

    timestamp = (now or datetime.utcnow()).strftime("%Y%m%d_%H%M%S")
    unique_suffix = uuid.uuid4().hex[:8]
    return f"{timestamp}_{unique_suffix}.{ext}"


def normalize_audio_ffmpeg(input_path: str, output_path: Optional[str] = None) -> str:
    """
    Normalizes any input audio file (WEBM, M4A, OGG, MP3, WAV) to a standard
    16kHz mono 16-bit PCM WAV file using FFmpeg before Whisper / VAD processing.
    """
    if not output_path:
        base_name, _ = os.path.splitext(input_path)
        output_path = f"{base_name}_16k.wav"

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        output_path
    ]

    try:
        logger.info(f"Running FFmpeg normalization: {input_path} -> {output_path}")
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        logger.warning(f"FFmpeg failed ({e.stderr.decode() if e.stderr else e}). Returning original path.")
        return input_path
    except FileNotFoundError:
        logger.warning("FFmpeg command not found on PATH. Proceeding with raw audio input.")
        return input_path
