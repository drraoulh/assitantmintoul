export type ChatRole = 'user' | 'assistant';

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;
  isError?: boolean;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

export interface ChatResponse {
  conversation_id: string;
  role: 'assistant';
  message: string;
  provider: string;
}

export interface HealthResponse {
  status: string;
  service: string;
}

export type BackendStatus = 'checking' | 'online' | 'offline';
