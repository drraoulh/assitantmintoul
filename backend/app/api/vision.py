from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import get_vision_service
from app.core.config import get_settings
from app.core.exceptions import VisionFailedError
from app.schemas.vision import VisionIdentifyResponse
from app.services.vision.base import VisionService

router = APIRouter(tags=["vision"])

_MAX_IMAGE_BYTES = 8 * 1024 * 1024


@router.post("/vision/identify", response_model=VisionIdentifyResponse)
async def identify_image(
    file: UploadFile = File(...),
    vision_service: VisionService = Depends(get_vision_service),
) -> VisionIdentifyResponse:
    image_bytes = await file.read()
    if not image_bytes:
        raise VisionFailedError("Empty image upload.")
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        raise VisionFailedError(
            "Image is too large. Keep photos under about 8 MB."
        )

    mime_type = file.content_type or "image/jpeg"
    description = await vision_service.identify(
        image_bytes=image_bytes,
        mime_type=mime_type,
    )
    provider = get_settings().vision_provider.strip().lower()
    if provider in {"google", "google-gemini"}:
        provider = "gemini"
    return VisionIdentifyResponse(
        description=description,
        provider=provider or "gemini",
    )
