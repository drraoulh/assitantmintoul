"""Optional async loader: Supabase structured places (+ eco_tags, activities)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import AsyncSessionLocal
from app.services.agents.knowledge.place_store import PlaceIndex, PlaceRecord

logger = logging.getLogger(__name__)


async def load_place_index_from_supabase(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    *,
    include_unpublished: bool = False,
) -> PlaceIndex:
    """Load published places with eco tags and activities from Supabase."""
    factory = session_factory or AsyncSessionLocal
    async with factory() as session:
        places = await _fetch_places(session, include_unpublished=include_unpublished)
        if not places:
            return PlaceIndex([])
        ids = [p.place_id for p in places]
        eco_map = await _fetch_eco_tags(session, ids)
        act_map = await _fetch_activities(session, ids)
        for place in places:
            place.eco_tags = eco_map.get(place.place_id, [])
            place.activities = act_map.get(place.place_id, place.activities)
    return PlaceIndex(places)


async def _fetch_places(
    session: AsyncSession,
    *,
    include_unpublished: bool,
) -> list[PlaceRecord]:
    published_clause = "" if include_unpublished else "where p.is_published = true"
    rows = (
        await session.execute(
            text(
                f"""
                select
                    p.id::text as place_id,
                    p.slug,
                    p.name_fr,
                    p.name_en,
                    coalesce(nullif(p.name_fr, ''), p.name_en, p.slug) as name,
                    coalesce(ci.name_fr, ci.name_en) as city,
                    coalesce(r.name_fr, r.name_en) as region,
                    coalesce(nullif(p.description_fr, ''), p.description_en) as description,
                    coalesce(nullif(p.cultural_info_fr, ''), p.cultural_info_en) as cultural_info,
                    coalesce(nullif(p.eco_info_fr, ''), p.eco_info_en) as eco_info,
                    coalesce(c.name_fr, c.name_en, c.slug) as category,
                    coalesce(z.name_fr, z.name_en) as cultural_zone,
                    p.estimated_cost_xaf,
                    p.recommended_duration_hours,
                    p.best_period,
                    p.is_published,
                    p.source_id::text as source_id,
                    s.name as source_name,
                    s.url as source_url,
                    ST_Y(p.location::geometry) as latitude,
                    ST_X(p.location::geometry) as longitude
                from places p
                left join regions r on r.id = p.region_id
                left join cities ci on ci.id = p.city_id
                left join categories c on c.id = p.category_id
                left join cultural_zones z on z.id = p.cultural_zone_id
                left join sources s on s.id = p.source_id
                {published_clause}
                order by coalesce(ci.name_fr, ''), coalesce(p.name_fr, '')
                """
            )
        )
    ).mappings().all()

    places: list[PlaceRecord] = []
    for row in rows:
        duration = row.get("recommended_duration_hours")
        cost = row.get("estimated_cost_xaf")
        places.append(
            PlaceRecord(
                place_id=str(row["place_id"]),
                name=str(row["name"]),
                name_fr=row.get("name_fr"),
                name_en=row.get("name_en"),
                slug=row.get("slug"),
                city=row.get("city"),
                region=row.get("region"),
                description=row.get("description"),
                cultural_info=row.get("cultural_info"),
                eco_info=row.get("eco_info"),
                activities=[],
                categories=[str(row["category"])] if row.get("category") else [],
                eco_tags=[],
                cultural_zone=row.get("cultural_zone"),
                estimated_cost_xaf=int(cost) if cost is not None else None,
                recommended_duration_hours=float(duration) if duration is not None else None,
                best_period=row.get("best_period"),
                latitude=_as_float(row.get("latitude")),
                longitude=_as_float(row.get("longitude")),
                source_id=row.get("source_id"),
                source_name=row.get("source_name"),
                source_url=row.get("source_url"),
                is_published=bool(row.get("is_published")),
            )
        )
    return places


async def _fetch_eco_tags(
    session: AsyncSession,
    place_ids: list[str],
) -> dict[str, list[str]]:
    if not place_ids:
        return {}
    try:
        rows = (
            await session.execute(
                text(
                    """
                    select pet.place_id::text as place_id,
                           coalesce(et.slug, et.name_fr, et.name_en) as tag
                    from place_eco_tags pet
                    join eco_tags et on et.id = pet.eco_tag_id
                    where pet.place_id::text = any(:ids)
                    """
                ),
                {"ids": place_ids},
            )
        ).mappings().all()
    except Exception:
        logger.exception("eco_tags join failed; continuing without eco tags")
        return {}

    out: dict[str, list[str]] = {}
    for row in rows:
        pid = str(row["place_id"])
        tag = str(row["tag"] or "").strip()
        if not tag:
            continue
        out.setdefault(pid, []).append(tag)
    return out


async def _fetch_activities(
    session: AsyncSession,
    place_ids: list[str],
) -> dict[str, list[str]]:
    if not place_ids:
        return {}
    try:
        rows = (
            await session.execute(
                text(
                    """
                    select place_id::text as place_id,
                           coalesce(nullif(name_fr, ''), name_en) as name
                    from place_activities
                    where place_id::text = any(:ids)
                    """
                ),
                {"ids": place_ids},
            )
        ).mappings().all()
    except Exception:
        logger.exception("place_activities join failed; continuing without activities")
        return {}

    out: dict[str, list[str]] = {}
    for row in rows:
        pid = str(row["place_id"])
        name = str(row["name"] or "").strip()
        if name:
            out.setdefault(pid, []).append(name)
    return out


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
