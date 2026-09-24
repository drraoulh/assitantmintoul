/**
 * Intro storage + phase model.
 * Pace is driven by typewriter completion (not a rushed fixed clock).
 */

export const INTRO_STORAGE_KEY = 'smartmboa_intro_seen';

export type IntroPhase =
  | 'INTRO'
  | 'REGION_NORTH'
  | 'REGION_WEST'
  | 'REGION_CENTER'
  | 'REGION_COAST'
  | 'CULTURES'
  | 'UNIFICATION'
  | 'AFRICA_MINIATURE'
  | 'CAMEROON'
  | 'BRAND'
  | 'READY'
  | 'EXITING'
  | 'DONE';

/** Ordered scenes that auto-advance after typing + hold. */
export const AUTO_PHASES: IntroPhase[] = [
  'INTRO',
  'REGION_NORTH',
  'REGION_WEST',
  'REGION_CENTER',
  'REGION_COAST',
  'CULTURES',
  'UNIFICATION',
  'AFRICA_MINIATURE',
  'CAMEROON',
  'BRAND',
  'READY',
];

/** Hold after a scene finishes typing (ms). */
export function holdAfter(phase: IntroPhase): number {
  switch (phase) {
    case 'INTRO':
      return 900;
    case 'CAMEROON':
      return 2200;
    case 'UNIFICATION':
      return 2000;
    case 'AFRICA_MINIATURE':
      return 1800;
    case 'BRAND':
      return 600;
    default:
      return 1600;
  }
}

export function markIntroSeen(): void {
  try {
    localStorage.setItem(INTRO_STORAGE_KEY, 'true');
  } catch {
    /* private mode / unavailable */
  }
}

export function clearIntroSeen(): void {
  try {
    localStorage.removeItem(INTRO_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export function hasSeenIntro(): boolean {
  if (typeof window === 'undefined') return true;
  try {
    if (new URLSearchParams(window.location.search).has('reset_intro')) {
      clearIntroSeen();
      return false;
    }
    return localStorage.getItem(INTRO_STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

/** Official Cameroon flag palette + accents used in the intro only. */
export const CM_FLAG = {
  green: '#007A5E',
  red: '#CE1126',
  yellow: '#FCD116',
  deepGreen: '#0B3D2E',
  water: '#2C8FB3',
  ivory: '#F8F5ED',
  sand: '#C4A574',
} as const;

/** Cultural area → region ids already in cameroon-points.json */
export const CULTURAL_ZONES = {
  'SOUDANO-SAHELIENNE': ['extreme-nord', 'nord', 'adamaoua'],
  GRASSFIELDS: ['ouest', 'nord-ouest'],
  'FANG-BETI': ['centre', 'sud', 'est'],
  SAWA: ['littoral', 'sud-ouest'],
} as const;

/** Zone colors — flag green / red / yellow + water for Sawa */
export const ZONE_COLORS: Record<keyof typeof CULTURAL_ZONES, string> = {
  'SOUDANO-SAHELIENNE': CM_FLAG.yellow,
  GRASSFIELDS: CM_FLAG.red,
  'FANG-BETI': CM_FLAG.green,
  SAWA: CM_FLAG.water,
};
