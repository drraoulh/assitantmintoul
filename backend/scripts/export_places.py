#!/usr/bin/env python3
"""Export Supabase tourist places (+ images) to a local folder.

Examples:
  python -m scripts.export_places
  python -m scripts.export_places --include-restaurants
  python -m scripts.export_places --no-images --out /tmp/places
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import mimetypes
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Default: lieux touristiques (skip restauration).
TOURIST_CATEGORY_SLUGS = {
    "activite",
    "parc",
    "musee",
    "cascade",
    "plage",
    "montagne",
    "monument",
    "patrimoine-culturel",
    "reserve",
}


def _async_db_url(raw: str) -> str:
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _safe_name(value: str, fallback: str = "item") -> str:
    cleaned = re.sub(r"[^\w.\-]+", "_", (value or "").strip(), flags=re.UNICODE)
    cleaned = cleaned.strip("._") or fallback
    return cleaned[:120]


def _image_url(row: dict[str, Any]) -> str | None:
    for key in ("original_url", "storage_path"):
        value = str(row.get(key) or "").strip()
        if value.startswith(("http://", "https://")):
            return value
    return None


def _guess_extension(url: str, content_type: str | None) -> str:
    path = unquote(urlparse(url).path)
    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed == ".jpe":
            return ".jpg"
        if guessed:
            return guessed
    return ".jpg"


async def _fetch_places(
    *,
    include_restaurants: bool,
) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured.")

    engine = create_async_engine(_async_db_url(settings.database_url), pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        """
                        select
                          p.id::text as id,
                          p.slug,
                          p.name_fr,
                          p.name_en,
                          p.description_fr,
                          p.description_en,
                          p.cultural_info_fr,
                          p.cultural_info_en,
                          p.eco_info_fr,
                          p.eco_info_en,
                          p.community_activities_fr,
                          p.community_activities_en,
                          p.local_guide_info_fr,
                          p.local_guide_info_en,
                          p.estimated_cost_xaf,
                          p.cost_reliability,
                          p.recommended_duration_hours,
                          p.best_period,
                          p.has_local_guide,
                          p.is_published,
                          p.verified_at,
                          p.created_at,
                          p.updated_at,
                          r.slug as region_slug,
                          r.name_fr as region_fr,
                          r.name_en as region_en,
                          c.slug as city_slug,
                          c.name_fr as city_fr,
                          c.name_en as city_en,
                          cat.slug as category_slug,
                          cat.name_fr as category_fr,
                          cat.name_en as category_en,
                          case
                            when p.location is null then null
                            else st_y(p.location::geometry)
                          end as lat,
                          case
                            when p.location is null then null
                            else st_x(p.location::geometry)
                          end as lng
                        from places p
                        left join regions r on r.id = p.region_id
                        left join cities c on c.id = p.city_id
                        left join categories cat on cat.id = p.category_id
                        where p.is_published is true
                        order by coalesce(r.name_fr, ''), coalesce(p.name_fr, '')
                        """
                    )
                )
            ).mappings().all()

            images = (
                await conn.execute(
                    text(
                        """
                        select
                          id::text as id,
                          place_id::text as place_id,
                          storage_path,
                          original_url,
                          alt_fr,
                          alt_en,
                          author,
                          license,
                          source_name,
                          retrieved_at,
                          is_primary,
                          created_at
                        from place_images
                        order by is_primary desc nulls last, created_at asc nulls last
                        """
                    )
                )
            ).mappings().all()
    finally:
        await engine.dispose()

    images_by_place: dict[str, list[dict[str, Any]]] = {}
    for row in images:
        item = dict(row)
        item["url"] = _image_url(item)
        images_by_place.setdefault(str(item["place_id"]), []).append(item)

    places: list[dict[str, Any]] = []
    for row in rows:
        place = dict(row)
        category = (place.get("category_slug") or "").strip().lower()
        if not include_restaurants:
            if category == "restauration":
                continue
            if category and category not in TOURIST_CATEGORY_SLUGS:
                continue
        place_id = str(place["id"])
        place["images"] = images_by_place.get(place_id, [])
        places.append(place)
    return places


async def _download_images(
    places: list[dict[str, Any]],
    images_root: Path,
    *,
    concurrency: int = 8,
) -> dict[str, int]:
    images_root.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(concurrency)
    stats = {"attempted": 0, "saved": 0, "failed": 0, "skipped": 0}

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(45.0, connect=10.0),
        follow_redirects=True,
        headers={"User-Agent": "SmartmboaTour-Export/1.0"},
    ) as client:

        async def one(place: dict[str, Any], image: dict[str, Any], index: int) -> None:
            url = image.get("url")
            if not url:
                stats["skipped"] += 1
                return
            stats["attempted"] += 1
            slug = _safe_name(str(place.get("slug") or place.get("id")), "place")
            place_dir = images_root / slug
            place_dir.mkdir(parents=True, exist_ok=True)
            async with sem:
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    ext = _guess_extension(url, response.headers.get("content-type"))
                    primary = "primary" if image.get("is_primary") else f"{index + 1:02d}"
                    filename = f"{primary}{ext}"
                    path = place_dir / filename
                    path.write_bytes(response.content)
                    image["local_path"] = str(path.relative_to(images_root.parent))
                    stats["saved"] += 1
                except Exception as exc:  # noqa: BLE001
                    stats["failed"] += 1
                    image["download_error"] = str(exc)
                    logger.warning("Image download failed for %s: %s", url[:80], exc)

        tasks = [
            one(place, image, index)
            for place in places
            for index, image in enumerate(place.get("images") or [])
        ]
        if tasks:
            await asyncio.gather(*tasks)
    return stats


async def export_places(
    out_dir: Path,
    *,
    include_restaurants: bool = False,
    download_images: bool = True,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    places = await _fetch_places(include_restaurants=include_restaurants)
    image_stats = {"attempted": 0, "saved": 0, "failed": 0, "skipped": 0}
    if download_images:
        image_stats = await _download_images(places, out_dir / "images")

    payload = {
        "exported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "include_restaurants": include_restaurants,
        "place_count": len(places),
        "image_count": sum(len(p.get("images") or []) for p in places),
        "download": image_stats,
        "places": places,
    }
    (out_dir / "places.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )

    # Compact CSV-friendly summary
    summary_rows = []
    for place in places:
        urls = [img.get("url") for img in place.get("images") or [] if img.get("url")]
        summary_rows.append(
            {
                "slug": place.get("slug"),
                "name_fr": place.get("name_fr"),
                "name_en": place.get("name_en"),
                "region": place.get("region_fr"),
                "city": place.get("city_fr"),
                "category": place.get("category_fr"),
                "lat": place.get("lat"),
                "lng": place.get("lng"),
                "image_count": len(place.get("images") or []),
                "primary_image": urls[0] if urls else None,
            }
        )
    (out_dir / "places_summary.json").write_text(
        json.dumps(summary_rows, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )

    readme = f"""# Export lieux touristiques Smartmboa

- Date: {payload['exported_at']}
- Lieux: {payload['place_count']}
- Images référencées: {payload['image_count']}
- Images téléchargées: {image_stats.get('saved', 0)}
- Restauration incluse: {include_restaurants}

Fichiers:
- `places.json` — export complet (textes FR/EN + métadonnées + URLs + chemins locaux)
- `places_summary.json` — vue condensée
- `images/<slug>/` — fichiers image téléchargés
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")
    return {
        "out_dir": str(out_dir),
        "place_count": payload["place_count"],
        "image_count": payload["image_count"],
        **image_stats,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="exports/supabase-tourist-places",
        help="Output directory (default: exports/supabase-tourist-places)",
    )
    parser.add_argument(
        "--include-restaurants",
        action="store_true",
        help="Also export category `restauration`",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip downloading image files (keep URLs only)",
    )
    args = parser.parse_args()
    out_dir = Path(args.out).resolve()
    result = asyncio.run(
        export_places(
            out_dir,
            include_restaurants=args.include_restaurants,
            download_images=not args.no_images,
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
