from fastapi import APIRouter

from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.health import router as health_router
from app.api.speech import router as speech_router
from app.api.tourist_sites import router as tourist_sites_router
from app.api.vision import router as vision_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(chat_router)
api_router.include_router(conversations_router)
api_router.include_router(speech_router)
api_router.include_router(vision_router)
api_router.include_router(tourist_sites_router)
