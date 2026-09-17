from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.firebase.schema import KnowledgeDocumentRecord, TouristSiteRecord


class FirebaseKnowledgeStore(ABC):
    """Cloud knowledge store (Firestore) for sites and documents."""

    @abstractmethod
    async def list_sites(self) -> list[TouristSiteRecord]:
        """Return all tourist site documents."""

    @abstractmethod
    async def upsert_site(self, site: TouristSiteRecord) -> None:
        """Create or replace one tourist site."""

    @abstractmethod
    async def list_documents(self) -> list[KnowledgeDocumentRecord]:
        """Return knowledge document records."""

    @abstractmethod
    async def upsert_document(self, document: KnowledgeDocumentRecord) -> None:
        """Create or replace one knowledge document."""


class PlaceholderFirebaseStore(FirebaseKnowledgeStore):
    """No-op store used when Firebase is disabled."""

    async def list_sites(self) -> list[TouristSiteRecord]:
        return []

    async def upsert_site(self, site: TouristSiteRecord) -> None:
        return None

    async def list_documents(self) -> list[KnowledgeDocumentRecord]:
        return []

    async def upsert_document(self, document: KnowledgeDocumentRecord) -> None:
        return None
