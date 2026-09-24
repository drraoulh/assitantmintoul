from __future__ import annotations

import logging

from app.core.config import get_settings
from app.schemas.tourism import TouristSiteRecord
from app.services.tourism.catalog import SiteCatalog
from app.services.tourism.image_index import enrich_images

logger = logging.getLogger(__name__)

_catalog: SiteCatalog | None = None


def get_site_catalog() -> SiteCatalog:
    """Return the warmed Supabase catalog when available, else local JSON."""
    if _catalog is not None:
        return _catalog
    return SiteCatalog()


def set_site_catalog(catalog: SiteCatalog) -> None:
    global _catalog
    _catalog = catalog


async def warm_tourism_knowledge(*, sync: bool = False) -> dict[str, int]:
    """Warm the site catalog from Supabase places.

    Set sync=True (or run `python -m scripts.sync_knowledge_base`) to rebuild
    the `knowledge_chunks` table. Startup only loads what is already there.
    """
    settings = get_settings()
    stats = {"places": 0, "chunks": 0, "synced": 0}
    if not settings.database_enabled:
        set_site_catalog(SiteCatalog())
        return stats

    from app.services.kb.supabase_repository import SupabaseKnowledgeRepository
    from app.services.rag.factory import refresh_rag_service

    repo = SupabaseKnowledgeRepository()
    if sync:
        try:
            stats["synced"] = await repo.sync_knowledge_chunks()
        except Exception:
            logger.exception("knowledge_chunks sync failed; continuing with live joins")

    records: list[TouristSiteRecord] = []
    try:
        records = await repo.list_site_records()
    except Exception:
        logger.exception("Place listing with geometry failed; retrying without GPS")
        try:
            records = await _list_sites_without_geometry(repo)
        except Exception:
            logger.exception("Plain place listing also failed")

    if records:
        records = [_with_cover_image(site) for site in records]
        set_site_catalog(SiteCatalog(sites=records))
        stats["places"] = len(records)
    else:
        set_site_catalog(SiteCatalog())

    # Force the next RAG call to re-read Supabase + files.
    refresh_rag_service()
    try:
        chunks = await repo.load_chunks()
        stats["chunks"] = len(chunks)
    except Exception:
        logger.exception("Could not count knowledge chunks after warm-up")

    logger.info(
        "Tourism knowledge warmed: places=%s chunks=%s synced=%s",
        stats["places"],
        stats["chunks"],
        stats["synced"],
    )
    return stats


async def _list_sites_without_geometry(repo) -> list[TouristSiteRecord]:
    from sqlalchemy import text

    records: list[TouristSiteRecord] = []
    async with repo._session_factory() as session:
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
                        p.cultural_info_fr as culture
                    from places p
                    left join regions r on r.id = p.region_id
                    left join cities ci on ci.id = p.city_id
                    left join categories c on c.id = p.category_id
                    where p.is_published = true
                    order by coalesce(ci.name_fr, ''), coalesce(p.name_fr, '')
                    """
                )
            )
        ).mappings().all()
    for row in rows:
        records.append(
            _with_cover_image(
                TouristSiteRecord(
                    id=str(row["id"]),
                    name=str(row["name"]),
                    slug=str(row["slug"]),
                    region=str(row["region"]),
                    city=str(row["city"]),
                    category=str(row["category"]),
                    description=str(row["description"]),
                    culture=str(row["culture"]).strip() if row.get("culture") else None,
                )
            )
        )
    return records


def _with_cover_image(site: TouristSiteRecord) -> TouristSiteRecord:
    images = enrich_images(site.images, slug=site.slug, place_id=site.id)
    if images == site.images:
        return site
    return site.model_copy(update={"images": images})
