/**
 * Progressive-enhancement haptics for SmartMboa.
 * Never throws — Vibration API is optional (blocked on many browsers / iOS).
 *
 * Typing feel: call `typeHaptic()` on each character.
 * Note: Chrome Android usually allows vibrate without gesture after HTTPS load;
 * some browsers require a prior tap — we also call unlock on first pointer.
 */

export type HapticType = 'light' | 'medium' | 'strong' | 'soft' | 'success';

const PATTERNS: Record<HapticType, number | number[]> = {
  light: 12,
  soft: 8,
  medium: 28,
  strong: [40, 30, 50],
  success: [18, 40, 18, 40, 30],
};

let unlocked = false;

function canVibrate(): boolean {
  return typeof navigator !== 'undefined' && 'vibrate' in navigator;
}

/** Call once on first user touch so later auto-vibrations are more reliable. */
export function unlockHaptics(): void {
  unlocked = true;
  if (!canVibrate()) return;
  try {
    navigator.vibrate(1);
  } catch {
    /* ignore */
  }
}

export function triggerHaptic(type: HapticType = 'light'): void {
  if (!canVibrate()) return;
  try {
    navigator.vibrate(PATTERNS[type] ?? 12);
  } catch {
    /* ignore */
  }
}

/**
 * Soft key-click vibration while text is typing.
 * Skip spaces/punctuation so it feels like writing, not a buzz storm.
 */
export function typeHaptic(char: string): void {
  if (!canVibrate()) return;
  if (!char || /\s|[.…,;:!?«»"'’-]/.test(char)) return;
  try {
    // 5–8ms is perceptible as a soft tick on most Android devices
    navigator.vibrate(unlocked ? 6 : 5);
  } catch {
    /* ignore */
  }
}

/** Named pulses used by the cinematic intro (scene changes / CTA). */
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
      tap: 18,
      soft: 14,
      flow: [14, 50, 14],
      micro: 8,
      unify: 34,
      fade: 12,
      final: 16,
      cta: 30,
    };
    navigator.vibrate(map[kind]);
  } catch {
    /* ignore */
  }
}
