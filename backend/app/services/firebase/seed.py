from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from app.services.firebase.base import FirebaseKnowledgeStore
from app.services.firebase.schema import KnowledgeDocumentRecord, TouristSiteRecord
from app.services.rag.loader import default_data_root

logger = logging.getLogger(__name__)

_HEADING = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def load_local_site_records(data_root: Path | None = None) -> list[TouristSiteRecord]:
    root = (data_root or default_data_root()) / "tourist_sites"
    records: list[TouristSiteRecord] = []
    if not root.is_dir():
        return records
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skip %s: %s", path, exc)
            continue
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            record = TouristSiteRecord.from_dict({**item, "source": "local-seed"})
            if record.id and record.name:
                records.append(record)
    return records


def load_local_document_records(
    data_root: Path | None = None,
) -> list[KnowledgeDocumentRecord]:
    root = (data_root or default_data_root()) / "documents"
    records: list[KnowledgeDocumentRecord] = []
    if not root.is_dir():
        return records
    for path in sorted(root.glob("*.md")):
        try:
            body = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            logger.warning("Skip %s: %s", path, exc)
            continue
        if not body:
            continue
        match = _HEADING.search(body)
        title = match.group(1).strip() if match else path.stem.replace("_", " ").title()
        records.append(
            KnowledgeDocumentRecord(
                id=path.stem,
                title=title,
                body=body,
                tags=[path.stem],
                source="local-seed",
            )
        )
    return records


async def seed_firebase_from_local(
    store: FirebaseKnowledgeStore,
    *,
    data_root: Path | None = None,
) -> dict[str, int]:
    """Upload local data/ JSON + Markdown into Firebase collections."""
    sites = load_local_site_records(data_root)
    documents = load_local_document_records(data_root)
    for site in sites:
        await store.upsert_site(site)
    for document in documents:
        await store.upsert_document(document)
    summary = {"sites": len(sites), "documents": len(documents)}
    logger.info("Seeded Firebase knowledge store: %s", summary)
    return summary
