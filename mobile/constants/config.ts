import Constants from 'expo-constants';
import { Platform } from 'react-native';

function lanHostFromExpo(): string | null {
  const hostUri = Constants.expoConfig?.hostUri ?? Constants.linkingUri;
  const ipMatch = String(hostUri ?? '').match(/(\d+\.\d+\.\d+\.\d+)/);
  if (ipMatch) {
    return ipMatch[1];
  }

  const hostname = Constants.expoConfig?.hostUri?.split(':')[0];
  if (hostname && hostname !== 'localhost' && hostname !== '127.0.0.1') {
    return hostname;
  }

  return null;
}

function resolveApiBaseUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL?.replace(/\/$/, '');
  if (fromEnv) {
    return fromEnv;
  }

  const lanHost = lanHostFromExpo();
  if (lanHost) {
    return `http://${lanHost}:8000`;
  }

  if (Platform.OS === 'android') {
    return 'http://10.0.2.2:8000';
  }

  return 'http://127.0.0.1:8000';
}

export const API_BASE_URL = resolveApiBaseUrl();
export const APP_NAME = 'Smartmboa Tour';
export const APP_TAGLINE = 'Découvrez le Cameroun autrement';
