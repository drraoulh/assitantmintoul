/**
 * Progressive-enhancement haptics for SmartMboa.
 *
 * How unlock works (Android / browsers that implement Vibration API):
 * - Autoplay policies sometimes block `navigator.vibrate` until a user gesture.
 * - ANY `touchstart` / `click` / `pointerdown` anywhere counts as that gesture.
 * - We attach one-shot listeners on window — no special button required.
 *
 * iOS Safari: `navigator.vibrate` is NOT implemented. A gesture cannot create
 * an API that does not exist — haptics stay a silent no-op on iPhone.
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
let unlockBound = false;

function canVibrate(): boolean {
  return typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function';
}

function vibrateSafe(pattern: number | number[]): void {
  if (!canVibrate()) return;
  try {
    navigator.vibrate(pattern);
  } catch {
    /* ignore */
  }
}

/** Mark gesture unlock + fire a tiny pulse so the session is armed. */
export function unlockHaptics(): void {
  unlocked = true;
  vibrateSafe(1);
}

export function isHapticsUnlocked(): boolean {
  return unlocked;
}

/**
 * Listen once for any user gesture anywhere on the page.
 * Call this when the intro mounts — first tap/click unlocks vibrate for typing.
 * Returns a cleanup function.
 */
export function bindHapticsGestureUnlock(): () => void {
  if (typeof window === 'undefined') return () => undefined;
  if (unlockBound || unlocked) return () => undefined;
  unlockBound = true;

  const onGesture = () => {
    unlockHaptics();
    remove();
  };

  const opts: AddEventListenerOptions = { capture: true, passive: true };
  const events = ['touchstart', 'pointerdown', 'click'] as const;

  const remove = () => {
    for (const ev of events) {
      window.removeEventListener(ev, onGesture, opts);
    }
  };

  for (const ev of events) {
    window.addEventListener(ev, onGesture, opts);
  }

  return remove;
}

export function triggerHaptic(type: HapticType = 'light'): void {
  vibrateSafe(PATTERNS[type] ?? 12);
}

/**
 * Soft key-click vibration while text is typing.
 * Skip spaces/punctuation so it feels like writing, not a buzz storm.
 * Works best after `bindHapticsGestureUnlock` + one user tap.
 */
export function typeHaptic(char: string): void {
  if (!char || /\s|[.…,;:!?«»"'’-]/.test(char)) return;
  // Prefer unlocked path; still attempt if API exists (some Android allow it).
  vibrateSafe(unlocked ? 7 : 5);
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
  vibrateSafe(map[kind]);
}
