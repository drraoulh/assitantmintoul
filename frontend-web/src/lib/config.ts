/** Public API + WebSocket URL helpers for SmartMboa Tour (Next.js). */

/**
 * REST API base URL.
 * - Prefer `NEXT_PUBLIC_API_URL` (set in production / .env.local).
 * - Dev fallback: local FastAPI.
 * - Production fallback without env: existing Render API (never invent domains).
 */
export function getApiBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '');
  if (fromEnv) {
    return fromEnv;
  }
  if (process.env.NODE_ENV === 'development') {
    return 'http://127.0.0.1:8000';
  }
  // Known production API from render.yaml — do not invent custom domains.
  return 'https://cameroon-ai-tour-guide-api.onrender.com';
}

/** @deprecated Prefer getApiBaseUrl(); kept for clarity at call sites. */
export const API_BASE_URL = getApiBaseUrl();

/**
 * Voice WebSocket URL derived from the HTTP API base.
 * https → wss, http → ws. Never use ws:// on an HTTPS page.
 */
export function getVoiceWebSocketUrl(): string {
  const http = getApiBaseUrl().replace(/\/$/, '');
  let wsRoot: string;
  if (http.startsWith('https://')) {
    wsRoot = `wss://${http.slice('https://'.length)}`;
  } else if (http.startsWith('http://')) {
    wsRoot = `ws://${http.slice('http://'.length)}`;
  } else {
    wsRoot = http;
  }
  return `${wsRoot}/api/voice/session`;
}

export const APP_NAME = 'SmartMboa Tour';
export const APP_TAGLINE_FR = 'Découvrez le Cameroun autrement';
export const APP_TAGLINE_EN = 'Discover Cameroon differently';

export const HEALTH_PROBE_TIMEOUT_MS = 20_000;
export const REQUEST_TIMEOUT_MS = 180_000;
export const KEEP_ALIVE_MS = 3 * 60 * 1000;
