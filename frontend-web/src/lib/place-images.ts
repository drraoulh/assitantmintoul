/**
 * Local cover images for verified places.
 * - /public/places/* : Wikimedia Commons (see ATTRIBUTION.json)
 * - /public/data/place_images_by_slug.json : Ayila'a verified export
 *
 * Never invents URLs. Only returns paths present in these indexes.
 */

import placeSlugImages from '../../public/data/place_images_by_slug.json';

/** Site id → local Wikimedia cover (downloaded under /public/places). */
export const LOCAL_PLACE_COVERS: Record<string, string> = {
  'parc-dja': '/places/parc-dja.jpg',
  'parc-waza': '/places/parc-waza.jpg',
  'chutes-de-la-lobe': '/places/chutes-de-la-lobe.jpg',
  'mont-cameroun': '/places/mont-cameroun.jpg',
  rhumsiki: '/places/rhumsiki.jpg',
  'parc-korup': '/places/parc-korup.jpg',
  'parc-national-korup': '/places/parc-korup.jpg',
  'kribi-plages': '/places/kribi-plages.jpg',
  'palais-royal-foumban': '/places/palais-royal-foumban.jpg',
  'chefferie-bandjoun': '/places/chefferie-bandjoun.jpg',
  'monument-reunification-yaounde': '/places/monument-reunification-yaounde.jpg',
  'down-beach-limbe': '/places/down-beach-limbe.jpg',
  'parc-national-benoue': '/places/parc-national-benoue.jpg',
  'parc-benoue': '/places/parc-national-benoue.jpg',
  'lac-barombi-mbo': '/places/lac-barombi-mbo.jpg',
  'jardin-botanique-limbe': '/places/jardin-botanique-limbe.jpg',
};

const slugMap = placeSlugImages as Record<string, string>;

function normalizeKey(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

export function resolvePlaceImage(place: {
  id?: string | null;
  slug?: string | null;
  name?: string | null;
  images?: string[] | null;
  image_url?: string | null;
}): string | null {
  if (place.image_url) return place.image_url;
  if (place.images?.[0]) return place.images[0];

  const keys = [place.id, place.slug, place.name ? normalizeKey(place.name) : null].filter(
    Boolean,
  ) as string[];

  for (const key of keys) {
    if (LOCAL_PLACE_COVERS[key]) return LOCAL_PLACE_COVERS[key];
    if (slugMap[key]) return slugMap[key];
  }

  for (const key of keys) {
    for (const [slug, url] of Object.entries(slugMap)) {
      if (slug.includes(key) || key.includes(slug)) return url;
    }
  }

  return null;
}

/**
 * Popular / must-see destinations inspired by Cameroon tourism catalogues
 * (e.g. tourism237 site list). Only IDs that exist in the SmartMboa API.
 */
export const MUST_SEE_IDS = [
  'parc-dja',
  'chutes-de-la-lobe',
  'mont-cameroun',
  'rhumsiki',
  'parc-waza',
  'kribi-plages',
  'palais-royal-foumban',
  'chefferie-bandjoun',
  'down-beach-limbe',
  'monument-reunification-yaounde',
  'parc-korup',
  'lac-barombi-mbo',
] as const;

export type ExperienceKind = 'nature' | 'culture' | 'beach' | 'heritage';

export const EXPERIENCE_FILTERS: {
  id: ExperienceKind | 'all';
  label: string;
  categories: string[];
}[] = [
  { id: 'all', label: 'Toutes', categories: [] },
  { id: 'nature', label: 'Nature & Safari', categories: ['nature', 'park'] },
  { id: 'culture', label: 'Culture', categories: ['culture', 'museum'] },
  { id: 'heritage', label: 'Patrimoine', categories: ['heritage'] },
  { id: 'beach', label: 'Plages', categories: ['beach', 'nature'] },
];
