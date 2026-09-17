from datetime import datetime

from pydantic import BaseModel, Field


class SourceRecord(BaseModel):
    title: str
    organization: str | None = None
    url: str | None = None
    publication_date: str | None = None
    verification_status: str = "official"


class TouristSiteRecord(BaseModel):
    id: str
    name: str
    slug: str
    region: str
    city: str
    category: str
    description: str
    history: str | None = None
    culture: str | None = None
    activities: list[str] = Field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None
    opening_hours: str | None = None
    price: str | None = None
    languages: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    sources: list[SourceRecord] = Field(default_factory=list)


class TouristSiteListResponse(BaseModel):
    items: list[TouristSiteRecord]
    count: int


class NearbyQuery(BaseModel):
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float = 50
