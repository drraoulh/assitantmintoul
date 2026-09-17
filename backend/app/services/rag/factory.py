from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.services.rag.base import PlaceholderRAGService, RAGService
from app.services.rag.local import LocalRAGService


def create_rag_service() -> RAGService:
    settings = get_settings()
    if not settings.rag_enabled:
        return PlaceholderRAGService()

    data_root = settings.rag_data_dir.strip()
    root = Path(data_root) if data_root else None
    return LocalRAGService(data_root=str(root) if root else None)


@lru_cache
def get_rag_service() -> RAGService:
    return create_rag_service()
