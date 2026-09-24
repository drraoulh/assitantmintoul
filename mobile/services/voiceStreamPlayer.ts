/**
 * Web MediaSource progressive MP3 player for one voice sequence at a time.
 * Falls back to blob URL play of a complete buffer when MSE is unavailable.
 */

import { Platform } from 'react-native';

import {
  mimeForMediaSource,
  supportsMediaSourceMp3,
} from './voiceEarlyPlayback';

export type StreamPlayerHooks = {
  onPlayStart?: (index: number) => void;
  onFirstAudible?: (index: number) => void;
  onEnded?: (index: number) => void;
  onError?: (index: number, error: unknown) => void;
};

export class ProgressiveMp3Player {
  private element: HTMLAudioElement | null = null;
  private mediaSource: MediaSource | null = null;
  private sourceBuffer: SourceBuffer | null = null;
  private objectUrl: string | null = null;
  private pending: Uint8Array[] = [];
  private endWhenIdle = false;
  private index = -1;
  private hooks: StreamPlayerHooks;
  private opened = false;
  private playLogged = false;
  private audibleLogged = false;
  readonly progressive: boolean;

  constructor(hooks: StreamPlayerHooks = {}) {
    this.hooks = hooks;
    this.progressive = Platform.OS === 'web' && supportsMediaSourceMp3();
  }

  async start(index: number, initial: Uint8Array, progressive: boolean): Promise<void> {
    this.resetMedia();
    this.index = index;
    this.playLogged = false;
    this.audibleLogged = false;
    this.endWhenIdle = false;
    this.pending = [];

    if (Platform.OS !== 'web') {
      throw new Error('ProgressiveMp3Player is web-only');
    }

    const AudioCtor = (globalThis as { Audio?: typeof Audio }).Audio;
    if (!AudioCtor) {
      throw new Error('Audio non disponible');
    }
    this.element = new AudioCtor();
    this.element.preload = 'auto';

    const useProgressive = progressive && this.progressive;
    if (useProgressive) {
      await this.startMse(initial);
    } else {
      await this.startBlob(initial);
    }
  }

  append(bytes: Uint8Array): void {
    if (!bytes.byteLength || !this.progressive || !this.mediaSource) {
      return;
    }
    if (!this.sourceBuffer || this.sourceBuffer.updating || !this.opened) {
      this.pending.push(bytes);
      return;
    }
    try {
      this.sourceBuffer.appendBuffer(bytes.slice().buffer as ArrayBuffer);
    } catch {
      this.pending.push(bytes);
    }
  }

  end(): void {
    this.endWhenIdle = true;
    this.flushEnd();
  }

  stop(): void {
    this.resetMedia();
  }

  private async startMse(initial: Uint8Array): Promise<void> {
    const mediaSource = new MediaSource();
    this.mediaSource = mediaSource;
    this.objectUrl = URL.createObjectURL(mediaSource);
    this.element!.src = this.objectUrl;

    await new Promise<void>((resolve, reject) => {
      const onOpen = () => {
        mediaSource.removeEventListener('sourceopen', onOpen);
        try {
          const sb = mediaSource.addSourceBuffer(mimeForMediaSource());
          this.sourceBuffer = sb;
          this.opened = true;
          sb.addEventListener('updateend', () => {
            this.drainPending();
            this.flushEnd();
          });
          sb.appendBuffer(initial.slice().buffer as ArrayBuffer);
          resolve();
        } catch (error) {
          reject(error);
        }
      };
      mediaSource.addEventListener('sourceopen', onOpen);
    });

    this.wireElementEvents();
    await this.safePlay();
  }

  private async startBlob(initial: Uint8Array): Promise<void> {
    const copy = Uint8Array.from(initial);
    const blob = new Blob([copy.buffer], { type: 'audio/mpeg' });
    this.objectUrl = URL.createObjectURL(blob);
    this.element!.src = this.objectUrl;
    this.wireElementEvents();
    await this.safePlay();
  }

  private wireElementEvents(): void {
    const el = this.element;
    if (!el) {
      return;
    }
    el.onplaying = () => {
      if (!this.audibleLogged) {
        this.audibleLogged = true;
        this.hooks.onFirstAudible?.(this.index);
      }
    };
    el.onended = () => {
      this.hooks.onEnded?.(this.index);
      this.resetMedia();
    };
    el.onerror = () => {
      this.hooks.onError?.(this.index, new Error('Lecture audio impossible'));
      this.hooks.onEnded?.(this.index);
      this.resetMedia();
    };
  }

  private async safePlay(): Promise<void> {
    const el = this.element;
    if (!el) {
      return;
    }
    if (!this.playLogged) {
      this.playLogged = true;
      this.hooks.onPlayStart?.(this.index);
    }
    try {
      await el.play();
      if (!this.audibleLogged) {
        this.audibleLogged = true;
        this.hooks.onFirstAudible?.(this.index);
      }
    } catch {
      // Autoplay may fail; unlock path is handled by the parent hook.
    }
  }

  private drainPending(): void {
    const sb = this.sourceBuffer;
    if (!sb || sb.updating || this.pending.length === 0) {
      return;
    }
    const next = this.pending.shift();
    if (!next) {
      return;
    }
    try {
      sb.appendBuffer(next.slice().buffer as ArrayBuffer);
    } catch {
      this.pending.unshift(next);
    }
  }

  private flushEnd(): void {
    if (!this.endWhenIdle || !this.mediaSource) {
      return;
    }
    if (this.pending.length > 0) {
      this.drainPending();
      return;
    }
    const sb = this.sourceBuffer;
    if (sb?.updating) {
      return;
    }
    if (this.mediaSource.readyState === 'open') {
      try {
        this.mediaSource.endOfStream();
      } catch {
        // ignore double-end
      }
    }
  }

  private resetMedia(): void {
    if (this.element) {
      try {
        this.element.pause();
        this.element.onplaying = null;
        this.element.onended = null;
        this.element.onerror = null;
        this.element.removeAttribute('src');
        this.element.load();
      } catch {
        // ignore
      }
    }
    this.element = null;
    this.sourceBuffer = null;
    if (this.mediaSource && this.mediaSource.readyState === 'open') {
      try {
        this.mediaSource.endOfStream();
      } catch {
        // ignore
      }
    }
    this.mediaSource = null;
    if (this.objectUrl) {
      URL.revokeObjectURL(this.objectUrl);
      this.objectUrl = null;
    }
    this.pending = [];
    this.opened = false;
    this.endWhenIdle = false;
  }
}
