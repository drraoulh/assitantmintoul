import pytest

from app.services.ai.grounding import build_grounded_system_prompt, knowledge_covers_query
from app.services.rag.base import PlaceholderRAGService
from app.services.rag.chunk import KnowledgeChunk
from app.services.rag.local import LocalRAGService
from app.services.search.base import PlaceholderWebSearchService, WebSearchHit, WebSearchService


def test_knowledge_covers_typical_site_question() -> None:
    chunks = [
        KnowledgeChunk(
            id="1",
            title="Plages de Kribi",
            text="Kribi est une station balnéaire du sud camerounais.",
            source="tourist_sites/kribi.json",
            city="Kribi",
            region="Sud",
        ),
        KnowledgeChunk(
            id="2",
            title="Chutes de la Lobé",
            text="Chutes d'eau se jetant dans l'océan près de Kribi.",
            source="tourist_sites/kribi.json",
            city="Kribi",
            region="Sud",
        ),
    ]
    assert knowledge_covers_query("Que voir à Kribi ?", chunks)
    assert not knowledge_covers_query("Quel est le prix d'entrée à Kribi aujourd'hui ?", chunks)


@pytest.mark.asyncio
async def test_grounding_skips_web_when_kb_covers() -> None:
    class TrackingWeb(WebSearchService):
        def __init__(self) -> None:
            self.calls = 0

        async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchHit]:
            self.calls += 1
            return [WebSearchHit("should-not-run", "x", "https://example.com", "web")]

    web = TrackingWeb()
    prompt = await build_grounded_system_prompt(
        "Que voir à Kribi ?",
        [],
        rag_service=LocalRAGService(),
        web_search_service=web,
        rag_top_k=4,
        web_search_max_results=3,
        web_search_timeout_seconds=4,
    )
    assert "Curated knowledge base excerpts" in prompt
    assert "Live web search results" not in prompt
    assert web.calls == 0


@pytest.mark.asyncio
async def test_grounding_uses_web_when_kb_empty() -> None:
    class FakeWeb(WebSearchService):
        async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchHit]:
            return [
                WebSearchHit(
                    "Kribi",
                    "Plages du Cameroun",
                    "https://example.com/kribi",
                    "web",
                )
            ]

    prompt = await build_grounded_system_prompt(
        "Que voir à Kribi ?",
        [],
        rag_service=PlaceholderRAGService(),
        web_search_service=FakeWeb(),
        rag_top_k=4,
        web_search_max_results=3,
        web_search_timeout_seconds=4,
    )
    assert "Live web search results" in prompt
