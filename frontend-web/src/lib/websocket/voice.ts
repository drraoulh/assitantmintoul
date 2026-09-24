import { getApiBaseUrl, getVoiceWebSocketUrl } from '../config';

export type VoiceServerEvent =
  | { type: 'ready' }
  | { type: 'pong' }
  | { type: 'status'; phase?: string; message?: string }
  | { type: 'transcript'; text: string }
  | { type: 'route'; intent?: string }
  | { type: 'token'; text: string }
  | { type: 'assistant_text'; text: string }
  | { type: 'audio_chunk'; data: string; mime?: string }
  | { type: 'audio_done' }
  | { type: 'turn_done'; ui?: Record<string, unknown> }
  | { type: 'interrupted' }
  | { type: 'error'; message?: string };

export function voiceSessionUrl(): string {
  return getVoiceWebSocketUrl();
}

export class VoiceSocket {
  private socket: WebSocket | null = null;
  private onEvent: ((event: VoiceServerEvent) => void) | null = null;

  connect(onEvent: (event: VoiceServerEvent) => void): Promise<void> {
    this.onEvent = onEvent;
    return new Promise((resolve, reject) => {
      const socket = new WebSocket(voiceSessionUrl());
      this.socket = socket;
      socket.onopen = () => resolve();
      socket.onerror = () => reject(new Error('WebSocket connection failed'));
      socket.onmessage = (msg) => {
        try {
          const data = JSON.parse(String(msg.data)) as VoiceServerEvent;
          this.onEvent?.(data);
        } catch {
          // ignore malformed
        }
      };
      socket.onclose = () => {
        this.socket = null;
      };
    });
  }

  send(payload: Record<string, unknown>): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  sendText(text: string, locale: 'fr' | 'en' = 'fr'): void {
    this.send({ type: 'text', text, locale });
  }

  sendAudioBase64(audio: string, mime = 'audio/webm'): void {
    this.send({ type: 'audio', data: audio, mime });
  }

  interrupt(): void {
    this.send({ type: 'interrupt' });
  }

  close(): void {
    try {
      this.send({ type: 'close' });
    } catch {
      // ignore
    }
    this.socket?.close();
    this.socket = null;
  }
}

export async function blobToBase64(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i += 32768) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 32768));
  }
  return btoa(binary);
}

export { getApiBaseUrl, getVoiceWebSocketUrl };
