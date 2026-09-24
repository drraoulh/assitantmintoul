'use client';

import { Volume2, VolumeX } from 'lucide-react';

export function IntroControls({
  soundEnabled,
  onToggleSound,
  onSkip,
  showSound,
}: {
  soundEnabled: boolean;
  onToggleSound: () => void;
  onSkip: () => void;
  showSound: boolean;
}) {
  return (
    <div className="absolute right-3 top-[max(0.75rem,env(safe-area-inset-top))] z-30 flex items-center gap-1 md:right-5">
      {showSound ? (
        <button
          type="button"
          onClick={onToggleSound}
          className="rounded-full px-2.5 py-1.5 text-white/55 transition hover:bg-white/10 hover:text-white/90"
          aria-label={soundEnabled ? 'Couper le son' : 'Activer le son'}
          aria-pressed={soundEnabled}
        >
          {soundEnabled ? (
            <Volume2 className="h-4 w-4" aria-hidden />
          ) : (
            <VolumeX className="h-4 w-4" aria-hidden />
          )}
        </button>
      ) : null}
      <button
        type="button"
        onClick={onSkip}
        className="rounded-full px-3 py-1.5 text-sm text-white/55 transition hover:bg-white/10 hover:text-white/90"
        aria-label="Passer l'introduction"
      >
        Passer →
      </button>
    </div>
  );
}
