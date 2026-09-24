'use client';

import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import Image from 'next/image';
import { useCallback, useEffect, useRef, useState } from 'react';

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
  | 'exit';

/** Pause after typing finishes so the line can be read. */
const HOLD_AFTER_TYPE_MS = 1400;
const HOLD_AFTER_WELCOME_MS = 1800;
const HOLD_AFTER_MINIATURE_MS = 2200;
const HOLD_AFTER_BRAND_MS = 1600;

/** ~ms per character — slow enough to feel handwritten / typed. */
const MS_PER_CHAR = 72;
const MS_PER_CHAR_TITLE = 88;

/** Scenes that auto-advance after typewriter + hold (cta waits for tap). */
const AUTO_SCENES: Phase[] = [
  'welcome',
  'mountains',
  'forests',
  'beaches',
  'cultures',
  'stories',
  'miniature',
  'brand',
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

/** Light haptic — works on most Android browsers; iOS Safari does not support Vibration API. */
function haptic(pattern: number | number[] = [28, 40, 28]) {
  try {
    if (typeof navigator === 'undefined') return;
    const vibrate = navigator.vibrate?.bind(navigator);
    if (typeof vibrate !== 'function') return;
    // Cancel any ongoing vibration then pulse
    vibrate(0);
    vibrate(pattern);
  } catch {
    /* ignore */
  }
}

function holdFor(phase: Phase): number {
  if (phase === 'welcome') return HOLD_AFTER_WELCOME_MS;
  if (phase === 'miniature') return HOLD_AFTER_MINIATURE_MS;
  if (phase === 'brand') return HOLD_AFTER_BRAND_MS;
  return HOLD_AFTER_TYPE_MS;
}

export function ImmersiveWelcome({
  onComplete,
}: {
  onComplete: () => void;
}) {
  const reduceMotion = useReducedMotion();
  const reduce = !!reduceMotion;
  const [phase, setPhase] = useState<Phase>('boot');
  const [visible, setVisible] = useState(true);

  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const reduceRef = useRef(reduce);
  reduceRef.current = reduce;

  const phaseRef = useRef<Phase>('boot');
  phaseRef.current = phase;

  const holdTimerRef = useRef<number | undefined>(undefined);
  const startedRef = useRef(false);
  const finishingRef = useRef(false);

  const clearHold = useCallback(() => {
    if (holdTimerRef.current !== undefined) {
      clearTimeout(holdTimerRef.current);
      holdTimerRef.current = undefined;
    }
  }, []);

  const finish = useCallback(() => {
    if (finishingRef.current) return;
    finishingRef.current = true;
    clearHold();
    markSeen();
    haptic([30, 40, 30]);
    setPhase('exit');
    window.setTimeout(
      () => {
        setVisible(false);
        onCompleteRef.current();
      },
      reduceRef.current ? 200 : 850,
    );
  }, [clearHold]);

  const advanceAfter = useCallback(
    (fromPhase: Phase) => {
      // Ignore stale completions from a scene we already left
      if (phaseRef.current !== fromPhase) return;
      if (finishingRef.current) return;

      clearHold();
      haptic([40, 50, 40]);

      const delay = reduceRef.current ? 280 : holdFor(fromPhase);
      holdTimerRef.current = window.setTimeout(() => {
        if (phaseRef.current !== fromPhase || finishingRef.current) return;

        if (fromPhase === 'brand') {
          setPhase('cta');
          haptic([50, 60, 50]);
          return;
        }

        const idx = AUTO_SCENES.indexOf(fromPhase);
        const next = AUTO_SCENES[idx + 1];
        if (!next) {
          setPhase('cta');
          haptic([50, 60, 50]);
          return;
        }
        setPhase(next);
        haptic(
          next === 'brand' || next === 'miniature'
            ? [45, 55, 45]
            : [35, 45, 35],
        );
      }, delay);
    },
    [clearHold],
  );

  // Boot once — do NOT depend on onComplete (parent often passes an inline fn)
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    if (hasSeenIntro()) {
      setPhase('exit');
      const t = window.setTimeout(
        () => {
          setVisible(false);
          onCompleteRef.current();
        },
        reduceRef.current ? 120 : 600,
      );
      return () => clearTimeout(t);
    }

    setPhase('welcome');
    haptic([18, 30, 18]);

    return () => {
      clearHold();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional one-shot boot
  }, []);

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
          <motion.div
            className="absolute inset-0"
            initial={reduce ? { scale: 1 } : { scale: 1.02 }}
            animate={reduce ? { scale: 1 } : { scale: 1.06 }}
            transition={{ duration: 14, ease: 'linear' }}
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
            {!reduce ? (
              <motion.div
                className="absolute inset-0 opacity-30"
                style={{
                  background:
                    'radial-gradient(ellipse 50% 40% at 70% 20%, rgba(214,168,79,0.35), transparent 60%)',
                }}
                animate={{ opacity: [0.2, 0.4, 0.25] }}
                transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
              />
            ) : null}
          </motion.div>

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

          <div className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 pb-16 pt-20 text-center text-white">
            <motion.div
              animate={mapSmall ? { scale: 0.78, y: -12 } : { scale: 1, y: 0 }}
              transition={{ duration: 0.9, ease: EASE_OUT }}
            >
              <CameroonSilhouette size="lg" showPoints={phase !== 'boot'} />
            </motion.div>

            <div className="mt-6 min-h-[10rem] w-full max-w-lg">
              <AnimatePresence mode="wait">
                {phase === 'welcome' ? (
                  <SceneKey key="welcome">
                    <TypewriterBlock
                      lines={[
                        {
                          text: 'BIENVENUE',
                          className:
                            'text-xs font-semibold tracking-[0.35em] text-[var(--gold-soft)]',
                          msPerChar: MS_PER_CHAR_TITLE,
                        },
                        {
                          text: 'AU CAMEROUN',
                          className:
                            'mt-2 font-display text-3xl font-semibold md:text-4xl',
                          msPerChar: MS_PER_CHAR_TITLE,
                        },
                      ]}
                      reduce={reduce}
                      onComplete={() => advanceAfter('welcome')}
                    />
                  </SceneKey>
                ) : null}

                {phase === 'mountains' ? (
                  <SceneKey key="mountains">
                    <TypewriterBlock
                      lines={[
                        {
                          text: 'Des montagnes…',
                          className: 'font-display text-2xl md:text-3xl',
                        },
                      ]}
                      reduce={reduce}
                      onComplete={() => advanceAfter('mountains')}
                    />
                  </SceneKey>
                ) : null}
                {phase === 'forests' ? (
                  <SceneKey key="forests">
                    <TypewriterBlock
                      lines={[
                        {
                          text: 'Des forêts…',
                          className: 'font-display text-2xl md:text-3xl',
                        },
                      ]}
                      reduce={reduce}
                      onComplete={() => advanceAfter('forests')}
                    />
                  </SceneKey>
                ) : null}
                {phase === 'beaches' ? (
                  <SceneKey key="beaches">
                    <TypewriterBlock
                      lines={[
                        {
                          text: 'Des plages…',
                          className: 'font-display text-2xl md:text-3xl',
                        },
                      ]}
                      reduce={reduce}
                      onComplete={() => advanceAfter('beaches')}
                    />
                  </SceneKey>
                ) : null}
                {phase === 'cultures' ? (
                  <SceneKey key="cultures">
                    <TypewriterBlock
                      lines={[
                        {
                          text: 'Des cultures…',
                          className: 'font-display text-2xl md:text-3xl',
                        },
                      ]}
                      reduce={reduce}
                      onComplete={() => advanceAfter('cultures')}
                    />
                  </SceneKey>
                ) : null}
                {phase === 'stories' ? (
                  <SceneKey key="stories">
                    <TypewriterBlock
                      lines={[
                        {
                          text: 'Des histoires…',
                          className: 'font-display text-2xl md:text-3xl',
                        },
                      ]}
                      reduce={reduce}
                      onComplete={() => advanceAfter('stories')}
                    />
                  </SceneKey>
                ) : null}
                {phase === 'miniature' ? (
                  <SceneKey key="miniature">
                    <TypewriterBlock
                      lines={[
                        {
                          text: "L'Afrique en miniature.",
                          className:
                            'font-display text-2xl font-semibold md:text-3xl',
                          msPerChar: MS_PER_CHAR,
                        },
                        {
                          text: 'Un pays à découvrir.',
                          className: 'mt-3 text-base text-white/85 md:text-lg',
                          delayBefore: 420,
                        },
                        {
                          text: 'Une histoire à vivre.',
                          className: 'text-base text-white/85 md:text-lg',
                          delayBefore: 280,
                        },
                      ]}
                      reduce={reduce}
                      onComplete={() => advanceAfter('miniature')}
                    />
                  </SceneKey>
                ) : null}

                {phase === 'brand' || phase === 'cta' ? (
                  <SceneKey key="brand">
                    <TypewriterBlock
                      lines={[
                        {
                          text: APP_NAME.toUpperCase(),
                          className:
                            'font-display text-4xl font-bold tracking-tight md:text-5xl',
                          msPerChar: MS_PER_CHAR_TITLE,
                        },
                        {
                          text: 'Votre guide intelligent pour découvrir le Cameroun.',
                          className: 'mt-3 text-base text-white/90 md:text-lg',
                          delayBefore: 500,
                        },
                        {
                          text: 'Explorez. Découvrez. Planifiez. Voyagez.',
                          className:
                            'mt-2 text-sm tracking-wide text-[var(--gold-soft)]',
                          delayBefore: 400,
                          msPerChar: 58,
                        },
                      ]}
                      reduce={reduce}
                      onComplete={
                        phase === 'brand'
                          ? () => advanceAfter('brand')
                          : undefined
                      }
                      showCursor={phase === 'brand'}
                      freezeAtEnd={phase === 'cta'}
                    />
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
                transition={{
                  duration: 0.55,
                  ease: EASE_OUT,
                  delay: phase === 'cta' ? 0 : 0.35,
                }}
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
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 10 }}
      animate={reduce ? { opacity: 1 } : { opacity: 1, y: 0 }}
      exit={reduce ? { opacity: 0 } : { opacity: 0, y: -8 }}
      transition={{ duration: reduce ? 0.15 : 0.55, ease: EASE_OUT }}
    >
      {children}
    </motion.div>
  );
}

