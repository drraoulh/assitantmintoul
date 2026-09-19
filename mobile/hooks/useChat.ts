import { useCallback, useEffect, useState } from 'react';

import { useLocale } from '../i18n';
import {
  ApiError,
  fetchConversation,
  fetchHealth,
  identifyImage,
  sendChatMessage,
} from '../services/api';
import {
  clearLastConversationId,
  loadLastConversationId,
  saveLastConversationId,
} from '../services/storage';
import type {
  BackendStatus,
  ChatMessage,
  ChatMode,
  ConversationTurn,
} from '../types/chat';

function createId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function toChatMessages(turns: ConversationTurn[]): ChatMessage[] {
  return turns.map((turn, index) => ({
    id: `history-${index}-${turn.created_at ?? index}`,
    role: turn.role,
    content: turn.content,
    createdAt: turn.created_at ?? new Date().toISOString(),
  }));
}

function isLikelyOffline(error: unknown): boolean {
  if (error instanceof ApiError) {
    return false;
  }
  const message = error instanceof Error ? error.message : String(error ?? '');
  return /failed to fetch|network request failed|load failed|networkerror|econnrefused|enotfound/i.test(
    message,
  );
}

async function sleep(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

function mimeFromUri(uri: string): string {
  const lower = uri.toLowerCase();
  if (lower.includes('.png')) return 'image/png';
  if (lower.includes('.webp')) return 'image/webp';
  if (lower.includes('.gif')) return 'image/gif';
  if (lower.includes('.heic') || lower.includes('.heif')) return 'image/heic';
  return 'image/jpeg';
}

export function useChat() {
  const { locale, t } = useLocale();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [isSending, setIsSending] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('checking');

  const errorText = useCallback(
    (error: unknown): string => {
      if (error instanceof ApiError) {
        return error.message;
      }
      if (error instanceof Error && error.message) {
        return error.message;
      }
      return t('error.server');
    },
    [t],
  );

  const checkHealth = useCallback(async () => {
    setBackendStatus('checking');
    // Render free tier can need a cold-start wake; retry before showing offline.
    const delays = [0, 2500, 5000];
    for (let attempt = 0; attempt < delays.length; attempt += 1) {
      if (delays[attempt] > 0) {
        await sleep(delays[attempt]);
      }
      try {
        await fetchHealth();
        setBackendStatus('online');
        return;
      } catch {
        // keep trying
      }
    }
    setBackendStatus('offline');
  }, []);

  useEffect(() => {
    void checkHealth();
  }, [checkHealth]);

  const openConversation = useCallback(async (id: string) => {
    setIsLoadingHistory(true);
    try {
      const history = await fetchConversation(id);
      setMessages(toChatMessages(history.messages));
      setConversationId(history.conversation_id);
      setBackendStatus('online');
      return true;
    } catch (error) {
      if (isLikelyOffline(error)) {
        setBackendStatus('offline');
      }
      return false;
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  const startNewConversation = useCallback(async () => {
    setMessages([]);
    setConversationId(undefined);
    await clearLastConversationId();
  }, []);

  useEffect(() => {
    if (conversationId) {
      void saveLastConversationId(conversationId);
    }
  }, [conversationId]);

  // Reopen the last thread on launch (server-side history, Supabase or memory).
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const storedId = await loadLastConversationId();
      if (!storedId || cancelled) {
        return;
      }
      await openConversation(storedId);
    })();
    return () => {
      cancelled = true;
    };
  }, [openConversation]);

  const sendMessage = useCallback(
    async (text: string, mode: ChatMode = 'text'): Promise<string | null> => {
      const trimmed = text.trim();
      if (!trimmed || isSending) {
        return null;
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
          mode,
          locale,
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
            sources: response.sources,
          },
        ]);
        return response.message;
      } catch (error) {
        if (isLikelyOffline(error)) {
          setBackendStatus('offline');
        }
        const message = errorText(error);
        setMessages((current) => [
          ...current,
          {
            id: createId(),
            role: 'assistant',
            content: message,
            createdAt: new Date().toISOString(),
            isError: true,
          },
        ]);
        return null;
      } finally {
        setIsSending(false);
      }
    },
    [conversationId, errorText, isSending, locale],
  );

  const sendImage = useCallback(
    async (uri: string): Promise<string | null> => {
      if (!uri || isSending) {
        return null;
      }

      const userMessage: ChatMessage = {
        id: createId(),
        role: 'user',
        content: t('photoSent'),
        imageUri: uri,
        createdAt: new Date().toISOString(),
      };

      setMessages((current) => [...current, userMessage]);
      setIsSending(true);

      try {
        const vision = await identifyImage(uri, mimeFromUri(uri));
        setBackendStatus('online');

        const guidePrompt = t('photo.guidePrompt').replace(
          '{{description}}',
          vision.description,
        );

        const response = await sendChatMessage({
          message: guidePrompt,
          conversation_id: conversationId,
          locale,
        });

        setConversationId(response.conversation_id);
        setMessages((current) => [
          ...current,
          {
            id: createId(),
            role: 'assistant',
            content: response.message,
            createdAt: new Date().toISOString(),
            sources: response.sources,
          },
        ]);
        return response.message;
      } catch (error) {
        if (isLikelyOffline(error)) {
          setBackendStatus('offline');
        }
        const message = errorText(error);
        setMessages((current) => [
          ...current,
          {
            id: createId(),
            role: 'assistant',
            content: message,
            createdAt: new Date().toISOString(),
            isError: true,
          },
        ]);
        return null;
      } finally {
        setIsSending(false);
      }
    },
    [conversationId, errorText, isSending, locale, t],
  );

  const appendExchange = useCallback((userText: string, assistantText: string) => {
    const now = new Date().toISOString();
    setMessages((current) => [
      ...current,
      {
        id: createId(),
        role: 'user',
        content: userText,
        createdAt: now,
      },
      {
        id: createId(),
        role: 'assistant',
        content: assistantText,
        createdAt: now,
      },
    ]);
    setBackendStatus('online');
  }, []);

  return {
    messages,
    conversationId,
    isSending,
    isLoadingHistory,
    backendStatus,
    sendMessage,
    sendImage,
    appendExchange,
    openConversation,
    startNewConversation,
    checkHealth,
  };
}
