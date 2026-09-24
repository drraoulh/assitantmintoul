import { API_BASE_URL } from '../constants/config';

export type VoiceServerEvent =
  | { type: 'ready'; message?: string; events?: string[] }
  | { type: 'pong' }
  | { type: 'status'; phase: string }
  | { type: 'transcript'; text: string; language?: string | null; latency_ms?: number }
  | { type: 'route'; kind: string; skip_kb?: boolean; skip_web?: boolean; reason?: string }
  | { type: 'token'; text: string }
  | { type: 'assistant_text'; text: string }
  | {
      type: 'audio_chunk';
      format?: string;
      index: number;
      sequence_id?: number;
      part?: number;
      data: string;
      text?: string;
      turn_id?: string;
    }
  | { type: 'audio_done'; index: number; sequence_id?: number; turn_id?: string }
  | {
      type: 'turn_done';
      metrics?: Record<string, unknown>;
      conversation_id?: string;
      turn_id?: string;
    }
  | { type: 'interrupted' }
  | {
      type: 'error';
      code?: string;
      message: string;
      recoverable?: boolean;
    };

function wsBaseUrl(): string {
  const http = API_BASE_URL.replace(/\/$/, '');
  if (http.startsWith('https://')) {
    return `wss://${http.slice('https://'.length)}`;
  }
  if (http.startsWith('http://')) {
    return `ws://${http.slice('http://'.length)}`;
  }
  return http;
}

export function voiceSessionUrl(): string {
  return `${wsBaseUrl()}/api/voice/session`;
}

export type VoiceSocketHandlers = {
  onEvent: (event: VoiceServerEvent) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
};

export class VoiceSocket {
  private socket: WebSocket | null = null;
  private handlers: VoiceSocketHandlers;

  constructor(handlers: VoiceSocketHandlers) {
    this.handlers = handlers;
  }

  get ready(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  connect(): void {
    if (this.socket && this.socket.readyState <= WebSocket.OPEN) {
      return;
    }
    const socket = new WebSocket(voiceSessionUrl());
    this.socket = socket;
    socket.onopen = () => this.handlers.onOpen?.();
    socket.onclose = () => this.handlers.onClose?.();
    socket.onerror = (error) => this.handlers.onError?.(error);
    socket.onmessage = (message) => {
      try {
        const payload = JSON.parse(String(message.data)) as VoiceServerEvent;
        this.handlers.onEvent(payload);
      } catch {
        // ignore malformed frames
      }
    };
  }

  close(): void {
    this.socket?.close();
    this.socket = null;
  }

  send(payload: Record<string, unknown>): void {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error('Voice socket is not connected');
    }
    this.socket.send(JSON.stringify(payload));
  }

  sendText(text: string, locale: 'fr' | 'en' = 'fr', turnId?: string): void {
    this.send({ type: 'text', text, locale, turn_id: turnId });
  }

  sendAudioBase64(
    audioBase64: string,
    mimeType = 'audio/m4a',
    locale: 'fr' | 'en' = 'fr',
    turnId?: string,
  ): void {
    this.send({
      type: 'audio',
      audio_base64: audioBase64,
      mime_type: mimeType,
      locale,
      turn_id: turnId,
    });
  }

  interrupt(): void {
    if (this.ready) {
      this.send({ type: 'interrupt' });
    }
  }
}

export async function uriToBase64(uri: string): Promise<string> {
  const response = await fetch(uri);
  const buffer = await response.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  // btoa is available on web; RN may need polyfill — Expo web is the jury target.
  if (typeof btoa === 'function') {
    return btoa(binary);
  }
  // Fallback for native without btoa
  const chars =
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  let output = '';
  for (let i = 0; i < bytes.length; i += 3) {
    const a = bytes[i];
    const b = bytes[i + 1];
    const c = bytes[i + 2];
    const bitmap = (a << 16) | ((b || 0) << 8) | (c || 0);
    output +=
      chars.charAt((bitmap >> 18) & 63) +
      chars.charAt((bitmap >> 12) & 63) +
      (Number.isNaN(b) ? '=' : chars.charAt((bitmap >> 6) & 63)) +
      (Number.isNaN(c) ? '=' : chars.charAt(bitmap & 63));
  }
  // Fix padding for last incomplete group
  const mod = bytes.length % 3;
  if (mod === 1) {
    output = `${output.slice(0, -2)}==`;
  } else if (mod === 2) {
    output = `${output.slice(0, -1)}=`;
  }
  return output;
}
