"""TTL cache for RAG retrieval — in-memory by default, Redis when REDIS_URL is set."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from app.services.rag.chunk import KnowledgeChunk

logger = logging.getLogger(__name__)

_PUNCT = re.compile(r"[^\w\s]+", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize_cache_query(query: str) -> str:
    """Collapse punctuation/case so near-identical questions share a cache key."""
    folded = query.strip().casefold()
    folded = _PUNCT.sub(" ", folded)
    return _WS.sub(" ", folded).strip()


@dataclass
class _MemoryEntry:
    expires_at: float
    payload: list[dict[str, Any]]


class RetrievalCache:
    """Cache Top-K retrieval results by normalized query + top_k.

    Phase 1: avoid re-running tokenization + TF-IDF for identical / near-identical
    questions within TTL. Does not cache live web or LLM answers.
    """

    def __init__(
        self,
        ttl_seconds: float = 300.0,
        redis_url: str = "",
        *,
        max_entries: int = 512,
    ) -> None:
        self._ttl = max(1.0, ttl_seconds)
        self._max_entries = max(32, max_entries)
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
        normalized = normalize_cache_query(query)
        digest = hashlib.sha256(f"{top_k}|{normalized}".encode()).hexdigest()
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
        if len(self._memory) >= self._max_entries:
            # Drop oldest expired first, else arbitrary eviction of one key.
            now = time.time()
            expired = [k for k, v in self._memory.items() if v.expires_at < now]
            for k in expired[: max(1, len(expired))]:
                self._memory.pop(k, None)
            if len(self._memory) >= self._max_entries:
                self._memory.pop(next(iter(self._memory)), None)
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
