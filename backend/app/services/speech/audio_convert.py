from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

from app.core.exceptions import TranscriptionFailedError

logger = logging.getLogger(__name__)

# Formats Hugging Face Whisper / soundfile handle reliably.
_WAV_MAGIC = b"RIFF"
_SAFE_FOR_SOUNDFILE = {"audio/wav", "audio/x-wav", "audio/wave", "audio/flac"}


def looks_like_wav(audio_bytes: bytes) -> bool:
    return len(audio_bytes) >= 12 and audio_bytes[:4] == _WAV_MAGIC and audio_bytes[8:12] == b"WAVE"


def needs_wav_conversion(mime_type: str | None, filename: str | None, audio_bytes: bytes) -> bool:
    if looks_like_wav(audio_bytes):
        return False
    raw = (mime_type or "").split(";")[0].strip().lower()
    if raw in _SAFE_FOR_SOUNDFILE:
        # Claimed wav/flac but bytes are not — still convert.
        return not looks_like_wav(audio_bytes) if "wav" in raw else False
    suffix = ""
    if filename and "." in filename:
        suffix = filename.rsplit(".", 1)[-1].lower()
    if suffix in {"wav", "wave", "flac"} and looks_like_wav(audio_bytes):
        return False
    return True


def _input_suffix(mime_type: str | None, filename: str | None, audio_bytes: bytes) -> str:
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in {"webm", "m4a", "mp4", "mp3", "ogg", "oga", "aac", "3gp", "caf", "wav", "flac", "amr"}:
            return f".{ext}"
    raw = (mime_type or "").split(";")[0].strip().lower()
    mapping = {
        "audio/webm": ".webm",
        "video/webm": ".webm",
        "audio/mp4": ".m4a",
        "audio/m4a": ".m4a",
        "video/mp4": ".mp4",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/ogg": ".ogg",
        "audio/aac": ".aac",
        "audio/amr": ".amr",
        "audio/3gpp": ".3gp",
        "audio/flac": ".flac",
        "audio/wav": ".wav",
    }
    if raw in mapping:
        return mapping[raw]
    # Sniff common containers when the client sent a blob: URL (no extension).
    if audio_bytes[:4] == b"\x1aE\xdf\xa3":
        return ".webm"
    if len(audio_bytes) > 8 and audio_bytes[4:8] == b"ftyp":
        return ".m4a"
    if audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb":
        return ".mp3"
    if audio_bytes[:4] == b"OggS":
        return ".ogg"
    return ".bin"


async def convert_to_wav(
    audio_bytes: bytes,
    *,
    mime_type: str | None = None,
    filename: str | None = None,
) -> bytes:
    """Normalize browser/mobile recordings to 16 kHz mono PCM WAV for ASR.

    Expo web records `audio/webm` (often via blob: URLs without an extension).
    Native Expo uses AAC `.m4a`. Hugging Face Whisper uses soundfile, which
    rejects those containers — hence the malformed soundfile error.
    """
    if not audio_bytes:
        raise TranscriptionFailedError("Empty audio upload.")

    if not needs_wav_conversion(mime_type, filename, audio_bytes):
        return audio_bytes

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.error("ffmpeg not found; cannot convert %s for Whisper", mime_type)
        raise TranscriptionFailedError(
            "Audio format not supported and converter is unavailable. "
            "Try again from another browser or device."
        )

    suffix = _input_suffix(mime_type, filename, audio_bytes)
    with tempfile.TemporaryDirectory(prefix="smt-asr-") as tmp:
        src = Path(tmp) / f"input{suffix}"
        dst = Path(tmp) / "output.wav"
        src.write_bytes(audio_bytes)
        proc = await asyncio.create_subprocess_exec(
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(dst),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()
        if proc.returncode != 0 or not dst.is_file() or dst.stat().st_size < 44:
            detail = (stderr or b"").decode("utf-8", errors="replace").strip()
            logger.warning(
                "ffmpeg convert failed mime=%s name=%s detail=%s",
                mime_type,
                filename,
                detail[:300],
            )
            raise TranscriptionFailedError(
                "Soundfile is either not in the correct format or is malformed. "
                "The recording could not be converted. Hold the mic and try again."
            )
        wav = dst.read_bytes()
        logger.info(
            "Converted STT audio %s/%s (%s bytes) -> wav (%s bytes)",
            mime_type,
            filename,
            len(audio_bytes),
            len(wav),
        )
        return wav
