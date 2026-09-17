from fastapi.testclient import TestClient
import httpx
import pytest

from app.api.deps import get_vision_service
from app.core.config import Settings
from app.core.exceptions import VisionUnavailableError
from app.main import app
from app.services.vision.base import VisionService
from app.services.vision.gemini import GeminiVisionService, _normalize_mime


class FakeVisionService(VisionService):
    async def identify(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
    ) -> str:
        if not image_bytes:
            raise VisionUnavailableError("Empty image upload.")
        return "Cette photo montre le Mont Cameroun, près de Buea."


def client_with_vision(service: VisionService) -> TestClient:
    app.dependency_overrides[get_vision_service] = lambda: service
    return TestClient(app)


def test_normalize_mime_maps_jpg() -> None:
    assert _normalize_mime("image/jpg") == "image/jpeg"
    assert _normalize_mime("image/png") == "image/png"
    assert _normalize_mime(None) == "image/jpeg"


def test_identify_endpoint_success() -> None:
    client = client_with_vision(FakeVisionService())
    try:
        response = client.post(
            "/api/vision/identify",
            files={"file": ("site.jpg", b"fake-image-bytes", "image/jpeg")},
        )
        assert response.status_code == 200
        payload = response.json()
        assert "Mont Cameroun" in payload["description"]
        assert payload["provider"] in {"gemini", "placeholder"}
    finally:
        app.dependency_overrides.clear()


def test_identify_endpoint_empty_file() -> None:
    client = client_with_vision(FakeVisionService())
    try:
        response = client.post(
            "/api/vision/identify",
            files={"file": ("site.jpg", b"", "image/jpeg")},
        )
        assert response.status_code == 502
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gemini_vision_identify_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "gemini-3.6-flash" in str(request.url)
        assert request.headers.get("x-goog-api-key") == "gemini_test_key"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": " Photo du Lac Ossa, près d'Édéa. "
                                }
                            ]
                        }
                    }
                ]
            },
        )

    settings = Settings(
        VISION_PROVIDER="gemini",
        GEMINI_API_KEY="gemini_test_key",
        gemini_api_base_url="https://generativelanguage.googleapis.com/v1beta",
        gemini_vision_model="gemini-3.6-flash",
    )
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = GeminiVisionService(settings=settings, client=client)
        text = await service.identify(b"fake-image", mime_type="image/jpeg")
    assert "Lac Ossa" in text


@pytest.mark.asyncio
async def test_gemini_vision_requires_api_key() -> None:
    settings = Settings(VISION_PROVIDER="gemini", GEMINI_API_KEY="")
    service = GeminiVisionService(settings=settings)
    with pytest.raises(VisionUnavailableError):
        await service.identify(b"fake-image", mime_type="image/jpeg")
