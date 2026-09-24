'use client';

import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import Image from 'next/image';
import { useCallback, useEffect, useState } from 'react';

import { CameroonSilhouette } from '@/components/maps/CameroonSilhouette';
import { APP_NAME } from '@/lib/config';
import { EASE_OUT } from '@/lib/motion';

export const INTRO_STORAGE_KEY = 'smartmboa_intro_seen';

type Phase =
  | 'boot'
  | 'welcome'
  | 'mountains'
  | 'forests'
  | 'beaches'
  | 'cultures'
  | 'stories'
  | 'miniature'
  | 'brand'
  | 'cta'
  | 'exit'
  | 'done';

const SCENES: { phase: Phase; duration: number }[] = [
  { phase: 'welcome', duration: 1100 },
  { phase: 'mountains', duration: 750 },
  { phase: 'forests', duration: 750 },
  { phase: 'beaches', duration: 750 },
  { phase: 'cultures', duration: 750 },
  { phase: 'stories', duration: 750 },
  { phase: 'miniature', duration: 1200 },
  { phase: 'brand', duration: 1400 },
  { phase: 'cta', duration: 999999 },
];

function markSeen() {
  try {
    localStorage.setItem(INTRO_STORAGE_KEY, 'true');
  } catch {
    /* ignore */
  }
}

