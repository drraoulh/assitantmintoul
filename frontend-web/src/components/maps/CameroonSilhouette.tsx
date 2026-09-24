'use client';

import { motion, useReducedMotion } from 'framer-motion';
import { useMemo } from 'react';

import mapData from '../../../public/maps/cameroon-points.json';

type Point = {
  id: string;
  label: string;
  x: number;
  y: number;
};

const points = mapData.points as Point[];

export function CameroonSilhouette({
  size = 'md',
  showPoints = true,
  className = '',
  glow = true,
}: {
  size?: 'sm' | 'md' | 'lg';
  showPoints?: boolean;
  className?: string;
  glow?: boolean;
}) {
  const reduce = useReducedMotion();
  const dims = size === 'sm' ? 140 : size === 'lg' ? 280 : 200;

  const pointDelay = useMemo(
    () => points.map((_, i) => 0.35 + i * 0.18),
    [],
  );

  return (
    <div
      className={`relative inline-flex items-center justify-center ${className}`}
      style={{ width: dims, height: (dims * 400) / 320 }}
      aria-hidden={!showPoints}
    >
      {glow ? (
        <div
          className="pointer-events-none absolute inset-[-12%] rounded-full opacity-70"
          style={{
            background:
              'radial-gradient(circle, rgba(214,168,79,0.28) 0%, rgba(214,168,79,0.08) 45%, transparent 70%)',
          }}
        />
      ) : null}

      <motion.svg
        viewBox={mapData.viewBox}
        width="100%"
        height="100%"
        role="img"
        aria-label="Carte stylisée du Cameroun"
        initial={reduce ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.85 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: reduce ? 0.25 : 1.1, ease: [0.22, 1, 0.36, 1] }}
      >
        <defs>
          <linearGradient id="cmFill" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#0B3D2E" />
            <stop offset="100%" stopColor="#145C43" />
          </linearGradient>
          <filter id="cmSoft" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow
              dx="0"
              dy="4"
              stdDeviation="6"
              floodColor="#D6A84F"
              floodOpacity="0.35"
            />
          </filter>
        </defs>
        <path
          d={mapData.path}
          fill="url(#cmFill)"
          stroke="#D6A84F"
          strokeWidth="2"
          filter={glow ? 'url(#cmSoft)' : undefined}
        />

        {showPoints
          ? points.map((p, i) => (
              <g key={p.id}>
                <motion.circle
                  cx={p.x}
                  cy={p.y}
                  r={4}
                  fill="#D6A84F"
                  initial={reduce ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{
                    delay: reduce ? 0 : pointDelay[i],
                    duration: 0.35,
                  }}
                />
                {!reduce ? (
                  <motion.circle
                    cx={p.x}
                    cy={p.y}
                    r={4}
                    fill="none"
                    stroke="#FFFFFF"
                    strokeWidth="1.2"
                    initial={{ opacity: 0, scale: 1 }}
                    animate={{ opacity: [0, 0.7, 0], scale: [1, 2.4, 2.8] }}
                    transition={{
                      delay: pointDelay[i] + 0.2,
                      duration: 1.6,
                      repeat: Infinity,
                      repeatDelay: 2.5,
                      ease: 'easeOut',
                    }}
                  />
                ) : null}
              </g>
            ))
          : null}
      </motion.svg>
    </div>
  );
}
