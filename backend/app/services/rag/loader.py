from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from app.services.rag.chunk import KnowledgeChunk

logger = logging.getLogger(__name__)

_HEADING = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)


def default_data_root() -> Path:
    """Resolve repo `data/` from backend package location."""
    return Path(__file__).resolve().parents[4] / "data"


def load_knowledge_chunks(data_root: Path | None = None) -> list[KnowledgeChunk]:
    root = data_root or default_data_root()
    chunks: list[KnowledgeChunk] = []
    chunks.extend(_load_tourist_sites(root / "tourist_sites"))
    chunks.extend(_load_documents(root / "documents"))
    logger.info("Loaded %s knowledge chunks from %s", len(chunks), root)
    return chunks


def _load_tourist_sites(directory: Path) -> list[KnowledgeChunk]:
    if not directory.is_dir():
        return []

    chunks: list[KnowledgeChunk] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping tourist site file %s: %s", path, exc)
            continue

        if not isinstance(payload, list):
            logger.warning("Expected list in %s", path)
            continue

        for item in payload:
            if not isinstance(item, dict):
                continue
            chunk = _site_to_chunk(item, source=path.name)
            if chunk is not None:
                chunks.append(chunk)
    return chunks


def _site_to_chunk(item: dict, *, source: str) -> KnowledgeChunk | None:
    site_id = str(item.get("id") or "").strip()
    name = str(item.get("name") or "").strip()
    if not site_id or not name:
        return None

    summary_fr = str(item.get("summary_fr") or "").strip()
    summary_en = str(item.get("summary_en") or "").strip()
    tips_fr = str(item.get("tips_fr") or "").strip()
    tips_en = str(item.get("tips_en") or "").strip()
    city = str(item.get("city") or "").strip() or None
    region = str(item.get("region") or "").strip() or None
    category = str(item.get("category") or "").strip() or None
    tags = tuple(str(tag).strip() for tag in item.get("tags") or [] if str(tag).strip())

    lines = [f"Site: {name}"]
    if city:
        lines.append(f"Ville: {city}")
    if region:
        lines.append(f"Région: {region}")
    if category:
        lines.append(f"Catégorie: {category}")
    if summary_fr:
        lines.append(f"FR: {summary_fr}")
    if summary_en:
        lines.append(f"EN: {summary_en}")
    if tips_fr:
        lines.append(f"Conseils FR: {tips_fr}")
    if tips_en:
        lines.append(f"Tips EN: {tips_en}")

    return KnowledgeChunk(
        id=f"site:{site_id}",
        title=name,
        text="\n".join(lines),
        source=f"tourist_sites/{source}",
        city=city,
        region=region,
        category=category,
        tags=tags,
    )


def _load_documents(directory: Path) -> list[KnowledgeChunk]:
    if not directory.is_dir():
        return []

    chunks: list[KnowledgeChunk] = []
    for path in sorted(directory.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            logger.warning("Skipping document %s: %s", path, exc)
            continue
        if not text:
            continue
        chunks.extend(_split_markdown(text, path=path))
    return chunks


def _split_markdown(text: str, *, path: Path) -> list[KnowledgeChunk]:
    """Split on ## / ### headings so retrieval stays focused."""
    matches = list(_HEADING.finditer(text))
    if not matches:
        title = path.stem.replace("_", " ").title()
        return [
            KnowledgeChunk(
                id=f"doc:{path.stem}",
                title=title,
                text=text,
                source=f"documents/{path.name}",
                tags=(path.stem,),
            )
        ]

    chunks: list[KnowledgeChunk] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[start:end].strip()
        title = match.group(1).strip()
        if len(section) < 40:
            continue
        chunks.append(
            KnowledgeChunk(
                id=f"doc:{path.stem}:{index}",
                title=title,
                text=section,
                source=f"documents/{path.name}",
                tags=(path.stem, title.lower()),
            )
        )
    return chunks
