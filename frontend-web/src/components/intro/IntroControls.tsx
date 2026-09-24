'use client';

export function IntroControls({ onSkip }: { onSkip: () => void }) {
  return (
    <div className="absolute right-3 top-[max(0.75rem,env(safe-area-inset-top))] z-30 md:right-5">
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
