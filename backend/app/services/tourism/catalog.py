from __future__ import annotations

import json
import logging
import re
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

from app.schemas.tourism import SourceRecord, TouristSiteRecord
from app.services.rag.loader import default_data_root

logger = logging.getLogger(__name__)

_SLUG = re.compile(r"[^a-z0-9]+")


class SiteCatalog:
    """JSON-backed catalog over data/tourist_sites (flat files from master KB)."""

    def __init__(self, sites: list[TouristSiteRecord] | None = None) -> None:
        if sites is not None:
            self._sites = sites
        else:
            self._sites = self._load_sites(default_data_root() / "tourist_sites")

    def all(self) -> list[TouristSiteRecord]:
        return list(self._sites)

    def get(self, site_id: str) -> TouristSiteRecord | None:
        for site in self._sites:
            if site.id == site_id or site.slug == site_id:
                return site
        return None

    def by_city(self, city: str) -> list[TouristSiteRecord]:
        needle = _fold(city)
        return [
            site
            for site in self._sites
            if needle in _fold(site.city) or needle in _fold(site.region)
        ]

    def nearby(
        self,
        *,
        city: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_km: float = 50,
    ) -> list[TouristSiteRecord]:
        if city:
            return self.by_city(city)
        if latitude is None or longitude is None:
            return []
        matches: list[TouristSiteRecord] = []
        for site in self._sites:
            if site.latitude is None or site.longitude is None:
                continue
            if _haversine_km(latitude, longitude, site.latitude, site.longitude) <= radius_km:
                matches.append(site)
        return matches

    def _load_sites(self, directory: Path) -> list[TouristSiteRecord]:
        if not directory.is_dir():
            return []

        sites: list[TouristSiteRecord] = []
        # Master layout: data/tourist_sites/*.json
        for path in sorted(directory.glob("*.json")):
            sites.extend(self._records_from_file(path))
        # Legacy layout: data/tourist_sites/<region>/sites.json
        for path in sorted(directory.glob("*/*.json")):
            sites.extend(self._records_from_file(path))
        return sites

    def _records_from_file(self, path: Path) -> list[TouristSiteRecord]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping %s: %s", path, exc)
            return []

        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = payload.get("sites", [])
        else:
            return []

        records: list[TouristSiteRecord] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            record = _to_record(item)
            if record is not None:
                records.append(record)
        return records


def _to_record(item: dict) -> TouristSiteRecord | None:
    site_id = str(item.get("id") or "").strip()
    name = str(item.get("name") or "").strip()
    if not site_id or not name:
        return None

    description = (
        str(item.get("description") or "").strip()
        or str(item.get("summary_fr") or "").strip()
        or str(item.get("summary_en") or "").strip()
    )
    slug = str(item.get("slug") or "").strip() or _slugify(name)
    region = str(item.get("region") or "").strip() or "Cameroon"
    city = str(item.get("city") or "").strip() or region
    category = str(item.get("category") or "").strip() or "site"

    tips = (
        str(item.get("tips_fr") or "").strip()
        or str(item.get("tips_en") or "").strip()
    )
    activities = item.get("activities") or item.get("tags") or []
    if not isinstance(activities, list):
        activities = []

    return TouristSiteRecord(
        id=site_id,
        name=name,
        slug=slug,
        region=region,
        city=city,
        category=category,
        description=description or name,
        history=str(item.get("history") or "").strip() or None,
        culture=str(item.get("culture") or "").strip() or None,
        activities=[str(a).strip() for a in activities if str(a).strip()],
        latitude=_as_float(item.get("latitude")),
        longitude=_as_float(item.get("longitude")),
        opening_hours=str(item.get("opening_hours") or "").strip() or None,
        price=str(item.get("price") or "").strip() or None,
        languages=[
            str(lang).strip()
            for lang in (item.get("languages") or [])
            if str(lang).strip()
        ],
        images=[
            str(image).strip()
            for image in (item.get("images") or [])
            if str(image).strip()
        ],
        sources=_to_sources(item.get("sources")),
    ) if description or tips or name else None


def _to_sources(value: object) -> list[SourceRecord]:
    if not isinstance(value, list):
        return []
    sources: list[SourceRecord] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "").strip()
        if not title:
            continue
        sources.append(
            SourceRecord(
                title=title,
                organization=str(entry.get("organization") or "").strip() or None,
                url=str(entry.get("url") or "").strip() or None,
                publication_date=(
                    str(entry.get("publication_date") or "").strip() or None
                ),
                verification_status=(
                    str(entry.get("verification_status") or "").strip() or "official"
                ),
            )
        )
    return sources


def _slugify(value: str) -> str:
    slug = _SLUG.sub("-", value.casefold()).strip("-")
    return slug or "site"


def _as_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _fold(value: str) -> str:
    return value.casefold().replace("é", "e").replace("è", "e").replace("ê", "e")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return 2 * radius * asin(sqrt(a))
