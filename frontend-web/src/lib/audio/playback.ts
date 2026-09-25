/**
 * Shared browser audio playback for voice chunks + TTS blobs.
 * Supports stop/interrupt so the UI can cancel playback reliably.
 */

type Listener = (playing: boolean) => void;

class AudioPlaybackController {
  private queue: Blob[] = [];
  private current: HTMLAudioElement | null = null;
  private resolveCurrent: (() => void) | null = null;
  private pumping = false;
  private stopped = false;
  private listeners = new Set<Listener>();

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    listener(this.isPlaying());
    return () => this.listeners.delete(listener);
  }

  private emit() {
    const playing = this.isPlaying();
    for (const l of this.listeners) l(playing);
  }

  isPlaying(): boolean {
    return this.pumping || !!this.current;
  }

  enqueueBase64(b64: string, mime = 'audio/mpeg') {
    try {
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      this.enqueueBlob(new Blob([bytes], { type: mime }));
    } catch {
      /* ignore bad chunk */
    }
  }

  enqueueBlob(blob: Blob) {
    if (this.stopped) this.stopped = false;
    this.queue.push(blob);
    void this.pump();
  }

  /** Play a single blob immediately (clears queue). Used for TTS of a message. */
  async playExclusive(blob: Blob): Promise<void> {
    this.stop();
    this.stopped = false;
    this.queue = [blob];
    await this.pump();
  }

  stop() {
    this.stopped = true;
    this.queue = [];
    if (this.current) {
      try {
        this.current.pause();
        this.current.removeAttribute('src');
        this.current.load();
      } catch {
        /* ignore */
      }
      this.current = null;
    }
    const resolve = this.resolveCurrent;
    this.resolveCurrent = null;
    resolve?.();
    this.pumping = false;
    this.emit();
  }

  private async pump() {
    if (this.pumping) return;
    this.pumping = true;
    this.emit();
    while (this.queue.length && !this.stopped) {
      const blob = this.queue.shift()!;
      const url = URL.createObjectURL(blob);
      try {
        await new Promise<void>((resolve) => {
          if (this.stopped) {
            resolve();
            return;
          }
          const audio = new Audio(url);
          this.current = audio;
          this.resolveCurrent = resolve;
          const done = () => {
            if (this.resolveCurrent === resolve) this.resolveCurrent = null;
            resolve();
          };
          audio.onended = done;
          audio.onerror = done;
          void audio.play().catch(done);
        });
      } finally {
        URL.revokeObjectURL(url);
        this.current = null;
      }
    }
    this.pumping = false;
    this.emit();
  }
}

export const audioPlayback = new AudioPlaybackController();
