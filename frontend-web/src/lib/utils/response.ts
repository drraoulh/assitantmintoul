import type { ChatResponse, ChatSource, MapMarker, ResponseKind, TouristSite } from '../types';

export function inferResponseKind(
  message: string,
  sources: ChatSource[] | undefined,
): ResponseKind {
  const m = message.toLowerCase();
  if (/réservation|reservation|booking|smb-/i.test(m)) return 'BOOKING';
  if (/hôtel|hotel|hébergement|lodging|ayila/i.test(m) && (sources?.length ?? 0) > 0) {
    return 'HOTEL';
  }
  if (/jour\s*1|day\s*1|itinéraire|itinerary|programme/i.test(m)) return 'ITINERARY';
  if ((sources?.length ?? 0) === 1) return 'PLACE_DETAILS';
  if ((sources?.length ?? 0) > 1) return 'PLACE_SEARCH';
  return 'SIMPLE_ANSWER';
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
    kind: inferResponseKind(response.message, response.sources),
  };
}
