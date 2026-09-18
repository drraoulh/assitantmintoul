"""Optional remote HF embeddings for vector Top-K (no local model download)."""

from __future__ import annotations

import logging
import math
from typing import Any  # used by _as_vector

import httpx

from app.core.config import Settings, get_settings
from app.core.http import shared_async_client
from app.services.rag.cache import RetrievalCache
from app.services.rag.base import RAGService
from app.services.rag.chunk import KnowledgeChunk

logger = logging.getLogger(__name__)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def _mean_pool(matrix: list[list[float]]) -> list[float]:
    if not matrix:
        return []
    dim = len(matrix[0])
    acc = [0.0] * dim
    for row in matrix:
        for i, value in enumerate(row):
            acc[i] += float(value)
    n = float(len(matrix))
    return [value / n for value in acc]


def _as_vector(payload: Any) -> list[float]:
    """Normalize HF feature-extraction JSON into a single vector."""
    if isinstance(payload, list) and payload:
        if isinstance(payload[0], (int, float)):
            return [float(x) for x in payload]
        if isinstance(payload[0], list):
            # token embeddings [[d], ...] or batch [[[d], ...]]
            if payload and isinstance(payload[0][0], list):
                return _mean_pool(payload[0])  # type: ignore[arg-type]
            return _mean_pool(payload)  # type: ignore[arg-type]
    if isinstance(payload, dict):
        for key in ("embeddings", "embedding", "data"):
            if key in payload:
                return _as_vector(payload[key])
    return []


class HuggingFaceEmbeddingIndex:
    """Precompute chunk vectors via HF Inference; query with the same model."""

    def __init__(
        self,
        chunks: list[KnowledgeChunk],
        *,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client
        self._chunks = chunks
        self._vectors: list[list[float]] = []
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready and len(self._vectors) == len(self._chunks)

    async def warm(self, *, max_chunks: int = 400) -> int:
        if not self._chunks:
            self._ready = True
            return 0
        token = (
            self._settings.huggingface_hub_token or self._settings.hf_token
        ).strip()
        if not token:
            logger.warning("Vector RAG skipped: missing HUGGINGFACE_HUB_TOKEN")
            return 0

        subset = self._chunks[:max_chunks]
        vectors: list[list[float]] = []
        for chunk in subset:
            text = f"{chunk.title}. {chunk.text[:700]}"
            try:
                vector = await self._embed(text, token)
            except Exception:
                logger.exception("Embedding failed for chunk %s", chunk.id)
                vector = []
            if not vector:
                # Keep alignment: empty vector scores 0.
                vectors.append([])
            else:
                vectors.append(vector)

        self._chunks = subset
        self._vectors = vectors
        self._ready = any(vectors)
        logger.info(
            "HF vector index ready: %s/%s chunks embedded",
            sum(1 for v in vectors if v),
            len(vectors),
        )
        return len(vectors)

    async def search(self, query: str, top_k: int = 4) -> list[KnowledgeChunk]:
        if not self.ready or top_k <= 0:
            return []
        token = (
            self._settings.huggingface_hub_token or self._settings.hf_token
        ).strip()
        if not token:
            return []
        try:
            query_vec = await self._embed(query, token)
        except Exception:
            logger.exception("Query embedding failed")
            return []
        if not query_vec:
            return []

        scored: list[tuple[float, KnowledgeChunk]] = []
        for chunk, vector in zip(self._chunks, self._vectors, strict=True):
            if not vector:
                continue
            score = _cosine(query_vec, vector)
            if score > 0.15:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]

    async def _embed(self, text: str, token: str) -> list[float]:
        model = self._settings.hf_embedding_model_id.strip()
        base = self._settings.hf_inference_base_url.rstrip("/")
        url = f"{base}/models/{model}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        client = self._client or shared_async_client(
            timeout_seconds=min(60.0, self._settings.hf_timeout_seconds),
        )
        response = await client.post(
            url,
            headers=headers,
            json={"inputs": text, "options": {"wait_for_model": True}},
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        if response.status_code >= 400:
            logger.warning(
                "HF embedding HTTP %s: %s",
                response.status_code,
                response.text[:200],
            )
            return []
        try:
            payload = response.json()
        except ValueError:
            return []
        return _as_vector(payload)


class HybridVectorRAGService(RAGService):
    """Merge lexical TF-IDF with optional HF vector hits, then cache."""

    def __init__(
        self,
        lexical: RAGService,
        *,
        vector_index: HuggingFaceEmbeddingIndex | None = None,
        cache: RetrievalCache | None = None,
    ) -> None:
        self._lexical = lexical
        self._vector = vector_index
        self._cache = cache

    @property
    def chunk_count(self) -> int:
        return getattr(self._lexical, "chunk_count", 0)

    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        chunks = await self.retrieve_chunks(query, top_k=top_k)
        return [chunk.text for chunk in chunks]

    async def retrieve_chunks(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[KnowledgeChunk]:
        if self._cache is not None:
            cached = self._cache.get(query, top_k)
            if cached is not None:
                return cached

        lexical_hits = await self._lexical.retrieve_chunks(query, top_k=top_k)
        vector_hits: list[KnowledgeChunk] = []
        if self._vector is not None and self._vector.ready:
            try:
                vector_hits = await self._vector.search(query, top_k=top_k)
            except Exception:
                logger.exception("Vector search failed; lexical only")

        merged = _rrf_merge(lexical_hits, vector_hits, top_k=top_k)
        if self._cache is not None:
            self._cache.set(query, top_k, merged)
        return merged


def _rrf_merge(
    lexical: list[KnowledgeChunk],
    vector: list[KnowledgeChunk],
    *,
    top_k: int,
    k: int = 60,
) -> list[KnowledgeChunk]:
    scores: dict[str, float] = {}
    by_id: dict[str, KnowledgeChunk] = {}
    for rank, chunk in enumerate(lexical):
        scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (k + rank + 1)
        by_id[chunk.id] = chunk
    for rank, chunk in enumerate(vector):
        scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (k + rank + 1)
        by_id[chunk.id] = chunk
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [by_id[chunk_id] for chunk_id, _ in ordered[:top_k]]
