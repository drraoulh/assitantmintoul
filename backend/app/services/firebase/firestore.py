from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.services.firebase.base import FirebaseKnowledgeStore
from app.services.firebase.schema import (
    DOCUMENTS_COLLECTION,
    SITES_COLLECTION,
    KnowledgeDocumentRecord,
    TouristSiteRecord,
)

logger = logging.getLogger(__name__)


class FirestoreKnowledgeStore(FirebaseKnowledgeStore):
    """Firestore-backed knowledge store using firebase-admin."""

    def __init__(
        self,
        *,
        project_id: str,
        credentials_file: str = "",
        client: Any | None = None,
    ) -> None:
        self._project_id = project_id.strip()
        self._credentials_file = credentials_file.strip()
        self._db = client if client is not None else self._build_client()

    def _build_client(self) -> Any:
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
        except ImportError as exc:  # pragma: no cover - optional dep missing
            raise RuntimeError(
                "firebase-admin is not installed. Run: pip install firebase-admin"
            ) from exc

        if not firebase_admin._apps:
            if self._credentials_file:
                path = Path(self._credentials_file)
                if not path.is_file():
                    raise FileNotFoundError(
                        f"Firebase credentials file not found: {path}"
                    )
                cred = credentials.Certificate(str(path))
                firebase_admin.initialize_app(cred, {"projectId": self._project_id})
            else:
                # Application Default Credentials (GCP / emulator friendly).
                firebase_admin.initialize_app(options={"projectId": self._project_id})
        return firestore.client()

    async def list_sites(self) -> list[TouristSiteRecord]:
        docs = self._db.collection(SITES_COLLECTION).stream()
        sites: list[TouristSiteRecord] = []
        for doc in docs:
            data = doc.to_dict() or {}
            data.setdefault("id", doc.id)
            site = TouristSiteRecord.from_dict(data)
            if site.id and site.name:
                sites.append(site)
        return sites

    async def upsert_site(self, site: TouristSiteRecord) -> None:
        if not site.id:
            raise ValueError("Tourist site id is required")
        self._db.collection(SITES_COLLECTION).document(site.id).set(site.to_firestore())

    async def list_documents(self) -> list[KnowledgeDocumentRecord]:
        docs = self._db.collection(DOCUMENTS_COLLECTION).stream()
        records: list[KnowledgeDocumentRecord] = []
        for doc in docs:
            data = doc.to_dict() or {}
            data.setdefault("id", doc.id)
            record = KnowledgeDocumentRecord.from_dict(data)
            if record.id and record.body:
                records.append(record)
        return records

    async def upsert_document(self, document: KnowledgeDocumentRecord) -> None:
        if not document.id:
            raise ValueError("Document id is required")
        self._db.collection(DOCUMENTS_COLLECTION).document(document.id).set(
            document.to_firestore()
        )
