from abc import ABC, abstractmethod

from app.core.exceptions import VisionUnavailableError


class VisionService(ABC):
    """Identify tourist sites or objects from a photo.

    Default provider: Google Gemini multimodal vision.
    """

    @abstractmethod
    async def identify(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        """Return a description of the uploaded image."""


class PlaceholderVisionService(VisionService):
    async def identify(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        raise VisionUnavailableError(
            "Photo identification is disabled. "
            "Set VISION_PROVIDER=gemini and GEMINI_API_KEY."
        )
