"""Geographical helpers for Agent 3 (great-circle distance only)."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from app.services.agents.knowledge.models import PlaceEvidence


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Great-circle distance in km — not driving distance."""
    radius = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return 2 * radius * asin(sqrt(a))


def place_distance_km(a: PlaceEvidence, b: PlaceEvidence) -> float | None:
    if (
        a.latitude is None
        or a.longitude is None
        or b.latitude is None
        or b.longitude is None
    ):
        return None
    return round(haversine_km(a.latitude, a.longitude, b.latitude, b.longitude), 3)


def order_by_nearest(
    places: list[PlaceEvidence],
) -> list[PlaceEvidence]:
    """Nearest-neighbor tour within a day. Falls back to input order if no coords."""
    if len(places) <= 1:
        return list(places)
    with_coords = [p for p in places if p.latitude is not None and p.longitude is not None]
    if len(with_coords) < 2:
        return list(places)

    remaining = list(places)
    # Start with first place that has coords, else first place.
    start = next(
        (p for p in remaining if p.latitude is not None and p.longitude is not None),
        remaining[0],
    )
    ordered = [start]
    remaining.remove(start)

    while remaining:
        current = ordered[-1]
        best_i = 0
        best_d: float | None = None
        for i, candidate in enumerate(remaining):
            dist = place_distance_km(current, candidate)
            if dist is None:
                continue
            if best_d is None or dist < best_d:
                best_d = dist
                best_i = i
        if best_d is None:
            ordered.extend(remaining)
            break
        ordered.append(remaining.pop(best_i))
    return ordered
