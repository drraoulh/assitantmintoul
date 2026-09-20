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
import { extensionForAudioMime } from '../utils/audioMime';

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
  const imageMap: Record<string, string> = {
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
    'image/gif': 'gif',
    'image/heic': 'heic',
    'image/heif': 'heif',
  };
  if (normalized in imageMap) {
    return imageMap[normalized];
  }
  return extensionForAudioMime(mimeType, fallback);
}

async function uploadMultipart<T>(
  path: string,
  uri: string,
  mimeType: string,
  fileName: string,
  signal: AbortSignal,
  source?: Blob | null,
): Promise<T> {
  // expo-file-system File.upload calls validatePath(), which is undefined on web
  // and crashes with "this.validatePath is not a function".
  if (Platform.OS === 'web') {
    let blob: Blob;
    if (source) {
      blob = source;
    } else {
      // Safari often throws "Load failed" on some picker URIs — callers should
      // pass asset.file / base64 when possible.
      try {
        const blobResponse = await fetch(uri, { signal });
        if (!blobResponse.ok) {
          throw new ApiError(
            `Impossible de lire le fichier local (HTTP ${blobResponse.status}).`,
            blobResponse.status,
          );
        }
        blob = await blobResponse.blob();
      } catch (error) {
        if (error instanceof ApiError) {
          throw error;
        }
        const message =
          error instanceof Error ? error.message : String(error ?? '');
        if (/load failed|failed to fetch|networkerror/i.test(message)) {
          throw new ApiError(
            "Impossible de lire l'image. Réessayez depuis la galerie.",
            0,
          );
        }
        throw error;
      }
    }

    const browserFile =
      typeof globalThis.File !== 'undefined' && source instanceof globalThis.File
        ? source
        : null;
    const resolvedMime = (browserFile?.type || blob.type || mimeType || 'application/octet-stream')
      .split(';')[0]
      .trim();
    const resolvedName =
      browserFile?.name ||
      fileName ||
      `upload.${extensionForMime(resolvedMime, 'bin')}`;
    const typedBlob =
      blob.type === resolvedMime ? blob : new Blob([blob], { type: resolvedMime });
    const form = new FormData();
    form.append('file', typedBlob, resolvedName);

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

function blobFromBase64(base64: string, mimeType: string): Blob {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: mimeType });
}

export type ImageUploadInput = {
  uri: string;
  mimeType?: string;
  fileName?: string | null;
  /** Web-only browser File from expo-image-picker — avoids Safari "Load failed". */
  file?: Blob | null;
  base64?: string | null;
};

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
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/conversations/${encodeURIComponent(conversationId)}`,
      {
        method: 'DELETE',
        signal: controller.signal,
        headers: {
          Accept: 'application/json',
        },
      },
    );
    // 204 No Content is success; some proxies also return 200.
    if (!response.ok && response.status !== 204) {
      const payload = await response.json().catch(() => null);
      throw new ApiError(
        readErrorDetail(payload) ?? `HTTP ${response.status}`,
        response.status,
      );
    }
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError('La suppression a pris trop de temps. Réessayez.', 504);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function transcribeAudio(
  uri: string,
  mimeType = 'audio/mp4',
): Promise<TranscriptionResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const fileName = `audio.${extensionForAudioMime(mimeType, 'm4a')}`;

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
  input: string | ImageUploadInput,
  mimeType = 'image/jpeg',
): Promise<VisionIdentifyResponse> {
  const asset: ImageUploadInput =
    typeof input === 'string' ? { uri: input, mimeType } : input;
  const resolvedMime =
    asset.mimeType ||
    asset.file?.type ||
    mimeType ||
    'image/jpeg';
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const fileName =
    asset.fileName?.trim() ||
    `photo.${extensionForMime(resolvedMime, 'jpg')}`;

  let source: Blob | null = asset.file ?? null;
  if (!source && asset.base64) {
    source = blobFromBase64(asset.base64, resolvedMime);
  }

  try {
    return await uploadMultipart<VisionIdentifyResponse>(
      '/api/vision/identify',
      asset.uri,
      resolvedMime,
      fileName,
      controller.signal,
      source,
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
