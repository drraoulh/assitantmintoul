"""Internal place records for structured retrieval (schema-aligned)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.schemas.tourism import TouristSiteRecord


def fold(text: str) -> str:
    lowered = (text or "").casefold().strip()
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


@dataclass
class PlaceRecord:
    """Normalized place row — mirrors Supabase `places` (+ joins) fields we use."""

    place_id: str
    name: str
    name_fr: str | None = None
    name_en: str | None = None
    slug: str | None = None
    city: str | None = None
    region: str | None = None
    description: str | None = None
    cultural_info: str | None = None
    eco_info: str | None = None
    activities: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    eco_tags: list[str] = field(default_factory=list)
    cultural_zone: str | None = None
    estimated_cost_xaf: int | None = None
    recommended_duration_hours: float | None = None
    best_period: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    source_id: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    is_published: bool = True

    def searchable_blob(self) -> str:
        parts = [
            self.name,
            self.name_fr or "",
            self.name_en or "",
            self.slug or "",
            self.city or "",
            self.region or "",
            self.description or "",
            self.cultural_info or "",
            self.eco_info or "",
            self.cultural_zone or "",
            " ".join(self.activities),
            " ".join(self.categories),
            " ".join(self.eco_tags),
        ]
        return fold(" ".join(parts))


_PRICE_NUM = re.compile(r"(\d[\d\s.,]{2,})")


def place_from_site_record(site: TouristSiteRecord) -> PlaceRecord:
    """Map catalog / API TouristSiteRecord → PlaceRecord (no invention)."""
    cost: int | None = None
    if site.price:
        match = _PRICE_NUM.search(site.price)
        if match:
            digits = re.sub(r"[^\d]", "", match.group(1))
            if digits:
                value = int(digits)
                if value >= 1000:
                    cost = value

    categories = [site.category] if site.category else []
    eco_tags: list[str] = []
    cat_fold = fold(site.category or "")
    if any(k in cat_fold for k in ("natural", "park", "garden", "nature", "parc", "eco")):
        eco_tags.append("nature")
    act_fold = fold(" ".join(site.activities))
    if any(k in act_fold for k in ("hik", "wildlife", "forest", "nature", "parc", "trek")):
        if "nature" not in eco_tags:
            eco_tags.append("nature")

    source_id = None
    source_name = None
    source_url = None
    if site.sources:
        src = site.sources[0]
        source_name = src.title or src.organization
        source_url = src.url
        source_id = fold(source_name or site.id)[:64] or site.id

    return PlaceRecord(
        place_id=site.id,
        name=site.name,
        name_fr=site.name,
        name_en=site.name,
        slug=site.slug,
        city=site.city or None,
        region=site.region or None,
        description=site.description or None,
        cultural_info=site.culture or None,
        eco_info=None,
        activities=list(site.activities or []),
        categories=categories,
        eco_tags=eco_tags,
        estimated_cost_xaf=cost,
        latitude=site.latitude,
        longitude=site.longitude,
        source_id=source_id,
        source_name=source_name,
        source_url=source_url,
        is_published=True,
    )


class PlaceIndex:
    """In-memory published place index for fast structured filters."""

    def __init__(self, places: list[PlaceRecord] | None = None) -> None:
        self._places = [p for p in (places or []) if p.is_published]

    @property
    def places(self) -> list[PlaceRecord]:
        return list(self._places)

    def __len__(self) -> int:
        return len(self._places)

    @classmethod
    def from_site_records(cls, records: list[TouristSiteRecord]) -> PlaceIndex:
        return cls([place_from_site_record(r) for r in records])

    @classmethod
    def from_catalog(cls) -> PlaceIndex:
        from app.services.tourism.catalog import SiteCatalog

        return cls.from_site_records(SiteCatalog().all())
