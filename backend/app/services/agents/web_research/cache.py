"""Web Research cache — Redis when REDIS_URL is set, in-memory otherwise.

Key: sha256(intent | region | normalized query).
TTL: 1 h for volatile info (current events, hotels, restaurants, prices),
     24 h for stable topics (gastronomy, culture, history).
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
import unicodedata
from threading import Lock
from typing import Any

from app.core.config import get_settings
from app.services.agents.web_research.models import WebResearchResult

logger = logging.getLogger(__name__)

_LOCK = Lock()
_CACHE: dict[str, tuple[float, WebResearchResult]] = {}
_PREFIX = "smartmboa:web:"
_VOLATILE_INTENTS = {"WEB_SEARCH", "HOTEL", "BOOKING"}
_VOLATILE_REASONS = {"FORCED_CURRENT_INFORMATION", "FORCED_HOTEL_SEARCH", "FORCED_RESTAURANT_SEARCH"}
_redis_client: Any = None
_redis_failed = False


def normalize_query(query: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (query or "").casefold())
    text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s-]", " ", text)
    return " ".join(text.split())


def cache_key(query: str, intent: str, region: str | None = None) -> str:
    raw = f"{intent}|{normalize_query(region or '')}|{normalize_query(query)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def ttl_for(intent: str, web_reason: str | None = None) -> float:
    settings = get_settings()
    if intent in _VOLATILE_INTENTS or (web_reason or "") in _VOLATILE_REASONS:
        return float(settings.web_cache_ttl_current_seconds)
    return float(settings.web_cache_ttl_stable_seconds)


def _redis():
    global _redis_client, _redis_failed
    if _redis_client is not None or _redis_failed:
        return _redis_client
    url = get_settings().redis_url
    if not url:
        _redis_failed = True
        return None
    try:
        import redis

        _redis_client = redis.Redis.from_url(
            url, socket_timeout=0.3, socket_connect_timeout=0.3
        )
        _redis_client.ping()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[WEB] redis cache unavailable, using memory: %s", exc)
        _redis_client = None
        _redis_failed = True
    return _redis_client


def cache_get(query: str, intent: str, region: str | None = None) -> WebResearchResult | None:
    key = cache_key(query, intent, region)
    client = _redis()
    if client is not None:
        try:
            raw = client.get(_PREFIX + key)
            if raw:
                return WebResearchResult.model_validate_json(raw)
        except Exception:  # noqa: BLE001
            logger.warning("[WEB] redis get failed", exc_info=True)
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
    region: str | None = None,
) -> None:
    if ttl_seconds <= 0:
        return
    key = cache_key(query, intent, region)
    client = _redis()
    if client is not None:
        try:
            client.setex(_PREFIX + key, int(ttl_seconds), result.model_dump_json())
        except Exception:  # noqa: BLE001
            logger.warning("[WEB] redis set failed", exc_info=True)
    with _LOCK:
        _CACHE[key] = (time.monotonic() + ttl_seconds, result.model_copy(deep=True))
        if len(_CACHE) > 256:
            oldest = sorted(_CACHE.items(), key=lambda kv: kv[1][0])[:64]
            for k, _ in oldest:
                _CACHE.pop(k, None)


def cache_clear() -> None:
    with _LOCK:
        _CACHE.clear()
