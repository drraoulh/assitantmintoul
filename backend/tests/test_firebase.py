from __future__ import annotations

import pytest

from app.services.firebase.base import PlaceholderFirebaseStore
from app.services.firebase.schema import KnowledgeDocumentRecord, TouristSiteRecord
from app.services.firebase.seed import (
    load_local_document_records,
    load_local_site_records,
    seed_firebase_from_local,
)


def test_tourist_site_record_roundtrip() -> None:
    site = TouristSiteRecord.from_dict(
        {
            "id": "yaounde-monument-reunification",
            "name": "Monument de la Réunification",
            "city": "Yaoundé",
            "region": "Centre",
            "category": "monument",
            "summary_fr": "Symbole national",
            "tags": ["yaoundé", "monument"],
        }
    )
    payload = site.to_firestore()
    assert payload["id"] == "yaounde-monument-reunification"
    assert payload["category"] == "monument"
    assert "monument" in payload["tags"]


def test_local_seed_includes_monuments() -> None:
    sites = load_local_site_records()
    assert len(sites) >= 70
    categories = {site.category for site in sites}
    assert "monument" in categories or any(
        "monument" in site.id or site.category in {"monument", "museum", "heritage"}
        for site in sites
    )
    names = " ".join(site.name.lower() for site in sites)
    assert "réunification" in names or "reunification" in names or "basilique" in names


def test_local_documents_include_monuments_guide() -> None:
    docs = load_local_document_records()
    ids = {doc.id for doc in docs}
    assert "monuments_heritage_guide" in ids
    assert "firebase_data_model" in ids


@pytest.mark.asyncio
async def test_seed_firebase_uses_in_memory_store() -> None:
    class MemoryStore(PlaceholderFirebaseStore):
        def __init__(self) -> None:
            self.sites: dict[str, TouristSiteRecord] = {}
            self.docs: dict[str, KnowledgeDocumentRecord] = {}

        async def upsert_site(self, site: TouristSiteRecord) -> None:
            self.sites[site.id] = site

        async def list_sites(self) -> list[TouristSiteRecord]:
            return list(self.sites.values())

        async def upsert_document(self, document: KnowledgeDocumentRecord) -> None:
            self.docs[document.id] = document

        async def list_documents(self) -> list[KnowledgeDocumentRecord]:
            return list(self.docs.values())

    store = MemoryStore()
    summary = await seed_firebase_from_local(store)
    assert summary["sites"] >= 70
    assert summary["documents"] >= 10
    assert len(store.sites) == summary["sites"]
    assert any("monument" in site.category or "basilique" in site.name.lower() for site in store.sites.values())
