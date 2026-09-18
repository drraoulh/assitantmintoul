"""TTL cache for RAG retrieval — in-memory by default, Redis when REDIS_URL is set."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from app.services.rag.chunk import KnowledgeChunk

logger = logging.getLogger(__name__)


@dataclass
class _MemoryEntry:
    expires_at: float
    payload: list[dict[str, Any]]


class RetrievalCache:
    """Cache Top-K retrieval results by normalized query + top_k."""

    def __init__(self, ttl_seconds: float = 300.0, redis_url: str = "") -> None:
        self._ttl = max(1.0, ttl_seconds)
        self._memory: dict[str, _MemoryEntry] = {}
        self._redis = None
        url = (redis_url or "").strip()
        if url:
            try:
                import redis  # type: ignore

                client = redis.Redis.from_url(url, decode_responses=True)
                client.ping()
                self._redis = client
                logger.info("RAG cache: Redis connected (%s)", url.split("@")[-1])
            except Exception as exc:  # noqa: BLE001
                logger.warning("RAG cache: Redis unavailable (%s); using memory", exc)

    @staticmethod
    def _key(query: str, top_k: int) -> str:
        digest = hashlib.sha256(
            f"{top_k}|{query.strip().casefold()}".encode()
        ).hexdigest()
        return f"rag:v1:{digest}"

    def get(self, query: str, top_k: int) -> list[KnowledgeChunk] | None:
        key = self._key(query, top_k)
        if self._redis is not None:
            try:
                raw = self._redis.get(key)
                if raw:
                    data = json.loads(raw)
                    return [KnowledgeChunk.from_cache_dict(item) for item in data]
            except Exception:
                logger.exception("RAG Redis get failed")

        entry = self._memory.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.time():
            self._memory.pop(key, None)
            return None
        return [KnowledgeChunk.from_cache_dict(item) for item in entry.payload]

    def set(self, query: str, top_k: int, chunks: list[KnowledgeChunk]) -> None:
        key = self._key(query, top_k)
        payload = [chunk.to_cache_dict() for chunk in chunks]
        if self._redis is not None:
            try:
                self._redis.setex(
                    key,
                    int(self._ttl),
                    json.dumps(payload, ensure_ascii=False),
                )
            except Exception:
                logger.exception("RAG Redis set failed")
        self._memory[key] = _MemoryEntry(
            expires_at=time.time() + self._ttl,
            payload=payload,
        )

    def clear(self) -> None:
        self._memory.clear()
        if self._redis is not None:
            try:
                for key in self._redis.scan_iter(match="rag:v1:*", count=200):
                    self._redis.delete(key)
            except Exception:
                logger.exception("RAG Redis clear failed")
