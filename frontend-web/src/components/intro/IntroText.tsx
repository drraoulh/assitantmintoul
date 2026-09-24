'use client';

import { AnimatePresence, motion } from 'framer-motion';

import type { IntroPhase } from '@/lib/intro';

const EASE = [0.22, 1, 0.36, 1] as const;

function Line({
  children,
  className = '',
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.p
      className={className}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.55, delay, ease: EASE }}
    >
      {children}
    </motion.p>
  );
}

export function IntroText({
  phase,
  reduce,
}: {
  phase: IntroPhase;
  reduce: boolean;
}) {
  if (reduce) return null;

  return (
    <div className="relative z-20 mx-auto mt-5 min-h-[7.5rem] w-full max-w-lg px-4 text-center">
      <AnimatePresence mode="wait">
        {phase === 'REGION_NORTH' ? (
          <Line key="n" className="font-display text-xl text-[#F8F5ED] md:text-2xl">
            Au nord, la savane et les lamidats.
          </Line>
        ) : null}

        {phase === 'REGION_WEST' ? (
          <Line key="w" className="font-display text-xl text-[#F8F5ED] md:text-2xl">
            À l&apos;ouest, les chefferies des hauteurs.
          </Line>
        ) : null}

        {phase === 'REGION_CENTER' ? (
          <Line key="c" className="font-display text-xl text-[#F8F5ED] md:text-2xl">
            Au centre, la forêt qui se souvient.
          </Line>
        ) : null}

        {phase === 'REGION_COAST' ? (
          <Line key="coast" className="font-display text-xl text-[#F8F5ED] md:text-2xl">
            Sur la côte, l&apos;eau qui raconte.
          </Line>
        ) : null}

        {phase === 'CULTURES' ? (
          <motion.div
            key="cultures"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5, ease: EASE }}
          >
            <p className="font-display text-xl text-[#F8F5ED] md:text-2xl">
              Près de 250 peuples.
            </p>
            <p className="mt-1 font-display text-lg text-[#E5C76B] md:text-xl">
              Plus de 200 langues.
            </p>
            <p className="mt-3 text-[11px] leading-relaxed text-white/45">
              Formulation culturelle de référence — non exhaustive.
            </p>
          </motion.div>
        ) : null}

        {phase === 'UNIFICATION' ? (
          <motion.div
            key="uni"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.55, ease: EASE }}
          >
            <p className="font-display text-2xl font-semibold text-[#F8F5ED] md:text-3xl">
              Quatre mondes.
              <br />
              Une seule terre.
            </p>
            <div className="mt-4 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-[10px] tracking-[0.2em] text-[#E5C76B] md:text-[11px]">
              <span>GRASSFIELDS</span>
              <span className="text-white/30">·</span>
              <span>SAWA</span>
              <span className="text-white/30">·</span>
              <span>FANG-BETI</span>
              <span className="text-white/30">·</span>
              <span>SOUDANO-SAHÉLIENNE</span>
            </div>
          </motion.div>
        ) : null}

        {phase === 'AFRICA_MINIATURE' ? (
          <Line
            key="mini"
            className="font-display text-2xl font-semibold text-[#F8F5ED] md:text-3xl"
          >
            L&apos;Afrique en miniature.
          </Line>
        ) : null}

        {phase === 'CAMEROON' ? (
          <Line
            key="cm"
            className="font-display text-3xl font-bold leading-tight tracking-tight text-[#F8F5ED] md:text-5xl"
          >
            ÇA, C&apos;EST LE CAMEROUN.
          </Line>
        ) : null}

        {phase === 'BRAND' || phase === 'READY' ? (
          <motion.div
            key="brand"
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6, ease: EASE }}
          >
            <p className="font-display text-4xl font-bold tracking-tight text-[#F8F5ED] md:text-5xl">
              SMARTMBOA
            </p>
            <p className="mt-3 text-base text-white/85 md:text-lg">
              Votre guide intelligent pour découvrir le Cameroun.
            </p>
            <p className="mt-2 text-sm tracking-[0.22em] text-[#E5C76B]">
              Découvrez. Explorez. Vivez.
            </p>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

/** Simplified copy stack for prefers-reduced-motion. */
export function ReducedIntroCopy() {
  return (
    <div className="mx-auto max-w-md px-4 text-center text-[#F8F5ED]">
      <p className="text-xs tracking-[0.3em] text-[#E5C76B]">BIENVENUE</p>
      <p className="mt-2 font-display text-3xl font-semibold">Au Cameroun.</p>
      <ul className="mt-6 space-y-2 text-sm text-white/80">
        <li>Une terre.</li>
        <li>Des peuples.</li>
        <li>Des cultures.</li>
        <li>Des histoires.</li>
      </ul>
      <p className="mt-5 text-[11px] tracking-[0.18em] text-[#E5C76B]">
        Grassfields · Sawa · Fang-Beti · Soudano-Sahélienne
      </p>
      <p className="mt-4 font-display text-lg">Un seul Cameroun.</p>
      <p className="mt-6 font-display text-3xl font-bold">SMARTMBOA</p>
    </div>
  );
}
