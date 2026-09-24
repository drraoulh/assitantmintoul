/**
 * Ordered early-play controller for voice WebSocket MP3 streams.
 *
 * Starts playback on the first bytes of sequence 0 (no audio_done wait).
 * Later sequences play strictly 0 → 1 → 2 … even if chunks arrive out of order.
 *
 * Web: MediaSource progressive append when available.
 * Fallback: play concatenated buffer as soon as the sequence is marked done
 * (still ordered); first sequence may also early-play a growing blob restart
 * only when MSE is unavailable and the first part alone is large enough.
 */

export type VoiceStreamMetrics = {
  frontend_audio_received_seq0?: number;
  frontend_play_start?: number;
  frontend_first_audio_played?: number;
  audio_done_received?: number;
  receive_to_play_start_ms?: number;
  play_start_to_audio_done_ms?: number;
  time_to_first_play_ms?: number;
};

export type SeqState = {
  parts: Uint8Array[];
  done: boolean;
  started: boolean;
};

export type PlayAction =
  | { type: 'start'; index: number; bytes: Uint8Array; progressive: boolean }
  | { type: 'append'; index: number; bytes: Uint8Array }
  | { type: 'end'; index: number }
  | { type: 'none' };

/** Minimum bytes before non-MSE early start (single first Fish chunk is ~4KB). */
export const MIN_EARLY_PLAY_BYTES = 2048;

export function concatParts(parts: Uint8Array[]): Uint8Array {
  let total = 0;
  for (const p of parts) {
    total += p.byteLength;
  }
  const out = new Uint8Array(total);
  let offset = 0;
  for (const p of parts) {
    out.set(p, offset);
    offset += p.byteLength;
  }
  return out;
}

/**
 * Pure scheduler: decides when to start / append / end given chunk arrival order.
 */
export class OrderedVoiceScheduler {
  readonly sequences = new Map<number, SeqState>();
  nextPlayIndex = 0;
  hasStartedPlayback = false;
  currentPlaying: number | null = null;
  /** When true, start as soon as first chunk of next index is buffered. */
  readonly preferEarlyPlay: boolean;

  constructor(preferEarlyPlay = true) {
    this.preferEarlyPlay = preferEarlyPlay;
  }

  reset(): void {
    this.sequences.clear();
    this.nextPlayIndex = 0;
    this.hasStartedPlayback = false;
    this.currentPlaying = null;
  }

  private ensure(index: number): SeqState {
    let state = this.sequences.get(index);
    if (!state) {
      state = { parts: [], done: false, started: false };
      this.sequences.set(index, state);
    }
    return state;
  }

  onChunk(index: number, bytes: Uint8Array, progressiveCapable: boolean): PlayAction {
    if (bytes.byteLength === 0) {
      return { type: 'none' };
    }
    const state = this.ensure(index);
    state.parts.push(bytes);

    // Append into the sequence already playing (progressive MSE).
    if (this.currentPlaying === index && state.started && progressiveCapable) {
      return { type: 'append', index, bytes };
    }

    return this.tryStart(index, progressiveCapable);
  }

  onDone(index: number, progressiveCapable: boolean): PlayAction {
    const state = this.ensure(index);
    state.done = true;

    if (this.currentPlaying === index && state.started && progressiveCapable) {
      return { type: 'end', index };
    }

    // Non-progressive: start now that the sequence is complete (ordered).
    if (!state.started && !progressiveCapable) {
      return this.tryStart(index, false);
    }

    // Progressive already playing: end signal only.
    if (state.started) {
      return { type: 'end', index };
    }

    return this.tryStart(index, progressiveCapable);
  }

  /** Call when playback of `index` fully finished so the next sequence can start. */
  onPlaybackFinished(index: number, progressiveCapable: boolean): PlayAction {
    if (this.currentPlaying === index) {
      this.currentPlaying = null;
    }
    this.sequences.delete(index);
    if (this.nextPlayIndex === index) {
      this.nextPlayIndex = index + 1;
    } else if (this.nextPlayIndex < index + 1) {
      this.nextPlayIndex = index + 1;
    }
    return this.tryStart(this.nextPlayIndex, progressiveCapable);
  }

  private tryStart(index: number, progressiveCapable: boolean): PlayAction {
    if (this.currentPlaying != null) {
      return { type: 'none' };
    }
    if (index !== this.nextPlayIndex) {
      return { type: 'none' };
    }
    const state = this.sequences.get(index);
    if (!state || state.started) {
      return { type: 'none' };
    }

    const total = state.parts.reduce((n, p) => n + p.byteLength, 0);
    const canEarly =
      this.preferEarlyPlay &&
      total >= MIN_EARLY_PLAY_BYTES &&
      state.parts.length > 0;
    const canComplete = state.done && total > 0;

    if (progressiveCapable && canEarly) {
      state.started = true;
      this.hasStartedPlayback = true;
      this.currentPlaying = index;
      return {
        type: 'start',
        index,
        bytes: concatParts(state.parts),
        progressive: true,
      };
    }

    if (!progressiveCapable && canComplete) {
      state.started = true;
      this.hasStartedPlayback = true;
      this.currentPlaying = index;
      return {
        type: 'start',
        index,
        bytes: concatParts(state.parts),
        progressive: false,
      };
    }

    // Non-MSE early: only start on first sequence with minimum bytes once,
    // accepting that further parts for this index must be ignored unless we
    // restart — prefer waiting for done when not progressive.
    if (!progressiveCapable && canEarly && state.done === false && index === 0) {
      // Still wait for done without MSE to avoid truncated MP3 — return none.
      return { type: 'none' };
    }

    return { type: 'none' };
  }
}

export function supportsMediaSourceMp3(): boolean {
  if (typeof MediaSource === 'undefined') {
    return false;
  }
  try {
    return (
      MediaSource.isTypeSupported('audio/mpeg') ||
      MediaSource.isTypeSupported('audio/mp4; codecs="mp3"')
    );
  } catch {
    return false;
  }
}

export function mimeForMediaSource(): string {
  if (typeof MediaSource !== 'undefined' && MediaSource.isTypeSupported('audio/mpeg')) {
    return 'audio/mpeg';
  }
  return 'audio/mp4; codecs="mp3"';
}
