from abc import ABC, abstractmethod


class VisionService(ABC):
    """Identify tourist sites or objects from a photo.

    Planned: an open-source vision model compatible with Hugging Face.
    """

    @abstractmethod
    async def identify(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        """Return a description of the uploaded image."""


class PlaceholderVisionService(VisionService):
    async def identify(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        raise NotImplementedError("Photo identification will be added in a later phase.")
