/**
 * 10 official regions — capitals from cameroon_admin.json (verified admin data).
 * Coordinates for region map pins come only from capital city sites when loaded
 * from the API; this file does not invent lat/lon.
 *
 * coverImage: curated Wikimedia Commons photos under /public/regions/
 * (see /public/regions/ATTRIBUTION.json for license + source).
 */
export interface RegionMeta {
  id: string;
  nameFr: string;
  nameEn: string;
  capitalFr: string;
  capitalEn: string;
  /** Region query string accepted by /api/tourist-sites?region= */
  apiRegion: string;
  /** Local cover photo representing the region (Wikimedia Commons). */
  coverImage: string;
}

export const REGIONS: RegionMeta[] = [
  {
    id: 'centre',
    nameFr: 'Centre',
    nameEn: 'Centre',
    capitalFr: 'Yaoundé',
    capitalEn: 'Yaoundé',
    apiRegion: 'Centre',
    coverImage: '/regions/centre.jpg',
  },
  {
    id: 'littoral',
    nameFr: 'Littoral',
    nameEn: 'Littoral',
    capitalFr: 'Douala',
    capitalEn: 'Douala',
    apiRegion: 'Littoral',
    coverImage: '/regions/littoral.jpg',
  },
  {
    id: 'ouest',
    nameFr: 'Ouest',
    nameEn: 'West',
    capitalFr: 'Bafoussam',
    capitalEn: 'Bafoussam',
    apiRegion: 'Ouest',
    coverImage: '/regions/ouest.jpg',
  },
  {
    id: 'nord-ouest',
    nameFr: 'Nord-Ouest',
    nameEn: 'North-West',
    capitalFr: 'Bamenda',
    capitalEn: 'Bamenda',
    apiRegion: 'Nord-Ouest',
    coverImage: '/regions/nord-ouest.jpg',
  },
  {
    id: 'sud-ouest',
    nameFr: 'Sud-Ouest',
    nameEn: 'South-West',
    capitalFr: 'Buea',
    capitalEn: 'Buea',
    apiRegion: 'Sud-Ouest',
    coverImage: '/regions/sud-ouest.jpg',
  },
  {
    id: 'nord',
    nameFr: 'Nord',
    nameEn: 'North',
    capitalFr: 'Garoua',
    capitalEn: 'Garoua',
    apiRegion: 'Nord',
    coverImage: '/regions/nord.jpg',
  },
  {
    id: 'extreme-nord',
    nameFr: 'Extrême-Nord',
    nameEn: 'Far North',
    capitalFr: 'Maroua',
    capitalEn: 'Maroua',
    apiRegion: 'Extrême-Nord',
    coverImage: '/regions/extreme-nord.jpg',
  },
  {
    id: 'adamaoua',
    nameFr: 'Adamaoua',
    nameEn: 'Adamawa',
    capitalFr: 'Ngaoundéré',
    capitalEn: 'Ngaoundéré',
    apiRegion: 'Adamaoua',
    coverImage: '/regions/adamaoua.jpg',
  },
  {
    id: 'est',
    nameFr: 'Est',
    nameEn: 'East',
    capitalFr: 'Bertoua',
    capitalEn: 'Bertoua',
    apiRegion: 'Est',
    coverImage: '/regions/est.jpg',
  },
  {
    id: 'sud',
    nameFr: 'Sud',
    nameEn: 'South',
    capitalFr: 'Ebolowa',
    capitalEn: 'Ebolowa',
    apiRegion: 'Sud',
    coverImage: '/regions/sud.jpg',
  },
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
