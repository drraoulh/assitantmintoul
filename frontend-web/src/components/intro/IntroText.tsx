'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';

import { typeHaptic } from '@/lib/haptics';
import { CM_FLAG, type IntroPhase } from '@/lib/intro';

const MS_PER_CHAR = 78;
const MS_PER_CHAR_TITLE = 92;

type TypeLine = {
  text: string;
  className?: string;
  msPerChar?: number;
  delayBefore?: number;
  accent?: 'yellow' | 'red' | 'green' | 'water' | 'ivory';
};

function accentColor(accent?: TypeLine['accent']): string | undefined {
  if (accent === 'yellow') return CM_FLAG.yellow;
  if (accent === 'red') return CM_FLAG.red;
  if (accent === 'green') return CM_FLAG.green;
  if (accent === 'water') return CM_FLAG.water;
  if (accent === 'ivory') return CM_FLAG.ivory;
  return undefined;
}

/** Character-by-character writing with phone vibration ticks. */
function Typewriter({
  lines,
  onComplete,
  reduce,
}: {
  lines: TypeLine[];
  onComplete?: () => void;
  reduce: boolean;
}) {
  const [lineIndex, setLineIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(0);
  const [started, setStarted] = useState(false);
  const [done, setDone] = useState(false);
  const completedRef = useRef(false);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;
  const linesRef = useRef(lines);
  const current = linesRef.current[lineIndex];
  const ms = current?.msPerChar ?? MS_PER_CHAR;

  useEffect(() => {
    if (!reduce) return;
    completedRef.current = true;
    setDone(true);
    const t = window.setTimeout(() => onCompleteRef.current?.(), 60);
    return () => clearTimeout(t);
  }, [reduce]);

  useEffect(() => {
    if (reduce) return;
    const delay = linesRef.current[0]?.delayBefore ?? 280;
    const t = window.setTimeout(() => setStarted(true), delay);
    return () => clearTimeout(t);
  }, [reduce]);

  useEffect(() => {
    if (reduce || !started || !current || done) return;

    if (charIndex >= current.text.length) {
      if (lineIndex >= linesRef.current.length - 1) {
        if (!completedRef.current) {
          completedRef.current = true;
          setDone(true);
          window.setTimeout(() => onCompleteRef.current?.(), 180);
        }
        return;
      }
      const nextDelay = linesRef.current[lineIndex + 1]?.delayBefore ?? 420;
      const t = window.setTimeout(() => {
        setLineIndex((i) => i + 1);
        setCharIndex(0);
      }, nextDelay);
      return () => clearTimeout(t);
    }

    const t = window.setTimeout(() => {
      typeHaptic(current.text[charIndex] ?? '');
      setCharIndex((c) => c + 1);
    }, ms);

    return () => clearTimeout(t);
  }, [charIndex, current, done, lineIndex, ms, reduce, started]);

  if (reduce) {
    return (
      <div aria-live="polite">
        {linesRef.current.map((line, i) => (
          <p
            key={`${line.text}-${i}`}
            className={line.className}
            style={{ color: accentColor(line.accent) }}
          >
            {line.text}
          </p>
        ))}
      </div>
    );
  }

  return (
    <div aria-live="polite">
      {linesRef.current.map((line, i) => {
        if (!done && i > lineIndex) return null;
        const shown = done || i < lineIndex ? line.text : line.text.slice(0, charIndex);
        const isActive = !done && i === lineIndex;
        return (
          <p
            key={`${line.text}-${i}`}
            className={line.className}
            style={{ color: accentColor(line.accent) }}
          >
            {shown}
            {isActive ? (
              <span
                className="ml-0.5 inline-block h-[0.95em] w-[0.09em] translate-y-[0.06em] animate-pulse align-baseline"
                style={{ background: CM_FLAG.yellow }}
                aria-hidden
              />
            ) : null}
          </p>
        );
      })}
    </div>
  );
}

function linesFor(phase: IntroPhase): TypeLine[] | null {
  switch (phase) {
    case 'REGION_NORTH':
      return [
        {
          text: 'Au nord, la savane et les lamidats.',
          className: 'font-display text-xl md:text-2xl',
          accent: 'yellow',
        },
      ];
    case 'REGION_WEST':
      return [
        {
          text: "À l'ouest, les chefferies des hauteurs.",
          className: 'font-display text-xl md:text-2xl',
          accent: 'red',
        },
      ];
    case 'REGION_CENTER':
      return [
        {
          text: 'Au centre, la forêt qui se souvient.',
          className: 'font-display text-xl md:text-2xl',
          accent: 'green',
        },
      ];
    case 'REGION_COAST':
      return [
        {
          text: "Sur la côte, l'eau qui raconte.",
          className: 'font-display text-xl md:text-2xl',
          accent: 'water',
        },
      ];
    case 'CULTURES':
      return [
        {
          text: 'Près de 250 peuples.',
          className: 'font-display text-xl md:text-2xl',
          accent: 'ivory',
        },
        {
          text: 'Plus de 200 langues.',
          className: 'mt-1 font-display text-lg md:text-xl',
          accent: 'yellow',
          delayBefore: 480,
        },
      ];
    case 'UNIFICATION':
      return [
        {
          text: 'Quatre mondes.',
          className: 'font-display text-2xl font-semibold md:text-3xl',
          accent: 'ivory',
          msPerChar: MS_PER_CHAR_TITLE,
        },
        {
          text: 'Une seule terre.',
          className: 'font-display text-2xl font-semibold md:text-3xl',
          accent: 'yellow',
          delayBefore: 500,
          msPerChar: MS_PER_CHAR_TITLE,
        },
        {
          text: 'GRASSFIELDS · SAWA · FANG-BETI · SOUDANO-SAHÉLIENNE',
          className: 'mt-4 text-[10px] tracking-[0.16em] md:text-[11px]',
          accent: 'red',
          delayBefore: 560,
          msPerChar: 42,
        },
      ];
    case 'AFRICA_MINIATURE':
      return [
        {
          text: "L'Afrique en miniature.",
          className: 'font-display text-2xl font-semibold md:text-3xl',
          accent: 'yellow',
          msPerChar: MS_PER_CHAR_TITLE,
        },
      ];
    case 'CAMEROON':
      return [
        {
          text: "ÇA, C'EST LE CAMEROUN.",
          className:
            'font-display text-3xl font-bold leading-tight tracking-tight md:text-5xl',
          accent: 'ivory',
          msPerChar: MS_PER_CHAR_TITLE,
        },
      ];
    case 'BRAND':
    case 'READY':
      return [
        {
          text: 'SMARTMBOA',
          className: 'font-display text-4xl font-bold tracking-tight md:text-5xl',
          accent: 'ivory',
          msPerChar: MS_PER_CHAR_TITLE,
        },
        {
          text: 'Votre guide intelligent pour découvrir le Cameroun.',
          className: 'mt-3 text-base text-white/85 md:text-lg',
          accent: 'ivory',
          delayBefore: 520,
        },
        {
          text: 'Découvrez. Explorez. Vivez.',
          className: 'mt-2 text-sm tracking-[0.22em]',
          accent: 'yellow',
          delayBefore: 420,
          msPerChar: 70,
        },
      ];
    default:
      return null;
  }
}

export function IntroText({
  phase,
  reduce,
  onTyped,
}: {
  phase: IntroPhase;
  reduce: boolean;
  onTyped?: (phase: IntroPhase) => void;
}) {
  const lines = linesFor(phase);

  return (
    <div className="relative z-20 mx-auto mt-5 min-h-[8rem] w-full max-w-lg px-4 text-center">
      <AnimatePresence mode="wait">
        {phase === 'INTRO' ? (
          <motion.div key="seed" className="h-8" />
        ) : null}

        {lines ? (
          <motion.div
            key={phase}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.4 }}
          >
            <Typewriter
              lines={lines}
              reduce={reduce}
              onComplete={() => onTyped?.(phase)}
            />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

export function ReducedIntroCopy() {
  return (
    <div className="mx-auto max-w-md px-4 text-center text-[#F8F5ED]">
      <p className="text-xs tracking-[0.3em]" style={{ color: CM_FLAG.yellow }}>
        BIENVENUE
      </p>
      <p className="mt-2 font-display text-3xl font-semibold">Au Cameroun.</p>
      <ul className="mt-6 space-y-2 text-sm text-white/80">
        <li style={{ color: CM_FLAG.yellow }}>Une terre.</li>
        <li style={{ color: CM_FLAG.red }}>Des peuples.</li>
        <li style={{ color: CM_FLAG.green }}>Des cultures.</li>
        <li>Des histoires.</li>
      </ul>
      <p className="mt-5 text-[11px] tracking-[0.18em]" style={{ color: CM_FLAG.yellow }}>
        Grassfields · Sawa · Fang-Beti · Soudano-Sahélienne
      </p>
      <p className="mt-4 font-display text-lg">Un seul Cameroun.</p>
      <p className="mt-6 font-display text-3xl font-bold">SMARTMBOA</p>
    </div>
  );
}
