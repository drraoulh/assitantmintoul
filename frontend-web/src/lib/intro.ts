/**
 * Intro storage + deterministic timeline (no chaotic setTimeout chains).
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

/** Storyboard checkpoints in ms from t=0 (~14s cinematic, then brand). */
export const INTRO_TIMELINE: { at: number; phase: IntroPhase; haptic?: string }[] = [
  { at: 0, phase: 'INTRO', haptic: 'breath' },
  { at: 1500, phase: 'REGION_NORTH', haptic: 'tap' },
  { at: 3000, phase: 'REGION_WEST', haptic: 'tap' },
  { at: 4500, phase: 'REGION_CENTER', haptic: 'soft' },
  { at: 6000, phase: 'REGION_COAST', haptic: 'flow' },
  { at: 7500, phase: 'CULTURES', haptic: 'micro' },
  { at: 9300, phase: 'UNIFICATION', haptic: 'unify' },
  { at: 10800, phase: 'AFRICA_MINIATURE', haptic: 'fade' },
  { at: 12300, phase: 'CAMEROON', haptic: 'final' },
  { at: 13800, phase: 'BRAND' },
  { at: 15200, phase: 'READY' },
];

export const INTRO_DURATION_MS = 15200;

export function phaseAt(elapsedMs: number): IntroPhase {
  let current: IntroPhase = 'INTRO';
  for (const step of INTRO_TIMELINE) {
    if (elapsedMs >= step.at) current = step.phase;
    else break;
  }
  return current;
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

/** Cultural area → region ids already in cameroon-points.json */
export const CULTURAL_ZONES = {
  'SOUDANO-SAHELIENNE': ['extreme-nord', 'nord', 'adamaoua'],
  GRASSFIELDS: ['ouest', 'nord-ouest'],
  'FANG-BETI': ['centre', 'sud', 'est'],
  SAWA: ['littoral', 'sud-ouest'],
} as const;

export const ZONE_COLORS: Record<keyof typeof CULTURAL_ZONES, string> = {
  'SOUDANO-SAHELIENNE': '#C4A574',
  GRASSFIELDS: '#D4AF37',
  'FANG-BETI': '#0B3D2E',
  SAWA: '#2C8FB3',
};
