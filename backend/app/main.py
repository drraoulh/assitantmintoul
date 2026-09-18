from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import init_database
from app.core.error_handlers import register_error_handlers
from app.core.http import close_shared_clients
from app.api.deps import get_speech_service, get_ai_service

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await init_database()
    from app.services.tourism.factory import warm_tourism_knowledge

    try:
        stats = await warm_tourism_knowledge()
        print(f"Tourism KB ready: {stats}")
    except Exception as exc:  # noqa: BLE001 - chat must start even if KB sync fails
        print(f"Tourism KB warm-up skipped: {exc}")
    # Keep STT/TTS adapters warm (no per-request model reload).
    try:
        get_speech_service()
        get_ai_service()
        print("Speech + AI services ready (singleton)")
    except Exception as exc:  # noqa: BLE001
        print(f"Speech/AI warm-up skipped: {exc}")
    yield
    await close_shared_clients()


app = FastAPI(
    title=settings.app_name,
    version="0.5.0",
    description="Intelligent tourist assistant dedicated to Cameroon (streaming voice pipeline).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=settings.cors_origin_list != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(api_router, prefix="/api")
