from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.services.rag.loader import default_data_root
from app.services.tourism.base import TourismService

logger = logging.getLogger(__name__)


def _normalize_city(value: str) -> str:
    return value.strip().casefold()


class LocalTourismService(TourismService):
    """Read curated tourist sites from data/tourist_sites/*.json."""

    def __init__(self, data_root: Path | None = None) -> None:
        root = data_root or default_data_root()
        self._sites = self._load_sites(root / "tourist_sites")

    async def find_sites(self, city: str) -> list[dict[str, Any]]:
        needle = _normalize_city(city)
        if not needle:
            return []
        return [
            site
            for site in self._sites
            if needle in _normalize_city(str(site.get("city") or ""))
            or needle in _normalize_city(str(site.get("name") or ""))
        ]

    async def build_itinerary(self, city: str, hours: int) -> dict[str, Any]:
        sites = await self.find_sites(city)
        # Rough pacing: one stop per ~2 hours, minimum 1 if sites exist.
        capacity = max(1, hours // 2) if hours > 0 else 3
        stops = [
            {
                "id": site.get("id"),
                "name": site.get("name"),
                "category": site.get("category"),
                "summary_fr": site.get("summary_fr"),
                "summary_en": site.get("summary_en"),
            }
            for site in sites[:capacity]
        ]
        return {
            "city": city,
            "hours": hours,
            "stops": stops,
            "note": (
                "Indicative itinerary from the local knowledge base. "
                "Confirm opening hours and transport on site."
            ),
        }

    def _load_sites(self, directory: Path) -> list[dict[str, Any]]:
        if not directory.is_dir():
            return []
        sites: list[dict[str, Any]] = []
        for path in sorted(directory.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Skipping %s: %s", path, exc)
                continue
            if isinstance(payload, list):
                sites.extend(item for item in payload if isinstance(item, dict))
        return sites
