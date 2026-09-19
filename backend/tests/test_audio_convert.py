import struct
from pathlib import Path

import pytest

from app.services.speech.audio_convert import convert_to_wav, looks_like_wav, needs_wav_conversion


def _minimal_wav(*, frames: int = 1600, rate: int = 16000) -> bytes:
    """Build a tiny mono PCM16 WAV in-memory."""
    data_size = frames * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        rate,
        rate * 2,
        2,
        16,
        b"data",
        data_size,
    )
    return header + (b"\x00\x00" * frames)


def test_looks_like_wav_detects_header() -> None:
    assert looks_like_wav(_minimal_wav())
    assert not looks_like_wav(b"not-audio")
    assert not looks_like_wav(b"\x1aE\xdf\xa3fake-webm")


def test_needs_conversion_for_webm_and_m4a() -> None:
    assert needs_wav_conversion("audio/webm", "blob.webm", b"\x1aE\xdf\xa3xxxx")
    assert needs_wav_conversion("audio/m4a", "clip.m4a", b"xxxxftypxxxx")
    assert not needs_wav_conversion("audio/wav", "a.wav", _minimal_wav())


@pytest.mark.asyncio
async def test_convert_webm_to_wav_with_ffmpeg(tmp_path: Path) -> None:
    src = tmp_path / "tone.webm"
    # Generate a short webm/opus via ffmpeg so conversion is realistic.
    import asyncio
    import shutil

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg not installed")
    proc = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=0.3",
        "-c:a",
        "libopus",
        str(src),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    if proc.returncode != 0 or not src.exists():
        pytest.skip("could not generate webm fixture")

    wav = await convert_to_wav(src.read_bytes(), mime_type="audio/webm", filename="tone.webm")
    assert looks_like_wav(wav)
    assert len(wav) > 44


@pytest.mark.asyncio
async def test_convert_passthrough_wav() -> None:
    original = _minimal_wav()
    out = await convert_to_wav(original, mime_type="audio/wav", filename="a.wav")
    assert out == original
