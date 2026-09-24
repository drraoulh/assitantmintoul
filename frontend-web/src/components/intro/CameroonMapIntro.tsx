'use client';

import { motion } from 'framer-motion';

import mapData from '../../../public/maps/cameroon-points.json';
import {
  CULTURAL_ZONES,
  ZONE_COLORS,
  type IntroPhase,
} from '@/lib/intro';

type Point = { id: string; label: string; x: number; y: number };

const points = mapData.points as Point[];
const byId = Object.fromEntries(points.map((p) => [p.id, p]));

const CENTER = { x: 160, y: 210 };

function regionGlow(phase: IntroPhase): string[] {
  switch (phase) {
    case 'REGION_NORTH':
      return ['extreme-nord', 'nord', 'adamaoua'];
    case 'REGION_WEST':
      return ['ouest', 'nord-ouest'];
    case 'REGION_CENTER':
      return ['centre', 'est', 'sud'];
    case 'REGION_COAST':
      return ['littoral', 'sud-ouest'];
    case 'CULTURES':
    case 'UNIFICATION':
    case 'AFRICA_MINIATURE':
    case 'CAMEROON':
    case 'BRAND':
    case 'READY':
      return points.map((p) => p.id);
    default:
      return [];
  }
}

function trailTarget(phase: IntroPhase): Point | null {
  switch (phase) {
    case 'REGION_NORTH':
      return byId.nord ?? null;
    case 'REGION_WEST':
      return byId.ouest ?? null;
    case 'REGION_CENTER':
      return byId.centre ?? null;
    case 'REGION_COAST':
      return byId.littoral ?? null;
    default:
      return null;
  }
}

function fillForPhase(phase: IntroPhase): string {
  if (phase === 'REGION_NORTH') return '#C4A574';
  if (phase === 'REGION_WEST') return '#D4AF37';
  if (phase === 'REGION_CENTER') return '#0B3D2E';
  if (phase === 'REGION_COAST') return '#145A42';
  if (
    phase === 'UNIFICATION' ||
    phase === 'AFRICA_MINIATURE' ||
    phase === 'CAMEROON' ||
    phase === 'BRAND' ||
    phase === 'READY'
  ) {
    return '#0B3D2E';
  }
  return '#0B3D2E';
}

function mapOpacity(phase: IntroPhase): number {
  if (phase === 'INTRO') return 0;
  if (phase === 'CAMEROON') return 0.2;
  if (phase === 'BRAND' || phase === 'READY') return 0.28;
  if (phase === 'EXITING') return 0.55;
  return 1;
}

function mapScale(phase: IntroPhase): number {
  if (phase === 'INTRO') return 0.92;
  if (phase === 'AFRICA_MINIATURE') return 1.02;
  if (phase === 'CAMEROON') return 1.04;
  if (phase === 'BRAND' || phase === 'READY') return 0.88;
  if (phase === 'EXITING') return 1.12;
  return 1;
}

