/** Shared STT mime helpers — Expo web uses blob: URLs with no extension. */

import { Platform } from 'react-native';

export function mimeFromRecordingUri(uri: string | null | undefined): string {
  const lower = (uri ?? '').toLowerCase();

  // Expo web MediaRecorder records audio/webm; blob: URIs have no .webm suffix.
  if (Platform.OS === 'web' || lower.startsWith('blob:')) {
    if (lower.includes('.wav')) return 'audio/wav';
    if (lower.includes('.mp3')) return 'audio/mpeg';
    if (lower.includes('.m4a') || lower.includes('.mp4')) return 'audio/m4a';
    return 'audio/webm';
  }

  if (lower.includes('.webm')) return 'audio/webm';
  if (lower.includes('.wav')) return 'audio/wav';
  if (lower.includes('.mp3')) return 'audio/mpeg';
  if (lower.includes('.caf')) return 'audio/wav';
  if (lower.includes('.3gp')) return 'audio/3gpp';
  // Native HIGH_QUALITY is AAC in an m4a container.
  return 'audio/m4a';
}

export function extensionForAudioMime(mimeType: string, fallback = 'm4a'): string {
  const normalized = mimeType.toLowerCase().split(';')[0]?.trim() ?? '';
  const map: Record<string, string> = {
    'audio/mp4': 'm4a',
    'audio/m4a': 'm4a',
    'video/mp4': 'm4a',
    'audio/mpeg': 'mp3',
    'audio/mp3': 'mp3',
    'audio/wav': 'wav',
    'audio/webm': 'webm',
    'video/webm': 'webm',
    'audio/ogg': 'ogg',
    'audio/3gpp': '3gp',
  };
  return map[normalized] ?? fallback;
}
