from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TouristSiteRecord:
    """Firestore document shape for tourist sites / monuments."""

    id: str
    name: str
    city: str
    region: str = ""
    category: str = "site"
    summary_fr: str = ""
    summary_en: str = ""
    tips_fr: str = ""
    tips_en: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = "local-seed"
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc).isoformat()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TouristSiteRecord:
        tags = data.get("tags") or []
        return cls(
            id=str(data.get("id") or "").strip(),
            name=str(data.get("name") or "").strip(),
            city=str(data.get("city") or "").strip(),
            region=str(data.get("region") or "").strip(),
            category=str(data.get("category") or "site").strip(),
            summary_fr=str(data.get("summary_fr") or "").strip(),
            summary_en=str(data.get("summary_en") or "").strip(),
            tips_fr=str(data.get("tips_fr") or "").strip(),
            tips_en=str(data.get("tips_en") or "").strip(),
            tags=[str(tag).strip() for tag in tags if str(tag).strip()],
            source=str(data.get("source") or "local-seed").strip(),
            updated_at=str(data.get("updated_at") or "").strip(),
        )

    def to_firestore(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


@dataclass
class KnowledgeDocumentRecord:
    """Firestore document shape for Markdown knowledge guides."""

    id: str
    title: str
    body: str
    tags: list[str] = field(default_factory=list)
    source: str = "local-seed"
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc).isoformat()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeDocumentRecord:
        tags = data.get("tags") or []
        return cls(
            id=str(data.get("id") or "").strip(),
            title=str(data.get("title") or "").strip(),
            body=str(data.get("body") or "").strip(),
            tags=[str(tag).strip() for tag in tags if str(tag).strip()],
            source=str(data.get("source") or "local-seed").strip(),
            updated_at=str(data.get("updated_at") or "").strip(),
        )

    def to_firestore(self) -> dict[str, Any]:
        return asdict(self)


SITES_COLLECTION = "tourist_sites"
DOCUMENTS_COLLECTION = "knowledge_documents"
