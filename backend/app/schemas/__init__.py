from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.health import HealthResponse
from app.schemas.speech import SynthesisRequest, TranscriptionResponse
from app.schemas.tourism import TouristSiteRecord
from app.schemas.vision import VisionIdentifyResponse

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "HealthResponse",
    "SynthesisRequest",
    "TranscriptionResponse",
    "TouristSiteRecord",
    "VisionIdentifyResponse",
]
