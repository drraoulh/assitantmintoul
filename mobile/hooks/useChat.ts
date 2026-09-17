import { useCallback, useEffect, useState } from 'react';

import { ApiError, fetchHealth, sendChatMessage } from '../services/api';
import type { BackendStatus, ChatMessage } from '../types/chat';

function createId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return 'Impossible de joindre le serveur. Vérifiez que FastAPI tourne sur le port 8000, puis réessayez.';
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [isSending, setIsSending] = useState(false);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('checking');

  const checkHealth = useCallback(async () => {
    try {
      await fetchHealth();
      setBackendStatus('online');
    } catch {
      setBackendStatus('offline');
    }
  }, []);

  useEffect(() => {
    void checkHealth();
  }, [checkHealth]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isSending) {
        return;
      }

      const userMessage: ChatMessage = {
        id: createId(),
        role: 'user',
        content: trimmed,
        createdAt: new Date().toISOString(),
      };

      setMessages((current) => [...current, userMessage]);
      setIsSending(true);

      try {
        const response = await sendChatMessage({
          message: trimmed,
          conversation_id: conversationId,
        });

        setConversationId(response.conversation_id);
        setBackendStatus('online');
        setMessages((current) => [
          ...current,
          {
            id: createId(),
            role: 'assistant',
            content: response.message,
            createdAt: new Date().toISOString(),
          },
        ]);
      } catch (error) {
        if (!(error instanceof ApiError)) {
          setBackendStatus('offline');
        }
        setMessages((current) => [
          ...current,
          {
            id: createId(),
            role: 'assistant',
            content: errorText(error),
            createdAt: new Date().toISOString(),
            isError: true,
          },
        ]);
      } finally {
        setIsSending(false);
      }
    },
    [conversationId, isSending],
  );

  return {
    messages,
    isSending,
    backendStatus,
    sendMessage,
    checkHealth,
  };
}
