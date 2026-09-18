export type ChatRole = 'user' | 'assistant';

export interface ChatSource {
  title: string;
  city?: string | null;
  region?: string | null;
  category?: string | null;
  organization?: string | null;
  url?: string | null;
  image_url?: string | null;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;
  isError?: boolean;
  sources?: ChatSource[];
  imageUri?: string;
}

export type ChatMode = 'text' | 'voice';

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  mode?: ChatMode;
}

export interface ChatResponse {
  conversation_id: string;
  role: 'assistant';
  message: string;
  provider: string;
  sources?: ChatSource[];
}

export interface ConversationSummary {
  id: string;
  title: string;
  message_count: number;
  updated_at?: string | null;
}

export interface ConversationListResponse {
  items: ConversationSummary[];
  count: number;
  persistent: boolean;
}

export interface ConversationTurn {
  role: ChatRole;
  content: string;
  created_at?: string | null;
}

export interface ConversationHistoryResponse {
  conversation_id: string;
  messages: ConversationTurn[];
  count: number;
}

export interface HealthResponse {
  status: string;
  service: string;
}

export type BackendStatus = 'checking' | 'online' | 'offline';