type TypeLine = {
  text: string;
  className?: string;
  msPerChar?: number;
  /** Extra pause before this line starts. */
  delayBefore?: number;
};

function TypewriterBlock({
  lines,
  reduce,
  onComplete,
  showCursor = true,
  freezeAtEnd = false,
}: {
  lines: TypeLine[];
  reduce: boolean;
  onComplete?: () => void;
  showCursor?: boolean;
  /** When true (e.g. CTA), show full text without retyping. */
  freezeAtEnd?: boolean;
}) {
  const [lineIndex, setLineIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(0);
  const [started, setStarted] = useState(false);
  const [done, setDone] = useState(false);
  const completedRef = useRef(false);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const linesRef = useRef(lines);
  // Keep snapshot from first mount; parent remounts per scene via key
  const current = linesRef.current[lineIndex];
  const ms = current?.msPerChar ?? MS_PER_CHAR;

  const finishTyping = useCallback(() => {
    if (completedRef.current) return;
    completedRef.current = true;
    setDone(true);
    setLineIndex(linesRef.current.length - 1);
    setCharIndex(linesRef.current[linesRef.current.length - 1]?.text.length ?? 0);
    window.setTimeout(() => onCompleteRef.current?.(), 120);
  }, []);

  useEffect(() => {
    if (freezeAtEnd) {
      completedRef.current = true;
      setDone(true);
      setStarted(true);
      setLineIndex(linesRef.current.length - 1);
      setCharIndex(
        linesRef.current[linesRef.current.length - 1]?.text.length ?? 0,
      );
    }
  }, [freezeAtEnd]);

  useEffect(() => {
    if (!reduce || freezeAtEnd) return;
    finishTyping();
  }, [finishTyping, freezeAtEnd, reduce]);

  useEffect(() => {
    if (reduce || freezeAtEnd) return;
    const delay = linesRef.current[0]?.delayBefore ?? 220;
    const t = window.setTimeout(() => setStarted(true), delay);
    return () => clearTimeout(t);
  }, [freezeAtEnd, reduce]);

  useEffect(() => {
    if (reduce || freezeAtEnd || !started || !current || done) return;

    if (charIndex >= current.text.length) {
      if (lineIndex >= linesRef.current.length - 1) {
        finishTyping();
        return;
      }
      const nextDelay = linesRef.current[lineIndex + 1]?.delayBefore ?? 380;
      const t = window.setTimeout(() => {
        setLineIndex((i) => i + 1);
        setCharIndex(0);
      }, nextDelay);
      return () => clearTimeout(t);
    }

    const t = window.setTimeout(() => {
      const nextChar = current.text[charIndex];
      if (nextChar && !/\s|[.…,;:!?]/.test(nextChar)) {
        haptic(5);
      }
      setCharIndex((c) => c + 1);
    }, ms);

    return () => clearTimeout(t);
  }, [
    charIndex,
    current,
    done,
    finishTyping,
    freezeAtEnd,
    lineIndex,
    ms,
    reduce,
    started,
  ]);

  return (
    <div aria-live="polite">
      {linesRef.current.map((line, i) => {
        if (i > lineIndex && !done) return null;
        const shown =
          done || i < lineIndex
            ? line.text
            : line.text.slice(0, charIndex);
        // When done, show all lines
        if (done && i > linesRef.current.length - 1) return null;
        if (done) {
          return (
            <p key={`${line.text}-${i}`} className={line.className}>
              {line.text}
            </p>
          );
        }
        if (i > lineIndex) return null;
        const isActive = i === lineIndex && !done;
        return (
          <p key={`${line.text}-${i}`} className={line.className}>
            {shown}
            {showCursor && isActive ? (
              <span
                className="ml-0.5 inline-block h-[0.95em] w-[0.09em] translate-y-[0.06em] animate-pulse bg-[var(--gold-soft)] align-baseline"
                aria-hidden
              />
            ) : null}
          </p>
        );
      })}
    </div>
  );
}
