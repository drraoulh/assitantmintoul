from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.services.rag.base import PlaceholderRAGService, RAGService
from app.services.rag.cache import RetrievalCache
from app.services.rag.chunk import KnowledgeChunk
from app.services.rag.loader import load_knowledge_chunks
from app.services.rag.local import LocalRAGService
from app.services.rag.vector_hf import HuggingFaceEmbeddingIndex, HybridVectorRAGService

logger = logging.getLogger(__name__)


class HybridRAGService(RAGService):
    """File KB immediately, then enrich with Supabase on first retrieval."""

    def __init__(
        self,
        file_chunks: list[KnowledgeChunk],
        *,
        load_supabase: bool,
        cache: RetrievalCache | None = None,
        vector_enabled: bool = False,
    ) -> None:
        self._file_chunks = file_chunks
        self._load_supabase = load_supabase
        self._cache = cache
        self._vector_enabled = vector_enabled
        self._vector_index: HuggingFaceEmbeddingIndex | None = None
        self._local = LocalRAGService(chunks=file_chunks)
        self._hybrid = HybridVectorRAGService(
            self._local,
            vector_index=None,
            cache=cache,
        )
        self._ready = not load_supabase
        self._lock = asyncio.Lock()
        self._vector_warm_task: asyncio.Task | None = None

    @property
    def chunk_count(self) -> int:
        return self._local.chunk_count

    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        chunks = await self.retrieve_chunks(query, top_k=top_k)
        return [chunk.text for chunk in chunks]

    async def retrieve_chunks(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[KnowledgeChunk]:
        await self._ensure_loaded()
        return await self._hybrid.retrieve_chunks(query, top_k=top_k)

    async def _ensure_loaded(self) -> None:
        if self._ready:
            self._ensure_vector_warming()
            return
        async with self._lock:
            if self._ready:
                self._ensure_vector_warming()
                return
            db_chunks: list[KnowledgeChunk] = []
            try:
                from app.services.kb.supabase_repository import (
                    SupabaseKnowledgeRepository,
                )

                db_chunks = await SupabaseKnowledgeRepository().load_chunks()
            except Exception:
                logger.exception(
                    "Supabase KB unavailable; continuing with file knowledge only"
                )
            merged = _merge_chunks(db_chunks, self._file_chunks)
            self._local = LocalRAGService(chunks=merged or self._file_chunks)
            self._hybrid = HybridVectorRAGService(
                self._local,
                vector_index=self._vector_index,
                cache=self._cache,
            )
            self._ready = True
            logger.info(
                "RAG hydrated: %s chunks (supabase=%s, files=%s)",
                self._local.chunk_count,
                len(db_chunks),
                len(self._file_chunks),
            )
            self._ensure_vector_warming()

    def _ensure_vector_warming(self) -> None:
        if not self._vector_enabled or self._vector_index is not None:
            return
        if self._vector_warm_task and not self._vector_warm_task.done():
            return

        async def _warm() -> None:
            index = HuggingFaceEmbeddingIndex(list(self._local.chunks))
            await index.warm()
            self._vector_index = index if index.ready else None
            self._hybrid = HybridVectorRAGService(
                self._local,
                vector_index=self._vector_index,
                cache=self._cache,
            )

        try:
            loop = asyncio.get_running_loop()
            self._vector_warm_task = loop.create_task(_warm())
        except RuntimeError:
            # No running loop during sync construction — warm on first retrieve.
            pass


def create_rag_service() -> RAGService:
    settings = get_settings()
    if not settings.rag_enabled:
        return PlaceholderRAGService()

    data_root = settings.rag_data_dir.strip()
    root = Path(data_root) if data_root else None
    file_chunks = load_knowledge_chunks(root)
    cache = RetrievalCache(
        ttl_seconds=settings.rag_cache_ttl_seconds,
        redis_url=settings.redis_url,
    )
    return HybridRAGService(
        file_chunks=file_chunks,
        load_supabase=settings.database_enabled,
        cache=cache,
        vector_enabled=settings.rag_vector_enabled,
    )


@lru_cache
def get_rag_service() -> RAGService:
    return create_rag_service()


def refresh_rag_service() -> RAGService:
    """Drop the cached RAG instance after a KB sync."""
    get_rag_service.cache_clear()
    return get_rag_service()


def _merge_chunks(
    primary: list[KnowledgeChunk],
    secondary: list[KnowledgeChunk],
) -> list[KnowledgeChunk]:
    seen: set[str] = set()
    merged: list[KnowledgeChunk] = []
    for chunk in [*primary, *secondary]:
        key = chunk.id.strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(chunk)
    return merged
