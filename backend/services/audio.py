import os
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)

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
