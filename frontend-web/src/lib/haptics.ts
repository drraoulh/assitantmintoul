/**
 * Progressive-enhancement haptics for SmartMboa.
 * Never throws — Vibration API is optional (blocked on many browsers / iOS).
 */

export type HapticType = 'light' | 'medium' | 'strong' | 'soft' | 'success';

const PATTERNS: Record<HapticType, number | number[]> = {
  light: 12,
  soft: 8,
  medium: 28,
  strong: [40, 30, 50],
  success: [18, 40, 18, 40, 30],
};

function canVibrate(): boolean {
  return typeof navigator !== 'undefined' && 'vibrate' in navigator;
}

export function triggerHaptic(type: HapticType = 'light'): void {
  if (!canVibrate()) return;
  try {
    navigator.vibrate(PATTERNS[type] ?? 12);
  } catch {
    /* ignore */
  }
}

/** Named pulses used by the cinematic intro (storyboard). */
export function introHaptic(
  kind:
    | 'breath'
    | 'tap'
    | 'soft'
    | 'flow'
    | 'micro'
    | 'unify'
    | 'fade'
    | 'final'
    | 'cta',
): void {
  if (!canVibrate()) return;
  try {
    const map: Record<typeof kind, number | number[]> = {
      breath: 10,
      tap: 16,
      soft: 14,
      flow: [12, 40, 12, 40, 18],
      micro: 8,
      unify: 32,
      fade: 10,
      final: 12,
      cta: 28,
    };
    navigator.vibrate(map[kind]);
  } catch {
    /* ignore */
  }
}
