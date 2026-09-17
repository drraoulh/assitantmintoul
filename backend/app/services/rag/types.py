from dataclasses import dataclass, field


@dataclass
class SourceRef:
    title: str
    organization: str | None = None
    url: str | None = None
    publication_date: str | None = None
    verification_status: str = "official"


@dataclass
class RetrievedChunk:
    site_id: str
    site_name: str
    region: str
    city: str
    text: str
    score: float
    sources: list[SourceRef] = field(default_factory=list)
