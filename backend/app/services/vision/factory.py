from app.core.config import get_settings
from app.services.vision.base import PlaceholderVisionService, VisionService
from app.services.vision.gemini import GeminiVisionService


def create_vision_service() -> VisionService:
    get_settings.cache_clear()
    settings = get_settings()
    provider = settings.vision_provider.strip().lower()
    if provider in {"gemini", "google", "google-gemini"}:
        return GeminiVisionService(settings=settings)
    if provider in {"placeholder", "none", "off"}:
        return PlaceholderVisionService()
    raise ValueError(
        f"Unknown VISION_PROVIDER '{provider}'. Use gemini or placeholder."
    )
