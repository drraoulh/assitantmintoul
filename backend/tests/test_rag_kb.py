import pytest

from app.services.rag.chunk import KnowledgeChunk
from app.services.rag.loader import load_knowledge_chunks
from app.services.rag.local import LocalRAGService


def test_loader_reads_nested_regional_sites() -> None:
    chunks = load_knowledge_chunks()
    assert len(chunks) >= 20
    titles = {chunk.title for chunk in chunks}
    assert any("Musée" in title or "Museum" in title or "Mont" in title for title in titles)


@pytest.mark.asyncio
async def test_local_rag_finds_kribi_style_query() -> None:
    chunks = [
        KnowledgeChunk(
            id="place:1",
            title="Chutes de la Lobé",
            text="Lieu: Chutes de la Lobé\nVille: Kribi\nRégion: Sud\nFR: Cascades qui se jettent dans l'océan.",
            source="supabase/places",
            city="Kribi",
            region="Sud",
            category="Cascade",
            tags=("kribi", "lobe"),
        ),
        KnowledgeChunk(
            id="place:2",
            title="Musée National",
            text="Lieu: Musée National\nVille: Yaoundé\nRégion: Centre",
            source="supabase/places",
            city="Yaoundé",
            region="Centre",
            category="Musée",
        ),
    ]
    rag = LocalRAGService(chunks=chunks)
    hits = await rag.retrieve_chunks("Que voir à Kribi ?", top_k=2)
    assert hits
    assert "Kribi" in hits[0].city or "Lobé" in hits[0].title
