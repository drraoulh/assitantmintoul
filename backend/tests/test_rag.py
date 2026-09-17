import pytest

from app.services.rag.context import build_system_prompt, format_knowledge_context
from app.services.rag.loader import load_knowledge_chunks
from app.services.rag.local import LocalRAGService
from app.services.tourism.local import LocalTourismService


def test_knowledge_base_loads_curated_chunks() -> None:
    chunks = load_knowledge_chunks()
    assert len(chunks) >= 70
    sources = {chunk.source.split("/", maxsplit=1)[0] for chunk in chunks}
    assert "tourist_sites" in sources
    assert "documents" in sources


@pytest.mark.asyncio
async def test_local_rag_retrieves_monument() -> None:
    rag = LocalRAGService()
    chunks = await rag.retrieve_chunks(
        "Monument de la Réunification et basilique à Yaoundé",
        top_k=5,
    )
    assert chunks
    joined = " ".join(chunk.text.lower() for chunk in chunks)
    assert "yaound" in joined
    assert any(
        word in joined
        for word in ("réunification", "reunification", "basilique", "monument", "musée", "musee")
    )


@pytest.mark.asyncio
async def test_local_rag_retrieves_national_park() -> None:
    rag = LocalRAGService()
    chunks = await rag.retrieve_chunks("parc national de Waza safari", top_k=4)
    assert chunks
    joined = " ".join(chunk.text.lower() for chunk in chunks)
    assert "waza" in joined


@pytest.mark.asyncio
async def test_local_rag_retrieves_yaounde_sites() -> None:
    rag = LocalRAGService()
    chunks = await rag.retrieve_chunks(
        "Quels sont les sites touristiques de Yaoundé ?",
        top_k=4,
    )
    assert chunks
    joined = " ".join(chunk.text.lower() for chunk in chunks)
    assert "yaound" in joined
    assert any(
        keyword in joined
        for keyword in ("monument", "musée", "musee", "mokolo", "fébé", "febe")
    )


@pytest.mark.asyncio
async def test_local_rag_retrieves_kribi_waterfall() -> None:
    rag = LocalRAGService()
    texts = await rag.retrieve("chutes de la Lobé près de Kribi", top_k=3)
    assert texts
    joined = " ".join(texts).lower()
    assert "lob" in joined
    assert "kribi" in joined


@pytest.mark.asyncio
async def test_local_rag_retrieves_food_context() -> None:
    rag = LocalRAGService()
    chunks = await rag.retrieve_chunks("Que manger au Cameroun ? ndolé", top_k=3)
    assert chunks
    joined = " ".join(chunk.text.lower() for chunk in chunks)
    assert "ndol" in joined or "cuisine" in joined or "plat" in joined


def test_format_knowledge_context_and_prompt() -> None:
    rag_chunks = load_knowledge_chunks()[:2]
    context = format_knowledge_context(rag_chunks)
    assert "[1]" in context
    prompt = build_system_prompt("Base prompt.", context)
    assert "Curated knowledge base excerpts" in prompt
    assert rag_chunks[0].title in prompt


@pytest.mark.asyncio
async def test_local_tourism_find_sites_for_douala() -> None:
    tourism = LocalTourismService()
    sites = await tourism.find_sites("Douala")
    assert len(sites) >= 3
    assert all("douala" in str(site.get("city") or "").lower() for site in sites)

    itinerary = await tourism.build_itinerary("Douala", hours=4)
    assert itinerary["city"] == "Douala"
    assert 1 <= len(itinerary["stops"]) <= 2