export function hasSeenIntro(): boolean {
  if (typeof window === 'undefined') return true;
  try {
    if (new URLSearchParams(window.location.search).has('reset_intro')) {
      localStorage.removeItem(INTRO_STORAGE_KEY);
      return false;
    }
    return localStorage.getItem(INTRO_STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

export function ImmersiveWelcome({
  onComplete,
}: {
  onComplete: () => void;
}) {
  const reduce = useReducedMotion();
  const [phase, setPhase] = useState<Phase>('boot');
  const [visible, setVisible] = useState(true);

  const finish = useCallback(() => {
    markSeen();
    setPhase('exit');
    window.setTimeout(
      () => {
        setVisible(false);
        onComplete();
      },
      reduce ? 200 : 850,
    );
  }, [onComplete, reduce]);

  useEffect(() => {
    if (hasSeenIntro()) {
      // Short returning-visitor transition
      setPhase('exit');
      const t = window.setTimeout(
        () => {
          setVisible(false);
          onComplete();
        },
        reduce ? 120 : 600,
      );
      return () => clearTimeout(t);
    }

    setPhase('welcome');
    let i = 0;
    let timer: number | undefined;

    const advance = () => {
      const scene = SCENES[i];
      if (!scene || scene.phase === 'cta') {
        setPhase('cta');
        return;
      }
      setPhase(scene.phase);
      if (reduce) {
        // Jump quickly through scenes for a11y
        i += 1;
        timer = window.setTimeout(advance, scene.phase === 'welcome' ? 400 : 180);
        return;
      }
      timer = window.setTimeout(() => {
        i += 1;
        advance();
      }, scene.duration);
    };

    advance();
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [onComplete, reduce]);

  if (!visible) return null;

  const mapSmall = phase === 'brand' || phase === 'cta' || phase === 'exit';

  return (
    <AnimatePresence>
      {visible ? (
        <motion.div
          className="fixed inset-0 z-[100] flex min-h-[100svh] flex-col overflow-hidden"
          initial={{ opacity: 1 }}
          animate={
            phase === 'exit'
              ? { opacity: 0, backgroundColor: '#F8F6F0' }
              : { opacity: 1 }
          }
          exit={{ opacity: 0 }}
          transition={{ duration: reduce ? 0.2 : 0.85, ease: EASE_OUT }}
          role="dialog"
          aria-label="Bienvenue sur SmartMboa"
        >
          {/* Background */}
          <motion.div
            className="absolute inset-0"
            initial={reduce ? { scale: 1 } : { scale: 1.02 }}
            animate={reduce ? { scale: 1 } : { scale: 1.06 }}
            transition={{ duration: 10, ease: 'linear' }}
          >
            <Image
              src="/images/hero-landscape.jpg"
              alt=""
              fill
              priority
              sizes="100vw"
              className="object-cover"
            />
            <div
              className="absolute inset-0"
              style={{
                background:
                  'linear-gradient(180deg, rgba(11,61,46,0.45) 0%, rgba(11,61,46,0.55) 45%, rgba(11,61,46,0.72) 100%)',
              }}
            />
            {/* Subtle light sweep */}
            {!reduce ? (
              <motion.div
                className="absolute inset-0 opacity-30"
                style={{
                  background:
                    'radial-gradient(ellipse 50% 40% at 70% 20%, rgba(214,168,79,0.35), transparent 60%)',
                }}
                animate={{ opacity: [0.2, 0.4, 0.25] }}
                transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
              />
            ) : null}
          </motion.div>

          {/* Skip */}
          {phase !== 'exit' ? (
            <button
              type="button"
              onClick={finish}
              className="absolute right-4 top-[max(1rem,env(safe-area-inset-top))] z-20 rounded-full px-3 py-1.5 text-sm text-white/70 transition hover:bg-white/10 hover:text-white"
              aria-label="Passer l'introduction"
            >
              Passer
            </button>
          ) : null}

          {/* Content */}
          <div className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 pb-16 pt-20 text-center text-white">
            <motion.div
              animate={
                mapSmall
                  ? { scale: 0.78, y: -12 }
                  : { scale: 1, y: 0 }
              }
              transition={{ duration: 0.7, ease: EASE_OUT }}
            >
              <CameroonSilhouette size="lg" showPoints={phase !== 'boot'} />
            </motion.div>

            <div className="mt-6 min-h-[9rem] w-full max-w-lg">
              <AnimatePresence mode="wait">
                {phase === 'welcome' ? (
                  <SceneKey key="welcome">
                    <p className="text-xs font-semibold tracking-[0.35em] text-[var(--gold-soft)]">
                      BIENVENUE
                    </p>
                    <p className="mt-2 font-display text-3xl font-semibold md:text-4xl">
                      AU CAMEROUN
                    </p>
                  </SceneKey>
                ) : null}

                {phase === 'mountains' ? (
                  <SceneKey key="mountains">
                    <p className="font-display text-2xl md:text-3xl">Des montagnes…</p>
                  </SceneKey>
                ) : null}
                {phase === 'forests' ? (
                  <SceneKey key="forests">
                    <p className="font-display text-2xl md:text-3xl">Des forêts…</p>
                  </SceneKey>
                ) : null}
                {phase === 'beaches' ? (
                  <SceneKey key="beaches">
                    <p className="font-display text-2xl md:text-3xl">Des plages…</p>
                  </SceneKey>
                ) : null}
                {phase === 'cultures' ? (
                  <SceneKey key="cultures">
                    <p className="font-display text-2xl md:text-3xl">Des cultures…</p>
                  </SceneKey>
                ) : null}
                {phase === 'stories' ? (
                  <SceneKey key="stories">
                    <p className="font-display text-2xl md:text-3xl">Des histoires…</p>
                  </SceneKey>
                ) : null}
                {phase === 'miniature' ? (
                  <SceneKey key="miniature">
                    <p className="font-display text-2xl font-semibold md:text-3xl">
                      L&apos;Afrique en miniature.
                    </p>
                    <p className="mt-3 text-base text-white/85 md:text-lg">
                      Un pays à découvrir.
                      <br />
                      Une histoire à vivre.
                    </p>
                  </SceneKey>
                ) : null}

                {phase === 'brand' || phase === 'cta' ? (
                  <SceneKey key="brand">
                    <p className="font-display text-4xl font-bold tracking-tight md:text-5xl">
                      {APP_NAME.toUpperCase()}
                    </p>
                    <p className="mt-3 text-base text-white/90 md:text-lg">
                      Votre guide intelligent pour découvrir le Cameroun.
                    </p>
                    <p className="mt-2 text-sm tracking-wide text-[var(--gold-soft)]">
                      Explorez. Découvrez. Planifiez. Voyagez.
                    </p>
                  </SceneKey>
                ) : null}
              </AnimatePresence>
            </div>

            {phase === 'cta' || phase === 'brand' ? (
              <motion.button
                type="button"
                onClick={finish}
                className="mt-8 inline-flex items-center gap-2 rounded-full bg-[var(--green-deep)] px-7 py-3.5 text-base font-semibold text-white shadow-[0_10px_40px_rgba(0,0,0,0.25)] ring-1 ring-[var(--gold)]/50"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                whileHover={reduce ? undefined : { x: 4 }}
                whileTap={{ scale: 0.97 }}
                transition={{ duration: 0.45, ease: EASE_OUT }}
                aria-label="Commencer l'exploration"
              >
                Commencer l&apos;exploration
                <ArrowRight className="h-5 w-5" aria-hidden />
              </motion.button>
            ) : null}
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function SceneKey({ children }: { children: React.ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 14 }}
      animate={reduce ? { opacity: 1 } : { opacity: 1, y: 0 }}
      exit={reduce ? { opacity: 0 } : { opacity: 0, y: -10 }}
      transition={{ duration: reduce ? 0.15 : 0.45, ease: EASE_OUT }}
    >
      {children}
    </motion.div>
  );
}
