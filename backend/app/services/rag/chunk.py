from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KnowledgeChunk:
    """One searchable unit from the local tourism knowledge base."""

    id: str
    title: str
    text: str
    source: str
    city: str | None = None
    region: str | None = None
    category: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def searchable_text(self) -> str:
        parts = [
            self.title,
            self.text,
            self.city or "",
            self.region or "",
            self.category or "",
            " ".join(self.tags),
            self.source,
        ]
        return " ".join(part for part in parts if part)
