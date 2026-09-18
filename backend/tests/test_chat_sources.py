from app.schemas.chat import ChatSource
from app.services.ai.context import sources_from_knowledge
from app.services.rag.chunk import KnowledgeChunk


def test_sources_from_knowledge_includes_images() -> None:
    chunks = [
        KnowledgeChunk(
            id="place:abc",
            title="Musée National",
            text="Musée à Yaoundé",
            source="supabase/places",
            city="Yaoundé",
            region="Centre",
            category="Musée",
            images=("https://cdn.example.com/musee.jpg",),
        ),
        KnowledgeChunk(
            id="region:xyz",
            title="Région Centre",
            text="Région",
            source="supabase/regions",
            region="Centre",
        ),
        KnowledgeChunk(
            id="place:abc",
            title="Musée National",
            text="dup",
            source="supabase/places",
            images=("https://cdn.example.com/musee.jpg",),
        ),
    ]
    sources = sources_from_knowledge(chunks)
    assert len(sources) == 1
    assert sources[0] == ChatSource(
        title="Musée National",
        city="Yaoundé",
        region="Centre",
        category="Musée",
        organization="supabase/places",
        url=None,
        image_url="https://cdn.example.com/musee.jpg",
    )
