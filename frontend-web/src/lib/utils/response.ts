import type {
  ChatResponse,
  ChatResponseType,
  MapMarker,
  MapUI,
  PlaceUI,
  StructuredChatUI,
  TouristSite,
} from '../types';

const KNOWN_TYPES = new Set<string>([
  'SIMPLE_ANSWER',
  'TOURISM_INFORMATION',
  'PLACE_LIST',
  'PLACE_DETAILS',
  'ITINERARY',
  'BUDGET_TRIP',
  'NATURE',
  'CULTURE',
  'FOOD',
  'HOTEL',
  'BOOKING',
  'VISION',
  'CLARIFICATION',
  'INSUFFICIENT_INFORMATION',
  'TRAVEL_ROUTE',
  'IMAGES',
]);

export function normalizeResponseType(
  raw: string | null | undefined,
): ChatResponseType {
  if (!raw) return 'SIMPLE_ANSWER';
  const upper = raw.trim().toUpperCase();
  if (KNOWN_TYPES.has(upper)) return upper;
  // Legacy aliases
  if (upper === 'PLACE_SEARCH') return 'PLACE_LIST';
  if (upper === 'SIMPLE_QA') return 'SIMPLE_ANSWER';
  return upper || 'SIMPLE_ANSWER';
}

export function resolveResponseKind(
  response: Pick<ChatResponse, 'response_type' | 'message' | 'sources' | 'places'>,
): ChatResponseType {
  if (response.response_type) {
    return normalizeResponseType(response.response_type);
  }
  return inferResponseKind(response.message, response.sources, response.places);
}

/** Fallback only when backend omits response_type. */
export function inferResponseKind(
  message: string,
  sources: ChatResponse['sources'],
  places?: PlaceUI[] | null,
): ChatResponseType {
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

export function placesToMarkers(places: PlaceUI[] | null | undefined): MapMarker[] {
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

export function mapUiToMarkers(map: MapUI | null | undefined): MapMarker[] {
  if (!map?.enabled && map?.enabled !== undefined && !map.markers?.length) {
    return [];
  }
  if (!map?.markers?.length) return [];
  return map.markers
    .filter(
      (m) =>
        typeof m.latitude === 'number' &&
        typeof m.longitude === 'number' &&
        Number.isFinite(m.latitude) &&
        Number.isFinite(m.longitude),
    )
    .map((m) => ({
      id: m.place_id,
      name: m.title,
      latitude: m.latitude,
      longitude: m.longitude,
    }));
}

export function sourcesToMarkers(
  sites: TouristSite[],
  sources: ChatResponse['sources'],
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

export function chatMarkersFromResponse(
  response: ChatResponse | StructuredChatUI,
  sitesCache: TouristSite[] = [],
): MapMarker[] {
  const fromMap = mapUiToMarkers(response.map);
  if (fromMap.length) return fromMap;
  const fromPlaces = placesToMarkers(response.places);
  if (fromPlaces.length) return fromPlaces;
  if ('sources' in response) {
    return sourcesToMarkers(sitesCache, response.sources);
  }
  return [];
}

export function structuredFromChatResponse(res: ChatResponse): StructuredChatUI {
  return {
    response_type: resolveResponseKind(res),
    places: res.places ?? [],
    map: res.map ?? null,
    itinerary: res.itinerary ?? null,
    budget: res.budget ?? null,
    hotels: res.hotels ?? [],
    booking: res.booking ?? null,
    vision: res.vision ?? null,
    ui_sources: res.ui_sources ?? [],
    actions: res.actions ?? [],
    images: res.images ?? [],
    routing: res.routing ?? null,
    structured_build_ms: res.structured_build_ms ?? null,
  };
}

export function enrichChat(response: ChatResponse) {
  return {
    ...response,
    kind: resolveResponseKind(response),
  };
}
