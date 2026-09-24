"""Verified place cover images (Ayila'a export) keyed by slug / local id.

Used when the live catalog / local JSON has an empty ``images`` list.
Never invents URLs — only returns paths present in the committed index.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from app.services.rag.loader import default_data_root

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_EXPORT_SUMMARY = (
    _REPO_ROOT
    / "exports"
    / "supabase-tourist-places"
    / "places_summary.json"
)
_DATA_INDEX = default_data_root() / "place_images_by_slug.json"


@lru_cache(maxsize=1)
def primary_image_by_slug() -> dict[str, str]:
    """slug → primary https image URL from the verified export / data index."""
    for path, loader in (
        (_DATA_INDEX, _load_slug_map),
        (_EXPORT_SUMMARY, _load_summary_list),
    ):
        if not path.is_file():
            continue
        try:
            mapping = loader(path)
        except Exception:
            logger.exception("Could not read place image index at %s", path)
            continue
        if mapping:
            return mapping
    logger.warning(
        "No place image index found (tried %s and %s)",
        _DATA_INDEX,
        _EXPORT_SUMMARY,
    )
    return {}


def _load_slug_map(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        slug = str(key or "").strip()
        url = str(value or "").strip()
        if slug and url.startswith(("http://", "https://")):
            out[slug] = url
    return out


def _load_summary_list(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return {}
    out: dict[str, str] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        slug = str(row.get("slug") or "").strip()
        url = str(row.get("primary_image") or "").strip()
        if slug and url.startswith(("http://", "https://")):
            out[slug] = url
    return out


def image_url_for_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    return primary_image_by_slug().get(slug.strip()) or None


def image_url_for_place(
    *,
    slug: str | None = None,
    place_id: str | None = None,
) -> str | None:
    """Resolve a cover URL by catalog slug and/or local site id."""
    return image_url_for_slug(slug) or image_url_for_slug(place_id)


def enrich_images(
    images: list[str] | None,
    *,
    slug: str | None = None,
    place_id: str | None = None,
) -> list[str]:
    """Keep existing images; if empty, attach one verified export URL when known."""
    cleaned = [str(url).strip() for url in (images or []) if str(url).strip()]
    if cleaned:
        return cleaned
    url = image_url_for_place(slug=slug, place_id=place_id)
    return [url] if url else []
