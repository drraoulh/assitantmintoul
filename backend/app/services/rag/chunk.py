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
    images: tuple[str, ...] = field(default_factory=tuple)

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

    def to_cache_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "text": self.text,
            "source": self.source,
            "city": self.city,
            "region": self.region,
            "category": self.category,
            "tags": list(self.tags),
            "images": list(self.images),
        }

    @classmethod
    def from_cache_dict(cls, data: dict) -> KnowledgeChunk:
        tags = data.get("tags") or []
        images = data.get("images") or []
        return cls(
            id=str(data.get("id") or ""),
            title=str(data.get("title") or ""),
            text=str(data.get("text") or ""),
            source=str(data.get("source") or ""),
            city=data.get("city"),
            region=data.get("region"),
            category=data.get("category"),
            tags=tuple(str(tag) for tag in tags),
            images=tuple(str(url) for url in images if str(url).strip()),
        )
