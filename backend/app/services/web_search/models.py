"""Provider-neutral web search contract (SmartMboa web-first chat)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

SourceType = str  # "news" | "official" | "blog" | "wiki" | "business" | "unknown"


class WebSearchResult(BaseModel):
    title: str
    url: str
    domain: str
    snippet: str
    source_type: SourceType = "unknown"
    published_at: Optional[str] = None
    raw_score: Optional[float] = None
    provider: str = ""


class ImageSearchResult(BaseModel):
    image_url: str
    thumbnail_url: Optional[str] = None
    page_url: str
    title: str
    source_domain: str
    alt_text: Optional[str] = None
