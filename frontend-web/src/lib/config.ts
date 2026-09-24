/** Public API base — never hardcode localhost in production builds. */
export function getApiBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '');
  if (fromEnv) {
    return fromEnv;
  }
  if (process.env.NODE_ENV === 'development') {
    return 'http://127.0.0.1:8000';
  }
  return 'https://cameroon-ai-tour-guide-api.onrender.com';
}

export const APP_NAME = 'SmartMboa';
export const APP_TAGLINE_FR = 'Votre guide intelligent pour découvrir le Cameroun';
export const APP_TAGLINE_EN = 'Your intelligent guide to discover Cameroon';

export const HEALTH_PROBE_TIMEOUT_MS = 20_000;
export const REQUEST_TIMEOUT_MS = 180_000;
export const KEEP_ALIVE_MS = 3 * 60 * 1000;
