/**
 * Cameroon destination matching for the Planifier form.
 * Catalog sourced from verified cameroon_admin.json + tourism aliases.
 */

import catalog from './cameroon-destinations.json';

export type CameroonDestination = {
  id: string;
  name: string;
  nameEn: string;
  region: string;
  aliases: string[];
  kind: string;
};

export const CAMEROON_DESTINATIONS = catalog as CameroonDestination[];

export function normalizePlaceQuery(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s'-]/g, ' ')
    .replace(/\s+/g, ' ');
}

function scoreDestination(query: string, dest: CameroonDestination): number {
  const q = normalizePlaceQuery(query);
  if (!q) return 0;
  const names = [
    dest.name,
    dest.nameEn,
    ...dest.aliases,
    dest.region,
  ].map(normalizePlaceQuery);

  let best = 0;
  for (const n of names) {
    if (!n) continue;
    if (n === q) best = Math.max(best, 100);
    else if (n.startsWith(q)) best = Math.max(best, 80 - Math.min(n.length - q.length, 20));
    else if (n.includes(q)) best = Math.max(best, 55);
    else if (q.length >= 3 && n.split(' ').some((w) => w.startsWith(q)))
      best = Math.max(best, 50);
  }
  return best;
}

/** Live suggestions while typing (best matches first). */
export function suggestCameroonDestinations(
  query: string,
  limit = 8,
): CameroonDestination[] {
  const q = normalizePlaceQuery(query);
  if (!q) {
    // Show popular starters when empty / very short
    const popular = [
      'Yaoundé',
      'Douala',
      'Limbé',
      'Kribi',
      'Bafoussam',
      'Bamenda',
      'Maroua',
      'Foumban',
    ];
    return popular
      .map((name) => CAMEROON_DESTINATIONS.find((d) => d.name === name))
      .filter((d): d is CameroonDestination => !!d)
      .slice(0, limit);
  }

  return CAMEROON_DESTINATIONS.map((d) => ({ d, s: scoreDestination(query, d) }))
    .filter((x) => x.s >= 45)
    .sort((a, b) => b.s - a.s || a.d.name.localeCompare(b.d.name, 'fr'))
    .slice(0, limit)
    .map((x) => x.d);
}

/** Exact / strong match for validation. */
export function resolveCameroonDestination(
  query: string,
): CameroonDestination | null {
  const q = normalizePlaceQuery(query);
  if (!q) return null;
  const ranked = CAMEROON_DESTINATIONS.map((d) => ({
    d,
    s: scoreDestination(query, d),
  })).sort((a, b) => b.s - a.s);
  const top = ranked[0];
  if (!top || top.s < 70) return null;
  return top.d;
}

export function isCameroonDestination(query: string): boolean {
  return resolveCameroonDestination(query) != null;
}
