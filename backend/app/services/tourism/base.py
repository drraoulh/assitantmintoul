from abc import ABC, abstractmethod
from typing import Any


class TourismService(ABC):
    """Tourist sites, nearby places, and itineraries.

    Planned: Firebase Firestore queries over curated Cameroon data
    (local JSON remains the seed / offline source of truth).
    """

    @abstractmethod
    async def find_sites(self, city: str) -> list[dict[str, Any]]:
        """Return known attractions for a city."""

    @abstractmethod
    async def build_itinerary(self, city: str, hours: int) -> dict[str, Any]:
        """Return a time-boxed visit plan."""


class PlaceholderTourismService(TourismService):
    async def find_sites(self, city: str) -> list[dict[str, Any]]:
        return []

    async def build_itinerary(self, city: str, hours: int) -> dict[str, Any]:
        return {"city": city, "hours": hours, "stops": []}
