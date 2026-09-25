"""In-memory TTL cache for Web Research results."""

from __future__ import annotations

import hashlib
import time
from threading import Lock

from app.services.agents.web_research.models import WebResearchResult

_LOCK = Lock()
_CACHE: dict[str, tuple[float, WebResearchResult]] = {}


def _norm_key(query: str, intent: str) -> str:
    raw = f"{intent}|{query.strip().casefold()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def cache_get(query: str, intent: str) -> WebResearchResult | None:
    key = _norm_key(query, intent)
    with _LOCK:
        item = _CACHE.get(key)
        if not item:
            return None
        expires, value = item
        if time.monotonic() > expires:
            _CACHE.pop(key, None)
            return None
        return value.model_copy(deep=True)


def cache_set(
    query: str,
    intent: str,
    result: WebResearchResult,
    *,
    ttl_seconds: float,
) -> None:
    if ttl_seconds <= 0:
        return
    key = _norm_key(query, intent)
    with _LOCK:
        _CACHE[key] = (time.monotonic() + ttl_seconds, result.model_copy(deep=True))
        # Bound memory
        if len(_CACHE) > 256:
            oldest = sorted(_CACHE.items(), key=lambda kv: kv[1][0])[:64]
            for k, _ in oldest:
                _CACHE.pop(k, None)


def cache_clear() -> None:
    with _LOCK:
        _CACHE.clear()
