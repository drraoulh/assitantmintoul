from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from app.api.deps import get_speech_service
from app.core.config import get_settings
from app.core.exceptions import SynthesisFailedError, TranscriptionFailedError
from app.schemas.speech import SynthesisRequest, TranscriptionResponse
from app.services.speech.base import SpeechService

router = APIRouter(tags=["speech"])

_MAX_AUDIO_BYTES = 12 * 1024 * 1024


@router.post("/speech/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    speech_service: SpeechService = Depends(get_speech_service),
) -> TranscriptionResponse:
    audio_bytes = await file.read()
    if not audio_bytes:
        raise TranscriptionFailedError("Empty audio upload.")
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise TranscriptionFailedError(
            "Audio file is too large. Keep recordings under about 12 MB."
        )

    mime_type = file.content_type or "application/octet-stream"
    text, language = await speech_service.transcribe(
        audio_bytes=audio_bytes,
        mime_type=mime_type,
        filename=file.filename,
    )
    provider = get_settings().speech_provider.strip().lower()
    if provider in {"hf", "huggingface-whisper"}:
        provider = "huggingface"
    elif provider in {"faster-whisper", "stt", "local"}:
        provider = "whisper"
    return TranscriptionResponse(
        text=text,
        language=language,
        provider=provider,
    )


@router.post("/speech/synthesize")
async def synthesize_speech(
    payload: SynthesisRequest,
    speech_service: SpeechService = Depends(get_speech_service),
) -> Response:
    text = payload.text.strip()
    if not text:
        raise SynthesisFailedError("Empty text for speech synthesis.")

    audio_bytes = await speech_service.synthesize(text)
    if not audio_bytes:
        raise SynthesisFailedError("Empty audio from TTS provider.")

    tts_provider = get_settings().tts_provider.strip().lower()
    if tts_provider in {"fish-audio", "fishspeech", "fish-speech"}:
        tts_provider = "fish"

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "X-TTS-Provider": tts_provider or "fish",
            "Cache-Control": "no-store",
        },
    )
