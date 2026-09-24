"""Cover-image fallback from the committed Ayila'a slug index."""

from __future__ import annotations

from app.services.tourism.catalog import SiteCatalog
from app.services.tourism.image_index import (
    enrich_images,
    image_url_for_place,
    primary_image_by_slug,
)


def test_primary_image_index_has_verified_https_urls() -> None:
    mapping = primary_image_by_slug()
    assert len(mapping) >= 90
    sample = next(iter(mapping.values()))
    assert sample.startswith("https://")


def test_image_url_for_place_matches_local_site_id() -> None:
    # Local JSON ids often equal export slugs (e.g. chutes-lancrenon-mbere).
    url = image_url_for_place(place_id="chutes-lancrenon-mbere")
    assert url is not None
    assert url.startswith("https://")


def test_enrich_images_keeps_existing() -> None:
    existing = ["https://cdn.example.com/a.jpg"]
    assert enrich_images(existing, slug="chutes-lancrenon-mbere") == existing


def test_enrich_images_fills_empty_from_index() -> None:
    filled = enrich_images([], place_id="chutes-lancrenon-mbere")
    assert len(filled) == 1
    assert filled[0].startswith("https://")


def test_site_catalog_attaches_cover_images() -> None:
    catalog = SiteCatalog()
    with_images = [s for s in catalog.all() if s.images]
    assert len(with_images) >= 80
    sample = with_images[0]
    assert sample.images[0].startswith("https://")
