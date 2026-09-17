import pytest

from app.services.search.base import WebSearchHit
from app.services.search.composite import CompositeWebSearchService
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
