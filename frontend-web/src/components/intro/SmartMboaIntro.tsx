'use client';

import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { CameroonMapIntro } from '@/components/intro/CameroonMapIntro';
import { IntroControls } from '@/components/intro/IntroControls';
import { IntroSound } from '@/components/intro/IntroSound';
import { IntroText, ReducedIntroCopy } from '@/components/intro/IntroText';
import { introHaptic, triggerHaptic } from '@/lib/haptics';
import {
  hasSeenIntro,
  INTRO_DURATION_MS,
  INTRO_TIMELINE,
  markIntroSeen,
  phaseAt,
  type IntroPhase,
} from '@/lib/intro';

export { INTRO_STORAGE_KEY, hasSeenIntro } from '@/lib/intro';

const EASE = [0.22, 1, 0.36, 1] as const;

type IntroHapticKind =
  | 'breath'
  | 'tap'
  | 'soft'
  | 'flow'
  | 'micro'
  | 'unify'
  | 'fade'
  | 'final'
  | 'cta';

function soundCueFor(phase: IntroPhase): Parameters<IntroSound['play']>[0] | null {
  switch (phase) {
    case 'INTRO':
      return 'heartbeat';
    case 'REGION_NORTH':
    case 'REGION_WEST':
      return 'wind';
    case 'REGION_CENTER':
      return 'forest';
    case 'REGION_COAST':
      return 'water';
    case 'CAMEROON':
      return 'silence';
    default:
      return null;
  }
}

export function SmartMboaIntro({ onComplete }: { onComplete: () => void }) {
  const reduceMotion = useReducedMotion();
  const reduce = !!reduceMotion;

  const [phase, setPhase] = useState<IntroPhase>('INTRO');
  const [visible, setVisible] = useState(true);
  const [soundOn, setSoundOn] = useState(false);

  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const soundRef = useRef(new IntroSound());
  const startedRef = useRef(false);
  const finishingRef = useRef(false);
  const rafRef = useRef<number | undefined>(undefined);
  const phaseRef = useRef<IntroPhase>('INTRO');
  const firedHaptics = useRef(new Set<string>());
  const lastSoundPhase = useRef<IntroPhase | null>(null);

  const exitToHome = useCallback((immediate = false) => {
    if (finishingRef.current) return;
    finishingRef.current = true;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    soundRef.current.stop();
    markIntroSeen();
    setPhase('EXITING');

    const ms = immediate || reduce ? 320 : 900;
    window.setTimeout(() => {
      setPhase('DONE');
      setVisible(false);
      onCompleteRef.current();
    }, ms);
  }, [reduce]);

  const skip = useCallback(() => {
    triggerHaptic('medium');
    soundRef.current.unlock();
    exitToHome(true);
  }, [exitToHome]);

  const startCta = useCallback(() => {
    introHaptic('cta');
    soundRef.current.unlock();
    exitToHome(false);
  }, [exitToHome]);

  const toggleSound = useCallback(() => {
    soundRef.current.unlock();
    setSoundOn((prev) => {
      const next = !prev;
      soundRef.current.setEnabled(next);
      if (next) {
        const cue = soundCueFor(phaseRef.current);
        if (cue) void soundRef.current.play(cue);
      } else {
        soundRef.current.stop();
      }
      return next;
    });
  }, []);

  // Boot once
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    if (hasSeenIntro()) {
      setPhase('EXITING');
      const t = window.setTimeout(() => {
        setVisible(false);
        onCompleteRef.current();
      }, reduce ? 120 : 480);
      return () => clearTimeout(t);
    }

    if (reduce) {
      // Static reduced-motion path — wait for CTA
      setPhase('READY');
      introHaptic('breath');
      return;
    }

    const t0 = performance.now();
    firedHaptics.current.add('INTRO');
    introHaptic('breath');

    const tick = (now: number) => {
      if (finishingRef.current) return;
      const elapsed = now - t0;
      const next = phaseAt(Math.min(elapsed, INTRO_DURATION_MS + 50));

      if (next !== phaseRef.current) {
        phaseRef.current = next;
        setPhase(next);

        const step = INTRO_TIMELINE.find((s) => s.phase === next);
        if (step?.haptic && !firedHaptics.current.has(next)) {
          firedHaptics.current.add(next);
          introHaptic((step.haptic as IntroHapticKind) || 'tap');
          if (next === 'CULTURES') {
            window.setTimeout(() => introHaptic('micro'), 420);
            window.setTimeout(() => introHaptic('micro'), 820);
          }
        }

        const cue = soundCueFor(next);
        if (cue && lastSoundPhase.current !== next) {
          lastSoundPhase.current = next;
          void soundRef.current.play(cue);
        }
      }

      if (elapsed < INTRO_DURATION_MS + 80 && !finishingRef.current) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };

    rafRef.current = requestAnimationFrame(tick);
    const sound = soundRef.current;

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      sound.stop();
    };
  }, [reduce]);

  if (!visible) return null;

  const showCta = phase === 'BRAND' || phase === 'READY' || reduce;

  return (
    <AnimatePresence>
      {visible ? (
        <motion.div
          className="fixed inset-0 z-[100] flex min-h-[100svh] flex-col overflow-hidden bg-[#050505]"
          initial={{ opacity: 1 }}
          animate={
            phase === 'EXITING'
              ? { opacity: 0, scale: 1.06, filter: 'blur(12px)' }
              : { opacity: 1, scale: 1, filter: 'blur(0px)' }
          }
          exit={{ opacity: 0 }}
          transition={{ duration: reduce ? 0.25 : 0.9, ease: EASE }}
          role="dialog"
          aria-label="Introduction SmartMboa — Cameroun"
          onPointerDown={() => soundRef.current.unlock()}
        >
          {/* Cinematic vignette */}
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                'radial-gradient(ellipse 70% 60% at 50% 42%, rgba(11,61,46,0.45) 0%, rgba(5,5,5,0.92) 70%, #050505 100%)',
            }}
          />

          <IntroControls
            soundEnabled={soundOn}
            onToggleSound={toggleSound}
            onSkip={skip}
            showSound={!reduce}
          />

          <div className="relative z-10 flex flex-1 flex-col items-center justify-center px-4 pb-16 pt-16">
            {reduce ? (
              <ReducedIntroCopy />
            ) : (
              <>
                <CameroonMapIntro phase={phase} reduce={false} />
                <IntroText phase={phase} reduce={false} />
              </>
            )}

            {showCta ? (
              <motion.button
                type="button"
                onClick={startCta}
                className="mt-10 inline-flex items-center gap-2 rounded-2xl bg-[#0B3D2E] px-7 py-3.5 text-base font-semibold text-[#F8F5ED] shadow-[0_12px_40px_rgba(0,0,0,0.35)] ring-1 ring-[#D4AF37]/55"
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                whileHover={reduce ? undefined : { scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                transition={{ duration: 0.5, ease: EASE }}
                aria-label="Commencer l'exploration"
              >
                COMMENCER L&apos;EXPLORATION
                <ArrowRight className="h-5 w-5 text-[#D4AF37]" aria-hidden />
              </motion.button>
            ) : null}
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

/** Back-compat alias used by Home. */
export function ImmersiveWelcome({ onComplete }: { onComplete: () => void }) {
  return <SmartMboaIntro onComplete={onComplete} />;
}
