import { File, UploadType } from 'expo-file-system';
import { Platform } from 'react-native';

import { API_BASE_URL } from '../constants/config';
import type {
  ChatRequest,
  ChatResponse,
  ConversationHistoryResponse,
  ConversationListResponse,
  HealthResponse,
} from '../types/chat';
import type { TranscriptionResponse } from '../types/speech';
import type { VisionIdentifyResponse } from '../types/vision';

const REQUEST_TIMEOUT_MS = 180000;

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function readErrorDetail(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') {
    return null;
  }

  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim();
  }

  return null;
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      readErrorDetail(payload) ?? `HTTP ${response.status}`,
      response.status,
    );
  }
  return payload as T;
}

function parseJsonBody<T>(body: string, status: number): T {
  let payload: unknown = null;
  try {
    payload = body ? JSON.parse(body) : null;
  } catch {
    payload = null;
  }
  if (status < 200 || status >= 300) {
    throw new ApiError(readErrorDetail(payload) ?? `HTTP ${status}`, status);
  }
  return payload as T;
}

function extensionForMime(mimeType: string, fallback: string): string {
  const normalized = mimeType.toLowerCase().split(';')[0]?.trim() ?? '';
  const map: Record<string, string> = {
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
    'image/gif': 'gif',
    'image/heic': 'heic',
    'image/heif': 'heif',
    'audio/mp4': 'm4a',
    'audio/m4a': 'm4a',
    'audio/mpeg': 'mp3',
    'audio/mp3': 'mp3',
    'audio/wav': 'wav',
    'audio/webm': 'webm',
    'audio/ogg': 'ogg',
  };
  return map[normalized] ?? fallback;
}

async function uploadMultipart<T>(
  path: string,
  uri: string,
  mimeType: string,
  fileName: string,
  signal: AbortSignal,
): Promise<T> {
  // expo-file-system File.upload calls validatePath(), which is undefined on web
  // and crashes with "this.validatePath is not a function".
  if (Platform.OS === 'web') {
    const blobResponse = await fetch(uri, { signal });
    if (!blobResponse.ok) {
      throw new ApiError(
        `Impossible de lire le fichier local (HTTP ${blobResponse.status}).`,
        blobResponse.status,
      );
    }
    const blob = await blobResponse.blob();
    const form = new FormData();
    form.append('file', blob, fileName);

    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      signal,
      headers: {
        Accept: 'application/json',
      },
      body: form,
    });
    return parseJsonResponse<T>(response);
  }

  // Expo SDK 57 rejects React Native's { uri, name, type } FormData parts
  // ("Unsupported FormDataPart implementation"). File.upload is the supported path.
  const file = new File(uri);
  const result = await file.upload(`${API_BASE_URL}${path}`, {
    httpMethod: 'POST',
    uploadType: UploadType.MULTIPART,
    fieldName: 'file',
    mimeType,
    headers: {
      Accept: 'application/json',
    },
    signal,
  });
  return parseJsonBody<T>(result.body, result.status);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
    });
    return await parseJsonResponse<T>(response);
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError('La réponse a pris trop de temps. Réessayez.', 504);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health');
}

export function sendChatMessage(payload: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listConversations(
  limit = 30,
): Promise<ConversationListResponse> {
  return request<ConversationListResponse>(`/api/conversations?limit=${limit}`);
}

export function fetchConversation(
  conversationId: string,
): Promise<ConversationHistoryResponse> {
  return request<ConversationHistoryResponse>(
    `/api/conversations/${encodeURIComponent(conversationId)}`,
  );
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/conversations/${encodeURIComponent(conversationId)}`,
    { method: 'DELETE' },
  );
  if (!response.ok) {
    throw new ApiError(`HTTP ${response.status}`, response.status);
  }
}

export async function transcribeAudio(
  uri: string,
  mimeType = 'audio/mp4',
): Promise<TranscriptionResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const fileName = `audio.${extensionForMime(mimeType, 'm4a')}`;

  try {
    return await uploadMultipart<TranscriptionResponse>(
      '/api/speech/transcribe',
      uri,
      mimeType,
      fileName,
      controller.signal,
    );
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError('La transcription a pris trop de temps. Réessayez.', 504);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function synthesizeSpeech(text: string): Promise<ArrayBuffer> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}/api/speech/synthesize`, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        Accept: 'audio/mpeg',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text }),
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new ApiError(
        readErrorDetail(payload) ?? `HTTP ${response.status}`,
        response.status,
      );
    }

    return await response.arrayBuffer();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError('La synthèse vocale a pris trop de temps. Réessayez.', 504);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function identifyImage(
  uri: string,
  mimeType = 'image/jpeg',
): Promise<VisionIdentifyResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const fileName = `photo.${extensionForMime(mimeType, 'jpg')}`;

  try {
    return await uploadMultipart<VisionIdentifyResponse>(
      '/api/vision/identify',
      uri,
      mimeType,
      fileName,
      controller.signal,
    );
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError("L'analyse d'image a pris trop de temps. Réessayez.", 504);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}
