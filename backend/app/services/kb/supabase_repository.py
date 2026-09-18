from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import AsyncSessionLocal
from app.schemas.tourism import SourceRecord, TouristSiteRecord
from app.services.rag.chunk import KnowledgeChunk

logger = logging.getLogger(__name__)


def _image_url(row: dict[str, Any]) -> str | None:
    for key in ("original_url", "storage_path"):
        value = str(row.get(key) or "").strip()
        if value.startswith(("http://", "https://")):
            return value
    return None


class SupabaseKnowledgeRepository:
    """Read the curated Cameroon tourism schema already living in Supabase.

    Source of truth tables: places, regions, cities, categories, cultural_*,
    phrases, sources. The `knowledge_chunks` table is the denormalized mirror
    used by RAG (rebuilt by `scripts/sync_knowledge_base.py`).
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session_factory = session_factory or AsyncSessionLocal

    async def load_chunks(self) -> list[KnowledgeChunk]:
        """Prefer synced `knowledge_chunks`, always append live region blurbs."""
        try:
            stored = await self._load_stored_chunks()
            async with self._session_factory() as session:
                regions = await self._region_chunks(session)
            if stored:
                return _dedupe([*stored, *regions])
            return await self.build_chunks_from_tables()
        except Exception:
            logger.exception("Failed to load Supabase knowledge chunks")
            return []

    async def build_chunks_from_tables(self) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        async with self._session_factory() as session:
            chunks.extend(await self._place_chunks(session))
            chunks.extend(await self._region_chunks(session))
            chunks.extend(await self._cultural_topic_chunks(session))
            chunks.extend(await self._phrase_chunks(session))
        logger.info("Built %s knowledge chunks from Supabase tables", len(chunks))
        return chunks

    async def sync_knowledge_chunks(self) -> int:
        """Rebuild allowed rows in `knowledge_chunks` (place/cultural_topic/phrase)."""
        chunks = await self.build_chunks_from_tables()
        # DB check: source_type IN ('place', 'cultural_topic', 'phrase')
        allowed = [
            chunk
            for chunk in chunks
            if chunk.id.startswith(("place:", "cultural_topic:", "phrase:"))
        ]
        async with self._session_factory() as session:
            await session.execute(
                text(
                    """
                    delete from knowledge_chunks
                    where source_type in ('place', 'cultural_topic', 'phrase')
                    """
                )
            )
            for chunk in allowed:
                source_type, _, rest = chunk.id.partition(":")
                source_id = rest or None
                place_id = source_id if source_type == "place" else None
                meta = {
                    "city": chunk.city,
                    "region": chunk.region,
                    "category": chunk.category,
                    "tags": list(chunk.tags),
                    "images": list(chunk.images),
                    "source": chunk.source,
                    "legacy_id": chunk.id,
                }
                await session.execute(
                    text(
                        """
                        insert into knowledge_chunks (
                            id, source_type, source_id, place_id, locale,
                            title, content, metadata, created_at
                        ) values (
                            :id, :source_type,
                            cast(:source_id as uuid),
                            cast(:place_id as uuid),
                            :locale, :title, :content,
                            cast(:metadata as jsonb),
                            now()
                        )
                        """
                    ),
                    {
                        "id": str(uuid4()),
                        "source_type": source_type,
                        "source_id": source_id,
                        "place_id": place_id,
                        "locale": "fr",
                        "title": chunk.title[:500],
                        "content": chunk.text,
                        "metadata": _json_dumps(meta),
                    },
                )
            await session.commit()
        return len(allowed)

    async def list_site_records(self) -> list[TouristSiteRecord]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        """
                        select
                            p.id::text as id,
                            p.slug,
                            coalesce(nullif(p.name_fr, ''), p.name_en, p.slug) as name,
                            coalesce(r.name_fr, r.name_en, 'Cameroon') as region,
                            coalesce(ci.name_fr, ci.name_en, r.name_fr, 'Cameroon') as city,
                            coalesce(c.name_fr, c.name_en, c.slug, 'site') as category,
                            coalesce(
                                nullif(p.description_fr, ''),
                                nullif(p.description_en, ''),
                                coalesce(nullif(p.name_fr, ''), p.name_en, p.slug)
                            ) as description,
                            p.cultural_info_fr as culture,
                            p.estimated_cost_xaf,
                            p.cost_reliability,
                            p.best_period,
                            p.recommended_duration_hours,
                            s.name as source_name,
                            s.url as source_url,
                            ST_Y(p.location::geometry) as latitude,
                            ST_X(p.location::geometry) as longitude
                        from places p
                        left join regions r on r.id = p.region_id
                        left join cities ci on ci.id = p.city_id
                        left join categories c on c.id = p.category_id
                        left join sources s on s.id = p.source_id
                        where p.is_published = true
                        order by coalesce(ci.name_fr, ''), coalesce(p.name_fr, '')
                        """
                    )
                )
            ).mappings().all()

        images_by_place = await self._load_images_by_place(
            [str(row["id"]) for row in rows]
        )
        records: list[TouristSiteRecord] = []
        for row in rows:
            sources: list[SourceRecord] = []
            if row.get("source_name"):
                sources.append(
                    SourceRecord(
                        title=str(row["source_name"]),
                        organization=str(row["source_name"]),
                        url=row.get("source_url"),
                        verification_status="official",
                    )
                )
            price = None
            if row.get("estimated_cost_xaf") is not None:
                reliability = row.get("cost_reliability") or "estimated"
                price = f"{int(row['estimated_cost_xaf'])} XAF ({reliability})"
            duration = row.get("recommended_duration_hours")
            activities = []
            if duration is not None:
                activities.append(f"durée recommandée ≈ {duration} h")
            if row.get("best_period"):
                activities.append(f"meilleure période: {row['best_period']}")

            place_id = str(row["id"])
            records.append(
                TouristSiteRecord(
                    id=place_id,
                    name=str(row["name"]),
                    slug=str(row["slug"]),
                    region=str(row["region"]),
                    city=str(row["city"]),
                    category=str(row["category"]),
                    description=str(row["description"]),
                    history=None,
                    culture=str(row["culture"]).strip() if row.get("culture") else None,
                    activities=activities,
                    latitude=_as_float(row.get("latitude")),
                    longitude=_as_float(row.get("longitude")),
                    opening_hours=None,
                    price=price,
                    languages=["fr", "en"],
                    images=images_by_place.get(place_id, []),
                    sources=sources,
                )
            )
        return records

    async def _load_stored_chunks(self) -> list[KnowledgeChunk]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        """
                        select id::text as id, source_type, title, content, metadata
                        from knowledge_chunks
                        where content is not null and length(trim(content)) > 0
                        order by created_at
                        """
                    )
                )
            ).mappings().all()

        chunks: list[KnowledgeChunk] = []
        for row in rows:
            meta = row.get("metadata") or {}
            if isinstance(meta, str):
                meta = _json_loads(meta)
            if not isinstance(meta, dict):
                meta = {}
            tags = meta.get("tags") or []
            if not isinstance(tags, list):
                tags = []
            images = meta.get("images") or []
            if not isinstance(images, list):
                images = []
            legacy_id = str(meta.get("legacy_id") or "").strip()
            chunk_id = legacy_id or f"{row['source_type']}:{row['id']}"
            chunks.append(
                KnowledgeChunk(
                    id=chunk_id,
                    title=str(row["title"] or "Sans titre"),
                    text=str(row["content"]),
                    source=str(meta.get("source") or f"supabase/{row['source_type']}"),
                    city=meta.get("city"),
                    region=meta.get("region"),
                    category=meta.get("category"),
                    tags=tuple(str(tag) for tag in tags if str(tag).strip()),
                    images=tuple(str(url) for url in images if str(url).strip()),
                )
            )
        return await self._enrich_place_images(chunks)

    async def _load_images_by_place(
        self,
        place_ids: list[str],
    ) -> dict[str, list[str]]:
        """Map place_id → ordered image URLs from `place_images`."""
        ids = [pid for pid in place_ids if pid]
        if not ids:
            return {}
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        """
                        select
                            place_id::text as place_id,
                            original_url,
                            storage_path,
                            coalesce(is_primary, false) as is_primary
                        from place_images
                        where place_id::text = any(:ids)
                        order by coalesce(is_primary, false) desc, created_at nulls last
                        """
                    ),
                    {"ids": ids},
                )
            ).mappings().all()

        by_place: dict[str, list[str]] = {}
        for row in rows:
            url = _image_url(dict(row))
            if not url:
                continue
            place_id = str(row["place_id"])
            bucket = by_place.setdefault(place_id, [])
            if url not in bucket:
                bucket.append(url)
        return by_place

    async def _enrich_place_images(
        self,
        chunks: list[KnowledgeChunk],
    ) -> list[KnowledgeChunk]:
        """Attach live `place_images` URLs when chunk metadata has none yet."""
        need: list[str] = []
        for chunk in chunks:
            if chunk.images:
                continue
            if not chunk.id.startswith("place:"):
                continue
            place_id = chunk.id.partition(":")[2]
            if place_id:
                need.append(place_id)
        if not need:
            return chunks

        images_by_place = await self._load_images_by_place(need)
        if not images_by_place:
            return chunks

        enriched: list[KnowledgeChunk] = []
        for chunk in chunks:
            if chunk.images or not chunk.id.startswith("place:"):
                enriched.append(chunk)
                continue
            place_id = chunk.id.partition(":")[2]
            urls = tuple(images_by_place.get(place_id, []))
            if not urls:
                enriched.append(chunk)
                continue
            text = chunk.text
            if "Image:" not in text:
                text = f"{text}\nImage: {urls[0]}"
            enriched.append(replace(chunk, images=urls, text=text))
        return enriched

    async def _place_chunks(self, session: AsyncSession) -> list[KnowledgeChunk]:
        rows = (
            await session.execute(
                text(
                    """
                    select
                        p.id::text as id,
                        p.slug,
                        coalesce(nullif(p.name_fr, ''), p.name_en, p.slug) as name,
                        coalesce(r.name_fr, r.name_en) as region,
                        coalesce(ci.name_fr, ci.name_en) as city,
                        coalesce(c.name_fr, c.name_en, c.slug) as category,
                        p.description_fr,
                        p.description_en,
                        p.cultural_info_fr,
                        p.cultural_info_en,
                        p.eco_info_fr,
                        p.eco_info_en,
                        p.community_activities_fr,
                        p.local_guide_info_fr,
                        p.estimated_cost_xaf,
                        p.cost_reliability,
                        p.best_period,
                        p.recommended_duration_hours,
                        s.name as source_name
                    from places p
                    left join regions r on r.id = p.region_id
                    left join cities ci on ci.id = p.city_id
                    left join categories c on c.id = p.category_id
                    left join sources s on s.id = p.source_id
                    where p.is_published = true
                    """
                )
            )
        ).mappings().all()

        images_by_place = await self._load_images_by_place(
            [str(row["id"]) for row in rows]
        )
        chunks: list[KnowledgeChunk] = []
        for row in rows:
            lines = [
                f"Lieu: {row['name']}",
            ]
            if row.get("city"):
                lines.append(f"Ville: {row['city']}")
            if row.get("region"):
                lines.append(f"Région: {row['region']}")
            if row.get("category"):
                lines.append(f"Catégorie: {row['category']}")
            for label, key in (
                ("Description FR", "description_fr"),
                ("Description EN", "description_en"),
                ("Culture FR", "cultural_info_fr"),
                ("Culture EN", "cultural_info_en"),
                ("Éco FR", "eco_info_fr"),
                ("Activités communautaires", "community_activities_fr"),
                ("Guide local", "local_guide_info_fr"),
            ):
                value = str(row.get(key) or "").strip()
                if value:
                    lines.append(f"{label}: {value}")
            if row.get("estimated_cost_xaf") is not None:
                lines.append(
                    "Coût estimé: "
                    f"{int(row['estimated_cost_xaf'])} XAF "
                    f"({row.get('cost_reliability') or 'estimated'})"
                )
            if row.get("best_period"):
                lines.append(f"Meilleure période: {row['best_period']}")
            if row.get("recommended_duration_hours") is not None:
                lines.append(
                    f"Durée recommandée: {row['recommended_duration_hours']} heures"
                )
            if row.get("source_name"):
                lines.append(f"Source: {row['source_name']}")

            place_id = str(row["id"])
            image_urls = tuple(images_by_place.get(place_id, []))
            if image_urls:
                lines.append(f"Image: {image_urls[0]}")
            chunks.append(
                KnowledgeChunk(
                    id=f"place:{place_id}",
                    title=str(row["name"]),
                    text="\n".join(lines),
                    source="supabase/places",
                    city=row.get("city"),
                    region=row.get("region"),
                    category=row.get("category"),
                    tags=(row.get("slug") or "", row.get("category") or ""),
                    images=image_urls,
                )
            )
        return chunks

    async def _region_chunks(self, session: AsyncSession) -> list[KnowledgeChunk]:
        rows = (
            await session.execute(
                text(
                    """
                    select
                        r.id::text as id,
                        r.slug,
                        coalesce(r.name_fr, r.name_en, r.slug) as name,
                        count(p.id) as place_count
                    from regions r
                    left join places p
                        on p.region_id = r.id and p.is_published = true
                    group by r.id, r.slug, r.name_fr, r.name_en
                    order by name
                    """
                )
            )
        ).mappings().all()
        return [
            KnowledgeChunk(
                id=f"region:{row['id']}",
                title=f"Région {row['name']}",
                text=(
                    f"Région du Cameroun: {row['name']} (slug {row['slug']}). "
                    f"{int(row['place_count'])} lieux publiés dans la base touristique."
                ),
                source="supabase/regions",
                region=str(row["name"]),
                category="region",
                tags=(row["slug"] or "", "region"),
            )
            for row in rows
        ]

    async def _cultural_topic_chunks(
        self,
        session: AsyncSession,
    ) -> list[KnowledgeChunk]:
        rows = (
            await session.execute(
                text(
                    """
                    select
                        t.id::text as id,
                        t.topic_type,
                        coalesce(t.title_fr, t.title_en) as title,
                        t.body_fr,
                        t.body_en,
                        z.name_fr as zone_name
                    from cultural_topics t
                    left join cultural_zones z on z.id = t.cultural_zone_id
                    where t.is_published = true
                    """
                )
            )
        ).mappings().all()
        chunks: list[KnowledgeChunk] = []
        for row in rows:
            lines = [f"Sujet culturel: {row['title']}"]
            if row.get("zone_name"):
                lines.append(f"Zone: {row['zone_name']}")
            if row.get("topic_type"):
                lines.append(f"Type: {row['topic_type']}")
            if row.get("body_fr"):
                lines.append(f"FR: {row['body_fr']}")
            if row.get("body_en"):
                lines.append(f"EN: {row['body_en']}")
            chunks.append(
                KnowledgeChunk(
                    id=f"cultural_topic:{row['id']}",
                    title=str(row["title"]),
                    text="\n".join(lines),
                    source="supabase/cultural_topics",
                    category="culture",
                    tags=(row.get("topic_type") or "culture", row.get("zone_name") or ""),
                )
            )
        return chunks

    async def _phrase_chunks(self, session: AsyncSession) -> list[KnowledgeChunk]:
        rows = (
            await session.execute(
                text(
                    """
                    select
                        p.id::text as id,
                        p.phrase_local,
                        p.translation_fr,
                        p.translation_en,
                        p.pronunciation,
                        p.cultural_context_fr,
                        l.name_fr as language_name,
                        l.slug as language_slug
                    from phrases p
                    left join languages l on l.id = p.language_id
                    where p.is_published = true
                    """
                )
            )
        ).mappings().all()
        chunks: list[KnowledgeChunk] = []
        for row in rows:
            lines = [
                f"Phrase utile ({row.get('language_name') or row.get('language_slug')})",
                f"Local: {row['phrase_local']}",
            ]
            if row.get("translation_fr"):
                lines.append(f"FR: {row['translation_fr']}")
            if row.get("translation_en"):
                lines.append(f"EN: {row['translation_en']}")
            if row.get("pronunciation"):
                lines.append(f"Prononciation: {row['pronunciation']}")
            if row.get("cultural_context_fr"):
                lines.append(f"Contexte: {row['cultural_context_fr']}")
            chunks.append(
                KnowledgeChunk(
                    id=f"phrase:{row['id']}",
                    title=str(row["phrase_local"]),
                    text="\n".join(lines),
                    source="supabase/phrases",
                    category="language",
                    tags=("phrase", row.get("language_slug") or ""),
                )
            )
        return chunks


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_dumps(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


def _json_loads(value: str) -> dict[str, Any]:
    import json

    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _dedupe(chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
    seen: set[str] = set()
    unique: list[KnowledgeChunk] = []
    for chunk in chunks:
        key = chunk.id.strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(chunk)
    return unique
