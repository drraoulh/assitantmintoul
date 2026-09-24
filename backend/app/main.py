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
    # Phase 1.9: warm shared HTTP clients (HF + Fish) so the first voice turn
    # does not pay a cold DNS/TLS handshake on the critical path.
    try:
        from app.core.http import shared_async_client
        import httpx

        warm_targets: list[tuple[str, str]] = []
        if settings.hf_api_base_url:
            warm_targets.append(("HF", settings.hf_api_base_url.rstrip("/")))
        fish_base = getattr(settings, "fish_audio_base_url", None) or "https://api.fish.audio"
        if settings.tts_provider == "fish":
            warm_targets.append(("Fish", str(fish_base).rstrip("/")))
        for label, base in warm_targets:
            client = shared_async_client(
                base_url=base,
                timeout_seconds=min(15.0, float(settings.hf_timeout_seconds or 60)),
            )
            try:
                await client.get("/", timeout=httpx.Timeout(8.0, connect=5.0))
                print(f"Inference HTTP warm: {label} TLS ready ({base})", flush=True)
            except Exception as warm_exc:  # noqa: BLE001 - warm is best-effort
                print(f"Inference HTTP warm skipped for {label}: {warm_exc}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"Inference HTTP warm-up skipped: {exc}", flush=True)
    # Phase 1: hydrate HybridRAG (Supabase merge + TF-IDF) before first request.
    try:
        from app.services.rag.factory import get_rag_service

        rag = get_rag_service()
        warm = getattr(rag, "warm", None)
        if callable(warm):
            n = await warm()
            print(f"RAG index hydrated: {n} chunks")
    except Exception as exc:  # noqa: BLE001
        print(f"RAG warm-up skipped: {exc}")
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
