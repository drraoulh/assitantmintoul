'use client';

import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { CameroonMapIntro } from '@/components/intro/CameroonMapIntro';
import { IntroControls } from '@/components/intro/IntroControls';
import { IntroText, ReducedIntroCopy } from '@/components/intro/IntroText';
import { introHaptic, triggerHaptic, unlockHaptics } from '@/lib/haptics';
import {
  AUTO_PHASES,
  hasSeenIntro,
  holdAfter,
  markIntroSeen,
  type IntroPhase,
} from '@/lib/intro';

export { INTRO_STORAGE_KEY, hasSeenIntro } from '@/lib/intro';

const EASE = [0.22, 1, 0.36, 1] as const;

const PHASE_HAPTIC: Partial<Record<IntroPhase, Parameters<typeof introHaptic>[0]>> = {
  INTRO: 'breath',
  REGION_NORTH: 'tap',
  REGION_WEST: 'tap',
  REGION_CENTER: 'soft',
  REGION_COAST: 'flow',
  CULTURES: 'micro',
  UNIFICATION: 'unify',
  AFRICA_MINIATURE: 'fade',
  CAMEROON: 'final',
};

export function SmartMboaIntro({ onComplete }: { onComplete: () => void }) {
  const reduceMotion = useReducedMotion();
  const reduce = !!reduceMotion;

  const [phase, setPhase] = useState<IntroPhase>('INTRO');
  const [visible, setVisible] = useState(true);

  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const startedRef = useRef(false);
  const finishingRef = useRef(false);
  const phaseRef = useRef<IntroPhase>('INTRO');
  const holdTimerRef = useRef<number | undefined>(undefined);

  const clearHold = useCallback(() => {
    if (holdTimerRef.current !== undefined) {
      clearTimeout(holdTimerRef.current);
      holdTimerRef.current = undefined;
    }
  }, []);

  const exitToHome = useCallback(
    (immediate = false) => {
      if (finishingRef.current) return;
      finishingRef.current = true;
      clearHold();
      markIntroSeen();
      setPhase('EXITING');

      const ms = immediate || reduce ? 320 : 900;
      window.setTimeout(() => {
        setPhase('DONE');
        setVisible(false);
        onCompleteRef.current();
      }, ms);
    },
    [clearHold, reduce],
  );

  const skip = useCallback(() => {
    unlockHaptics();
    triggerHaptic('medium');
    exitToHome(true);
  }, [exitToHome]);

  const startCta = useCallback(() => {
    unlockHaptics();
    introHaptic('cta');
    exitToHome(false);
  }, [exitToHome]);

  const goNext = useCallback(
    (from: IntroPhase) => {
      if (finishingRef.current) return;
      if (phaseRef.current !== from) return;

      clearHold();
      const idx = AUTO_PHASES.indexOf(from);
      const next = AUTO_PHASES[idx + 1];
      if (!next || next === 'READY') {
        setPhase('READY');
        phaseRef.current = 'READY';
        return;
      }

      const delay = reduce ? 280 : holdAfter(from);
      holdTimerRef.current = window.setTimeout(() => {
        if (finishingRef.current || phaseRef.current !== from) return;
        phaseRef.current = next;
        setPhase(next);
        const haptic = PHASE_HAPTIC[next];
        if (haptic) introHaptic(haptic);
        if (next === 'CULTURES') {
          window.setTimeout(() => introHaptic('micro'), 500);
          window.setTimeout(() => introHaptic('micro'), 950);
        }
      }, delay);
    },
    [clearHold, reduce],
  );

  const onTyped = useCallback(
    (forPhase: IntroPhase) => {
      if (forPhase === 'BRAND') {
        goNext('BRAND');
        return;
      }
      if (forPhase === 'INTRO') return;
      goNext(forPhase);
    },
    [goNext],
  );

  // Boot once — typewriter drives pace after INTRO breath
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
      setPhase('READY');
      phaseRef.current = 'READY';
      return;
    }

    phaseRef.current = 'INTRO';
    setPhase('INTRO');
    introHaptic('breath');

    // After the breathing point, start the typed sequence
    const t = window.setTimeout(() => {
      if (finishingRef.current) return;
      phaseRef.current = 'REGION_NORTH';
      setPhase('REGION_NORTH');
      introHaptic('tap');
    }, 1800);

    return () => {
      clearTimeout(t);
      clearHold();
    };
  }, [clearHold, reduce]);

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
          onPointerDown={() => unlockHaptics()}
        >
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                'radial-gradient(ellipse 70% 60% at 50% 42%, rgba(0,122,94,0.35) 0%, rgba(5,5,5,0.92) 70%, #050505 100%)',
            }}
          />
          {/* Soft flag wash */}
          <div
            className="pointer-events-none absolute inset-x-0 top-0 h-1.5 opacity-80"
            style={{
              background: 'linear-gradient(90deg, #007A5E 0%, #CE1126 50%, #FCD116 100%)',
            }}
            aria-hidden
          />

          <IntroControls onSkip={skip} />

          <div className="relative z-10 flex flex-1 flex-col items-center justify-center px-4 pb-16 pt-16">
            {reduce ? (
              <ReducedIntroCopy />
            ) : (
              <>
                <CameroonMapIntro phase={phase} reduce={false} />
                <IntroText phase={phase} reduce={false} onTyped={onTyped} />
              </>
            )}

            {showCta ? (
              <motion.button
                type="button"
                onClick={startCta}
                className="mt-10 inline-flex items-center gap-2 rounded-2xl bg-[#007A5E] px-7 py-3.5 text-base font-semibold text-[#F8F5ED] shadow-[0_12px_40px_rgba(0,0,0,0.35)] ring-1 ring-[#FCD116]/60"
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                whileHover={reduce ? undefined : { scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                transition={{ duration: 0.5, ease: EASE }}
                aria-label="Commencer l'exploration"
              >
                COMMENCER L&apos;EXPLORATION
                <ArrowRight className="h-5 w-5 text-[#FCD116]" aria-hidden />
              </motion.button>
            ) : null}
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export function ImmersiveWelcome({ onComplete }: { onComplete: () => void }) {
  return <SmartMboaIntro onComplete={onComplete} />;
}
