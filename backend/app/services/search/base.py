from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class WebSearchHit:
    title: str
    snippet: str
    url: str = ""
    source: str = "web"
    published_at: str | None = None
    source_type: str | None = None

    def as_text(self) -> str:
        parts = [self.title.strip()]
        if self.snippet.strip():
            parts.append(self.snippet.strip())
        if self.url.strip():
            parts.append(f"URL: {self.url.strip()}")
        if self.source.strip():
            parts.append(f"Source: {self.source.strip()}")
        return "\n".join(parts)


class WebSearchService(ABC):
    """Search the public web for up-to-date tourism context."""

    @abstractmethod
    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchHit]:
        """Return ranked web hits for a traveller query."""


class PlaceholderWebSearchService(WebSearchService):
    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchHit]:
        return []
