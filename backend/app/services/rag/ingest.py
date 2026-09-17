from pathlib import Path
import json

from app.schemas.tourism import TouristSiteRecord


def catalog_root(configured_path: str) -> Path:
    path = Path(configured_path)
    if path.is_absolute() and path.exists():
        return path
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data" / "tourist_sites"
        if candidate.exists():
            return candidate
    return Path.cwd() / configured_path


def load_tourist_sites(configured_path: str) -> list[TouristSiteRecord]:
    root = catalog_root(configured_path)
    sites: list[TouristSiteRecord] = []
    for json_file in sorted(root.glob("*/*.json")):
        payload = json.loads(json_file.read_text(encoding="utf-8"))
        records = payload if isinstance(payload, list) else payload.get("sites", [])
        for item in records:
            sites.append(TouristSiteRecord.model_validate(item))
    return sites


def chunk_site(site: TouristSiteRecord) -> list[dict]:
    """Split a site into retrieval chunks. One section = one chunk."""
    sections = [
        ("description", site.description),
        ("history", site.history),
        ("culture", site.culture),
        ("visit", _visit_blurb(site)),
    ]
    chunks: list[dict] = []
    for kind, body in sections:
        if not body or not str(body).strip():
            continue
        text = (
            f"{site.name} ({site.city}, {site.region}, Cameroon). "
            f"Category: {site.category}. {body.strip()}"
        )
        chunks.append(
            {
                "chunk_id": f"{site.id}:{kind}",
                "site_id": site.id,
                "site_name": site.name,
                "slug": site.slug,
                "region": site.region,
                "city": site.city,
                "category": site.category,
                "kind": kind,
                "text": text,
                "sources": [source.model_dump() for source in site.sources],
            }
        )
    return chunks


def _visit_blurb(site: TouristSiteRecord) -> str:
    activities = ", ".join(site.activities) if site.activities else "not listed"
    hours = site.opening_hours or "not available in this knowledge base"
    price = site.price or "not available in this knowledge base"
    return (
        f"Typical visitor activities recorded here: {activities}. "
        f"Opening hours: {hours}. Price: {price}. "
        "Unlisted practical details must not be invented."
    )
