import { File, UploadType } from 'expo-file-system';

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

  try {
    // Expo SDK 57 rejects React Native's { uri, name, type } FormData parts
    // ("Unsupported FormDataPart implementation"). File.upload is the supported path.
    const file = new File(uri);
    const result = await file.upload(`${API_BASE_URL}/api/speech/transcribe`, {
      httpMethod: 'POST',
      uploadType: UploadType.MULTIPART,
      fieldName: 'file',
      mimeType,
      headers: {
        Accept: 'application/json',
      },
      signal: controller.signal,
    });
    return parseJsonBody<TranscriptionResponse>(result.body, result.status);
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

  try {
    const file = new File(uri);
    const result = await file.upload(`${API_BASE_URL}/api/vision/identify`, {
      httpMethod: 'POST',
      uploadType: UploadType.MULTIPART,
      fieldName: 'file',
      mimeType,
      headers: {
        Accept: 'application/json',
      },
      signal: controller.signal,
    });
    return parseJsonBody<VisionIdentifyResponse>(result.body, result.status);
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
