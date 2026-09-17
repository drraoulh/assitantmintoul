import pytest

from app.services.search.base import WebSearchHit
from app.services.search.composite import CompositeWebSearchService
from app.services.search.open_web import OpenWebSearchService
from app.services.search.wikipedia import enrich_cameroon_query


def test_enrich_query_adds_cameroon_when_missing() -> None:
    assert "Cameroun" in enrich_cameroon_query("meilleures plages")
    assert enrich_cameroon_query("Kribi plages").startswith("Kribi")


@pytest.mark.asyncio
async def test_composite_web_search_merges_and_dedupes() -> None:
    class A:
        async def search(self, query: str, *, max_results: int = 5):
            return [
                WebSearchHit("Kribi", "Plages", "https://example.com/kribi", "a"),
                WebSearchHit("Douala", "Port", "https://example.com/douala", "a"),
            ]

    class B:
        async def search(self, query: str, *, max_results: int = 5):
            return [
                WebSearchHit("Kribi wiki", "Encore Kribi", "https://example.com/kribi", "b"),
                WebSearchHit("Waza", "Parc", "https://example.com/waza", "b"),
            ]

    service = CompositeWebSearchService(services=[A(), B()])  # type: ignore[arg-type]
    hits = await service.search("tourisme", max_results=3)
    assert len(hits) == 3
    urls = [hit.url for hit in hits]
    assert urls.count("https://example.com/kribi") == 1


def test_open_web_maps_organic_rows() -> None:
    hit = OpenWebSearchService._to_hit(
        {
            "title": "Kribi sur Facebook",
            "href": "https://www.facebook.com/groups/kribi.tourisme",
            "body": "Conseils de voyageurs pour Kribi.",
        }
    )
    assert hit is not None
    assert hit.source == "web:facebook.com"
    assert "facebook.com" in hit.url
    assert "Conseils" in hit.snippet


@pytest.mark.asyncio
async def test_open_web_search_uses_injected_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = OpenWebSearchService(timeout_seconds=5)

    def fake_sync(query: str, max_results: int):
        assert "Cameroun" in query or "Kribi" in query
        return [
            {
                "title": "TripAdvisor Kribi",
                "href": "https://www.tripadvisor.com/Kribi",
                "body": "Best beaches near Kribi",
            },
            {
                "title": "Page Facebook Kribi",
                "href": "https://facebook.com/kribi.guide",
                "body": "Photos et avis récents",
            },
        ][:max_results]

    monkeypatch.setattr(service, "_search_sync", fake_sync)
    hits = await service.search("Kribi plages", max_results=5)
    assert len(hits) == 2
    assert hits[0].source == "web:tripadvisor.com"
    assert hits[1].source == "web:facebook.com"
