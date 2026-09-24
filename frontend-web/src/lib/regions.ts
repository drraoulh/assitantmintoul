/**
 * 10 official regions — capitals from cameroon_admin.json (verified admin data).
 * Coordinates for region map pins come only from capital city sites when loaded
 * from the API; this file does not invent lat/lon.
 */
export interface RegionMeta {
  id: string;
  nameFr: string;
  nameEn: string;
  capitalFr: string;
  capitalEn: string;
  /** Region query string accepted by /api/tourist-sites?region= */
  apiRegion: string;
}

export const REGIONS: RegionMeta[] = [
  { id: 'centre', nameFr: 'Centre', nameEn: 'Centre', capitalFr: 'Yaoundé', capitalEn: 'Yaoundé', apiRegion: 'Centre' },
  { id: 'littoral', nameFr: 'Littoral', nameEn: 'Littoral', capitalFr: 'Douala', capitalEn: 'Douala', apiRegion: 'Littoral' },
  { id: 'ouest', nameFr: 'Ouest', nameEn: 'West', capitalFr: 'Bafoussam', capitalEn: 'Bafoussam', apiRegion: 'Ouest' },
  { id: 'nord-ouest', nameFr: 'Nord-Ouest', nameEn: 'North-West', capitalFr: 'Bamenda', capitalEn: 'Bamenda', apiRegion: 'Nord-Ouest' },
  { id: 'sud-ouest', nameFr: 'Sud-Ouest', nameEn: 'South-West', capitalFr: 'Buea', capitalEn: 'Buea', apiRegion: 'Sud-Ouest' },
  { id: 'nord', nameFr: 'Nord', nameEn: 'North', capitalFr: 'Garoua', capitalEn: 'Garoua', apiRegion: 'Nord' },
  { id: 'extreme-nord', nameFr: 'Extrême-Nord', nameEn: 'Far North', capitalFr: 'Maroua', capitalEn: 'Maroua', apiRegion: 'Extrême-Nord' },
  { id: 'adamaoua', nameFr: 'Adamaoua', nameEn: 'Adamawa', capitalFr: 'Ngaoundéré', capitalEn: 'Ngaoundéré', apiRegion: 'Adamaoua' },
  { id: 'est', nameFr: 'Est', nameEn: 'East', capitalFr: 'Bertoua', capitalEn: 'Bertoua', apiRegion: 'Est' },
  { id: 'sud', nameFr: 'Sud', nameEn: 'South', capitalFr: 'Ebolowa', capitalEn: 'Ebolowa', apiRegion: 'Sud' },
];

export function regionByApiName(region: string): RegionMeta | undefined {
  const n = region.trim().toLowerCase();
  return REGIONS.find(
    (r) =>
      r.apiRegion.toLowerCase() === n ||
      r.nameFr.toLowerCase() === n ||
      r.nameEn.toLowerCase() === n ||
      r.id === n,
  );
}