export function CameroonMapIntro({
  phase,
  reduce,
}: {
  phase: IntroPhase;
  reduce: boolean;
}) {
  const glowIds = new Set(regionGlow(phase));
  const target = trailTarget(phase);
  const showOutline =
    phase !== 'INTRO' && phase !== 'DONE';
  const showStars = phase === 'CULTURES' || phase === 'UNIFICATION';
  const unify =
    phase === 'UNIFICATION' ||
    phase === 'AFRICA_MINIATURE' ||
    phase === 'CAMEROON' ||
    phase === 'BRAND' ||
    phase === 'READY' ||
    phase === 'EXITING';
  const showCoastRipple = phase === 'REGION_COAST';

  // Culture star positions = existing region points only (no invented coords)
  const starPoints = points;

  return (
    <motion.div
      className="relative mx-auto flex w-[min(78vw,340px)] items-center justify-center md:w-[min(70vh,520px)]"
      animate={{
        opacity: mapOpacity(phase),
        scale: reduce ? 1 : mapScale(phase),
        filter:
          phase === 'EXITING'
            ? 'blur(10px)'
            : phase === 'CAMEROON'
              ? 'blur(0px)'
              : 'blur(0px)',
      }}
      transition={{ duration: reduce ? 0.2 : 0.85, ease: [0.22, 1, 0.36, 1] }}
    >
      {/* Soft halo */}
      {(phase === 'AFRICA_MINIATURE' ||
        phase === 'CAMEROON' ||
        phase === 'BRAND' ||
        phase === 'READY') &&
      !reduce ? (
        <motion.div
          className="pointer-events-none absolute inset-[-18%] rounded-full"
          style={{
            background:
              'radial-gradient(circle, rgba(212,175,55,0.28) 0%, rgba(212,175,55,0.06) 45%, transparent 70%)',
          }}
          initial={{ opacity: 0 }}
          animate={{ opacity: [0.45, 0.75, 0.55] }}
          transition={{ duration: 3.2, repeat: Infinity, ease: 'easeInOut' }}
        />
      ) : null}

      <svg
        viewBox={mapData.viewBox}
        className="relative z-10 h-auto w-full"
        role="img"
        aria-label="Carte stylisée du Cameroun"
      >
        <defs>
          <linearGradient id="introFill" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={fillForPhase(phase)} />
            <stop offset="100%" stopColor={unify ? '#145A42' : fillForPhase(phase)} />
          </linearGradient>
          <filter id="introGlow" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow
              dx="0"
              dy="0"
              stdDeviation="8"
              floodColor={unify ? '#D4AF37' : '#E5C76B'}
              floodOpacity="0.45"
            />
          </filter>
          <linearGradient id="trailGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="rgba(229,199,107,0)" />
            <stop offset="50%" stopColor="rgba(229,199,107,0.95)" />
            <stop offset="100%" stopColor="rgba(229,199,107,0)" />
          </linearGradient>
        </defs>

        {/* Country silhouette */}
        {showOutline ? (
          <motion.path
            d={mapData.path}
            fill="url(#introFill)"
            stroke={unify ? '#D4AF37' : '#E5C76B'}
            strokeWidth={unify ? 2.4 : 1.6}
            filter={reduce ? undefined : 'url(#introGlow)'}
            initial={reduce ? false : { opacity: 0, pathLength: 0.15 }}
            animate={{ opacity: 1, pathLength: 1 }}
            transition={{ duration: reduce ? 0.2 : 1.1, ease: 'easeOut' }}
          />
        ) : null}

        {/* Cultural zone soft overlays via region dots (no fake polygons) */}
        {unify && !reduce
          ? (Object.keys(CULTURAL_ZONES) as (keyof typeof CULTURAL_ZONES)[]).map(
              (zone) =>
                CULTURAL_ZONES[zone].map((id) => {
                  const p = byId[id];
                  if (!p) return null;
                  return (
                    <motion.circle
                      key={`zone-${zone}-${id}`}
                      cx={p.x}
                      cy={p.y}
                      r={28}
                      fill={ZONE_COLORS[zone]}
                      initial={{ opacity: 0.35 }}
                      animate={{ opacity: phase === 'UNIFICATION' ? 0.28 : 0.08 }}
                      transition={{ duration: 1.2 }}
                    />
                  );
                }),
            )
          : null}

        {/* Light trail from center to region */}
        {target && !reduce ? (
          <motion.line
            x1={CENTER.x}
            y1={CENTER.y}
            x2={target.x}
            y2={target.y}
            stroke="url(#trailGrad)"
            strokeWidth="2.5"
            strokeLinecap="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: [0, 1, 0.65] }}
            transition={{ duration: 0.9, ease: 'easeOut' }}
          />
        ) : null}

        {/* Region highlight points */}
        {points.map((p) => {
          const active = glowIds.has(p.id);
          if (!active && phase !== 'CULTURES') return null;
          const coast = phase === 'REGION_COAST' && (p.id === 'littoral' || p.id === 'sud-ouest');
          return (
            <g key={p.id}>
              <motion.circle
                cx={p.x}
                cy={p.y}
                r={coast ? 6 : 4.5}
                fill={coast ? '#2C8FB3' : '#D4AF37'}
                initial={reduce ? false : { opacity: 0, scale: 0 }}
                animate={{ opacity: active ? 1 : 0.35, scale: 1 }}
                transition={{ duration: 0.45 }}
              />
              {!reduce && active ? (
                <motion.circle
                  cx={p.x}
                  cy={p.y}
                  r={4.5}
                  fill="none"
                  stroke={coast ? '#2C8FB3' : '#F8F5ED'}
                  strokeWidth="1.2"
                  initial={{ opacity: 0, scale: 1 }}
                  animate={{ opacity: [0.6, 0], scale: [1, 2.6] }}
                  transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut' }}
                />
              ) : null}
            </g>
          );
        })}

        {/* Coast ripple — littoral / sud-ouest only (existing coords) */}
        {showCoastRipple && !reduce
          ? ['littoral', 'sud-ouest'].map((id) => {
              const p = byId[id];
              if (!p) return null;
              return (
                <motion.circle
                  key={`ripple-${id}`}
                  cx={p.x}
                  cy={p.y}
                  r={10}
                  fill="none"
                  stroke="#2C8FB3"
                  strokeWidth="1.4"
                  initial={{ opacity: 0.7, scale: 0.6 }}
                  animate={{ opacity: [0.55, 0], scale: [0.8, 2.4] }}
                  transition={{ duration: 1.8, repeat: Infinity, ease: 'easeOut' }}
                />
              );
            })
          : null}

        {/* Culture stars — region points only */}
        {showStars
          ? starPoints.map((p, i) => (
              <motion.circle
                key={`star-${p.id}`}
                cx={p.x}
                cy={p.y}
                r={2.2}
                fill="#F8F5ED"
                initial={reduce ? false : { opacity: 0, scale: 0 }}
                animate={{ opacity: [0, 1, 0.85], scale: 1 }}
                transition={{
                  delay: reduce ? 0 : 0.08 * i,
                  duration: 0.5,
                }}
              />
            ))
          : null}

        {/* Center breath seed (INTRO) */}
        {phase === 'INTRO' ? (
          <motion.circle
            cx={CENTER.x}
            cy={CENTER.y}
            r={3.5}
            fill="#E5C76B"
            animate={
              reduce
                ? { opacity: 1 }
                : { opacity: [0.35, 1, 0.35], scale: [0.85, 1.25, 0.85] }
            }
            transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
          />
        ) : null}
      </svg>

      {/* Coast city labels — text only, no invented map pins */}
      {phase === 'REGION_COAST' ? (
        <motion.p
          className="absolute bottom-[8%] left-1/2 z-20 -translate-x-1/2 whitespace-nowrap text-[11px] tracking-[0.18em] text-[#9FD4E8] md:text-xs"
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.9 }}
        >
          Douala · Kribi · Limbe
        </motion.p>
      ) : null}
    </motion.div>
  );
}
