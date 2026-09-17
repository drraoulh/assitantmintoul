import { API_BASE_URL } from '../constants/config';
import type { ChatRequest, ChatResponse, HealthResponse } from '../types/chat';

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

    const payload = await response.json().catch(() => null);

    if (!response.ok) {
      throw new ApiError(
        readErrorDetail(payload) ?? `HTTP ${response.status}`,
        response.status,
      );
    }

    return payload as T;
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
