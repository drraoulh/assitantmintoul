import type {
  ChatPlace,
  ChatResponse,
  ChatSource,
  MapMarker,
  ResponseKind,
  TouristSite,
} from '../types';

const TYPE_MAP: Record<string, ResponseKind> = {
  PLACE_LIST: 'PLACE_LIST',
  PLACE_SEARCH: 'PLACE_SEARCH',
  PLACE_DETAILS: 'PLACE_DETAILS',
  ITINERARY: 'ITINERARY',
  BUDGET_TRIP: 'BUDGET_TRIP',
  HOTEL: 'HOTEL',
  BOOKING: 'BOOKING',
  VISION: 'VISION',
  SIMPLE_ANSWER: 'SIMPLE_ANSWER',
  SIMPLE_QA: 'SIMPLE_ANSWER',
  TOURISM_INFO: 'SIMPLE_ANSWER',
  NATURE: 'PLACE_LIST',
  CULTURE: 'PLACE_LIST',
};

export function resolveResponseKind(response: ChatResponse): ResponseKind {
  const raw = response.response_type?.trim().toUpperCase();
  if (raw && TYPE_MAP[raw]) return TYPE_MAP[raw];
  return inferResponseKind(response.message, response.sources, response.places);
}

export function inferResponseKind(
  message: string,
  sources: ChatSource[] | undefined,
  places?: ChatPlace[] | null,
): ResponseKind {
  const m = message.toLowerCase();
  if (/réservation|reservation|booking|smb-/i.test(m)) return 'BOOKING';
  if (
    (/hôtel|hotel|hébergement|lodging|ayila/i.test(m) && (sources?.length ?? 0) > 0) ||
    (places?.some((p) => /hotel|hôtel|héberg/i.test(p.category ?? '')) ?? false)
  ) {
    return 'HOTEL';
  }
  if (/jour\s*1|day\s*1|itinéraire|itinerary|programme/i.test(m)) return 'ITINERARY';
  if ((places?.length ?? 0) > 1) return 'PLACE_LIST';
  if ((places?.length ?? 0) === 1) return 'PLACE_DETAILS';
  if ((sources?.length ?? 0) === 1) return 'PLACE_DETAILS';
  if ((sources?.length ?? 0) > 1) return 'PLACE_LIST';
  return 'SIMPLE_ANSWER';
}

export function placesToMarkers(places: ChatPlace[] | null | undefined): MapMarker[] {
  if (!places?.length) return [];
  const markers: MapMarker[] = [];
  for (const p of places) {
    if (
      typeof p.latitude === 'number' &&
      typeof p.longitude === 'number' &&
      Number.isFinite(p.latitude) &&
      Number.isFinite(p.longitude)
    ) {
      markers.push({
        id: p.id,
        name: p.name,
        latitude: p.latitude,
        longitude: p.longitude,
        category: p.category ?? undefined,
      });
    }
  }
  return markers;
}

export function sourcesToMarkers(
  sites: TouristSite[],
  sources: ChatSource[] | undefined,
): MapMarker[] {
  if (!sources?.length) return [];
  const markers: MapMarker[] = [];
  for (const s of sources) {
    const match = sites.find(
      (site) =>
        site.name.toLowerCase() === s.title.toLowerCase() ||
        site.name.toLowerCase().includes(s.title.toLowerCase()) ||
        s.title.toLowerCase().includes(site.name.toLowerCase()),
    );
    if (
      match &&
      typeof match.latitude === 'number' &&
      typeof match.longitude === 'number' &&
      Number.isFinite(match.latitude) &&
      Number.isFinite(match.longitude)
    ) {
      markers.push({
        id: match.id,
        name: match.name,
        latitude: match.latitude,
        longitude: match.longitude,
        category: match.category,
      });
    }
  }
  return markers;
}

export function sitesToMarkers(sites: TouristSite[]): MapMarker[] {
  return sites
    .filter(
      (s) =>
        typeof s.latitude === 'number' &&
        typeof s.longitude === 'number' &&
        Number.isFinite(s.latitude) &&
        Number.isFinite(s.longitude),
    )
    .map((s) => ({
      id: s.id,
      name: s.name,
      latitude: s.latitude as number,
      longitude: s.longitude as number,
      category: s.category,
    }));
}

export function isHotelCategory(category: string): boolean {
  return /hotel|hôtel|heberg|lodg|resort|auberge/i.test(category);
}

export function enrichChat(response: ChatResponse) {
  return {
    ...response,
    kind: resolveResponseKind(response),
  };
}

export function chatMarkersFromResponse(
  response: ChatResponse,
  sitesCache: TouristSite[],
): MapMarker[] {
  const fromMap =
    response.map?.markers
      ?.filter(
        (m) =>
          typeof m.latitude === 'number' &&
          typeof m.longitude === 'number' &&
          Number.isFinite(m.latitude) &&
          Number.isFinite(m.longitude),
      )
      .map((m, i) => ({
        id: m.id || `map-${i}`,
        name: m.name || 'Lieu',
        latitude: m.latitude,
        longitude: m.longitude,
        category: m.category ?? undefined,
      })) ?? [];
  if (fromMap.length) return fromMap;
  const fromPlaces = placesToMarkers(response.places);
  if (fromPlaces.length) return fromPlaces;
  return sourcesToMarkers(sitesCache, response.sources ?? response.ui_sources ?? undefined);
}
