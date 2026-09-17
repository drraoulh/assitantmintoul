from collections.abc import Sequence

from app.schemas.chat import ChatSource
from app.services.rag.types import RetrievedChunk


def sources_from_chunks(chunks: Sequence[RetrievedChunk] | None) -> list[ChatSource]:
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
