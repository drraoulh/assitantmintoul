from collections.abc import Sequence

from app.schemas.chat import ChatSource
from app.services.rag.chunk import KnowledgeChunk
from app.services.rag.types import RetrievedChunk


def sources_from_knowledge(
    chunks: Sequence[KnowledgeChunk] | None,
) -> list[ChatSource]:
    """Build chat source cards from HybridRAG / KB chunks (incl. place images)."""
    unique: list[ChatSource] = []
    seen: set[str] = set()
    if not chunks:
        return unique
    for chunk in chunks:
        key = (chunk.id or chunk.title).strip().casefold()
        if not key or key in seen:
            continue
        # Skip thin region blurbs — prefer concrete places / topics.
        if chunk.id.startswith("region:"):
            continue
        seen.add(key)
        image_url = next((url for url in chunk.images if url), None)
        unique.append(
            ChatSource(
                title=chunk.title,
                city=chunk.city,
                region=chunk.region,
                category=chunk.category,
                organization=chunk.source or None,
                url=None,
                image_url=image_url,
            )
        )
    return unique


def sources_from_chunks(chunks: Sequence[RetrievedChunk] | None) -> list[ChatSource]:
    """Legacy FAISS RetrievedChunk path."""
    unique: list[ChatSource] = []
    seen: set[tuple[str, str | None]] = set()
    if not chunks:
        return unique
    for chunk in chunks:
        for source in chunk.sources:
            key = (source.title, source.url)
            if key in seen:
                continue
            seen.add(key)
            unique.append(
                ChatSource(
                    title=source.title,
                    organization=source.organization,
                    url=source.url,
                )
            )
    return unique
