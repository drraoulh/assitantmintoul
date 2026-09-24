/**
 * Optional ambient audio for the cinematic intro.
 * Default OFF — browsers block autoplay. Missing files = silent no-op.
 */

type Cue = 'heartbeat' | 'wind' | 'forest' | 'water' | 'silence';

const FILES: Record<Exclude<Cue, 'silence'>, string> = {
  heartbeat: '/audio/heartbeat.mp3',
  wind: '/audio/wind.mp3',
  forest: '/audio/forest.mp3',
  water: '/audio/water.mp3',
};

export class IntroSound {
  private enabled = false;
  private unlocked = false;
  private current: HTMLAudioElement | null = null;
  private volume = 0.22;

  isEnabled() {
    return this.enabled;
  }

  setEnabled(on: boolean) {
    this.enabled = on;
    if (!on) this.stop();
  }

  /** Call after a user gesture so later play() can succeed. */
  unlock() {
    this.unlocked = true;
  }

  async play(cue: Cue) {
    if (!this.enabled || !this.unlocked) return;
    if (cue === 'silence') {
      this.fadeOut(400);
      return;
    }
    const src = FILES[cue];
    try {
      this.stop();
      const audio = new Audio(src);
      audio.volume = this.volume;
      audio.loop = cue === 'heartbeat' || cue === 'wind' || cue === 'forest' || cue === 'water';
      this.current = audio;
      await audio.play();
    } catch {
      /* missing file or autoplay policy — ignore */
    }
  }

  fadeOut(ms = 500) {
    const a = this.current;
    if (!a) return;
    const start = a.volume;
    const t0 = performance.now();
    const step = (now: number) => {
      const p = Math.min(1, (now - t0) / ms);
      a.volume = start * (1 - p);
      if (p < 1) requestAnimationFrame(step);
      else {
        a.pause();
        a.src = '';
        if (this.current === a) this.current = null;
      }
    };
    requestAnimationFrame(step);
  }

  stop() {
    if (!this.current) return;
    try {
      this.current.pause();
      this.current.src = '';
    } catch {
      /* ignore */
    }
    this.current = null;
  }
}
