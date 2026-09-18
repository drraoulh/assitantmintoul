from fastapi.testclient import TestClient
import httpx
import pytest

from app.api.deps import get_speech_service
from app.core.config import Settings
from app.core.exceptions import SpeechUnavailableError, TranscriptionFailedError
from app.main import app
from app.services.speech.base import SpeechService
from app.services.speech.huggingface import HuggingFaceSpeechService
from app.services.speech.whisper import extension_for, whisper_model_size


class FakeSpeechService(SpeechService):
    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/wav",
        filename: str | None = None,
    ) -> tuple[str, str | None]:
        if not audio_bytes:
            raise TranscriptionFailedError("Empty audio upload.")
        return "Quels sont les sites à visiter à Yaoundé ?", "fr"

    async def synthesize(self, text: str) -> bytes:
        raise NotImplementedError


def client_with_speech(service: SpeechService) -> TestClient:
    app.dependency_overrides[get_speech_service] = lambda: service
    return TestClient(app)


def test_whisper_model_size_from_hf_id() -> None:
    assert whisper_model_size("openai/whisper-small") == "small"
    assert whisper_model_size("whisper-tiny") == "tiny"


def test_extension_for_mime_and_filename() -> None:
    assert extension_for("audio/m4a", None) == ".m4a"
    assert extension_for("application/octet-stream", "clip.webm") == ".webm"


def test_transcribe_endpoint_success() -> None:
    client = client_with_speech(FakeSpeechService())
    try:
        response = client.post(
            "/api/speech/transcribe",
            files={"file": ("voice.m4a", b"fake-audio-bytes", "audio/mp4")},
        )
        assert response.status_code == 200
        payload = response.json()
        assert "Yaoundé" in payload["text"]
        assert payload["language"] == "fr"
        assert payload["provider"] in {"whisper", "huggingface", "placeholder"}
    finally:
        app.dependency_overrides.clear()


def test_transcribe_endpoint_empty_file() -> None:
    client = client_with_speech(FakeSpeechService())
    try:
        response = client.post(
            "/api/speech/transcribe",
            files={"file": ("voice.m4a", b"", "audio/mp4")},
        )
        assert response.status_code == 502
        assert "Empty" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_huggingface_speech_transcribe_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.headers.get("content-type", "").startswith("application/json")
        body = request.read()
        assert b"generate_kwargs" in body
        assert b"french" in body
        assert b"transcribe" in body
        return httpx.Response(200, json={"text": " Visiter le Mont Cameroun "})

    settings = Settings(
        speech_provider="huggingface",
        hf_whisper_model_id="openai/whisper-small",
        huggingface_hub_token="hf_test_token",
        hf_inference_base_url="https://router.huggingface.co/hf-inference",
    )
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = HuggingFaceSpeechService(settings=settings, client=client)
        text, language = await service.transcribe(
            b"fake-audio",
            mime_type="audio/mp4",
            filename="voice.m4a",
        )
    assert text == "Visiter le Mont Cameroun"
    assert language == "fr"


@pytest.mark.asyncio
async def test_huggingface_speech_requires_token() -> None:
    settings = Settings(
        speech_provider="huggingface",
        HUGGINGFACE_HUB_TOKEN="",
        HF_TOKEN="",
    )
    service = HuggingFaceSpeechService(settings=settings)
    with pytest.raises(SpeechUnavailableError):
        await service.transcribe(b"fake-audio", mime_type="audio/mp4")


def test_normalize_hf_content_type_maps_mp4_to_m4a() -> None:
    from app.services.speech.huggingface import normalize_hf_content_type

    assert normalize_hf_content_type("audio/mp4", "voice.m4a") == "audio/m4a"
    assert normalize_hf_content_type("audio/mp4", None) == "audio/m4a"
    assert normalize_hf_content_type("audio/wav", "a.wav") == "audio/wav"


@pytest.mark.asyncio
async def test_fish_audio_synthesize_success() -> None:
    from app.services.speech.fish_audio import FishAudioTTSService

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/tts"
        assert request.headers.get("model") == "s2.1-pro-free"
        assert b"Bienvenue" in request.content
        return httpx.Response(200, content=b"ID3fake-mp3")

    settings = Settings(
        tts_provider="fish",
        FISH_AUDIO_API_KEY="fish_test_key",
        fish_audio_base_url="https://api.fish.audio",
        fish_audio_model="s2.1-pro-free",
        fish_audio_reference_id="",
    )
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = FishAudioTTSService(settings=settings, client=client)
        audio = await service.synthesize("Bienvenue au Cameroun")
    assert audio.startswith(b"ID3")


@pytest.mark.asyncio
async def test_fish_audio_requires_api_key() -> None:
    from app.services.speech.fish_audio import FishAudioTTSService

    settings = Settings(tts_provider="fish", FISH_AUDIO_API_KEY="")
    service = FishAudioTTSService(settings=settings)
    with pytest.raises(SpeechUnavailableError):
        await service.synthesize("Bonjour")


def test_synthesize_endpoint_success() -> None:
    class FakeTTS(SpeechService):
        async def transcribe(
            self,
            audio_bytes: bytes,
            mime_type: str = "audio/wav",
            filename: str | None = None,
        ) -> tuple[str, str | None]:
            raise NotImplementedError

        async def synthesize(self, text: str) -> bytes:
            assert "Yaoundé" in text
            return b"ID3tts-bytes"

    client = client_with_speech(FakeTTS())
    try:
        response = client.post(
            "/api/speech/synthesize",
            json={"text": "Visitez Yaoundé"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("audio/mpeg")
        assert response.content == b"ID3tts-bytes"
        assert response.headers.get("x-tts-provider")
    finally:
        app.dependency_overrides.clear()


def test_synthesize_endpoint_empty_text() -> None:
    client = client_with_speech(FakeSpeechService())
    try:
        response = client.post("/api/speech/synthesize", json={"text": "   "})
        assert response.status_code == 502
    finally:
        app.dependency_overrides.clear()
