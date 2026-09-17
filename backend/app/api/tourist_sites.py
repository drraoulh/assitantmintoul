from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_site_catalog
from app.schemas.tourism import TouristSiteListResponse, TouristSiteRecord
from app.services.tourism.catalog import SiteCatalog

router = APIRouter(prefix="/tourist-sites", tags=["tourist-sites"])


@router.get("", response_model=TouristSiteListResponse)
async def list_tourist_sites(
    city: str | None = Query(default=None),
    region: str | None = Query(default=None),
    catalog: SiteCatalog = Depends(get_site_catalog),
) -> TouristSiteListResponse:
    items = catalog.all()
    if city:
        items = catalog.by_city(city)
    if region:
        needle = region.casefold()
        items = [site for site in items if needle in site.region.casefold()]
    return TouristSiteListResponse(items=items, count=len(items))


@router.get("/nearby", response_model=TouristSiteListResponse)
async def nearby_tourist_sites(
    city: str | None = Query(default=None),
    latitude: float | None = Query(default=None),
    longitude: float | None = Query(default=None),
    radius_km: float = Query(default=50, ge=1, le=500),
    catalog: SiteCatalog = Depends(get_site_catalog),
) -> TouristSiteListResponse:
    if not city and (latitude is None or longitude is None):
        raise HTTPException(
            status_code=400,
            detail="Provide city= or latitude and longitude.",
        )
    items = catalog.nearby(
        city=city,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
    )
    return TouristSiteListResponse(items=items, count=len(items))


@router.get("/{site_id}", response_model=TouristSiteRecord)
async def get_tourist_site(
    site_id: str,
    catalog: SiteCatalog = Depends(get_site_catalog),
) -> TouristSiteRecord:
    site = catalog.get(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Tourist site not found.")
    return site
