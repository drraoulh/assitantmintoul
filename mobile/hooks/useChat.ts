import { useCallback, useEffect, useRef, useState } from 'react';

import { useLocale } from '../i18n';
import {
  ApiError,
  fetchConversation,
  fetchHealth,
  identifyImage,
  sendChatMessage,
  type ImageUploadInput,
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

/** Keep Render free tier warm (sleeps after ~15 min idle). */
const KEEP_ALIVE_MS = 3 * 60 * 1000;
/** Pause between wake attempts after the initial burst. */
const WAKE_RETRY_MS = 5_000;

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
    // Timeouts / 5xx while the free instance boots still mean "waking".
    if (error.status === 504 || error.status === 502 || error.status === 503) {
      return true;
    }
    return false;
  }
  const message = error instanceof Error ? error.message : String(error ?? '');
  return /failed to fetch|network request failed|load failed|networkerror|econnrefused|enotfound|aborted|timeout/i.test(
    message,
  );
}

async function sleep(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

export function useChat() {
  const { locale, t } = useLocale();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [isSending, setIsSending] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('checking');
  const healthGenRef = useRef(0);

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
    const gen = ++healthGenRef.current;
    const stillCurrent = () => gen === healthGenRef.current;

    setBackendStatus('checking');
    // Burst first: Render free cold-start is often 30–90s.
    const burstDelays = [0, 1500, 3000, 5000, 8000, 12000, 15000];
    for (let attempt = 0; attempt < burstDelays.length; attempt += 1) {
      if (!stillCurrent()) {
        return;
      }
      if (burstDelays[attempt] > 0) {
        await sleep(burstDelays[attempt]);
      }
      if (!stillCurrent()) {
        return;
      }
      if (attempt >= 1) {
        setBackendStatus('waking');
      }
      try {
        await fetchHealth();
        if (stillCurrent()) {
          setBackendStatus('online');
        }
        return;
      } catch {
        // keep trying while the free instance wakes up
      }
    }

    // Never stick on "Hors ligne" — keep waking until the API answers.
    if (stillCurrent()) {
      setBackendStatus('waking');
    }
    while (stillCurrent()) {
      await sleep(WAKE_RETRY_MS);
      if (!stillCurrent()) {
        return;
      }
      try {
        await fetchHealth();
        if (stillCurrent()) {
          setBackendStatus('online');
        }
        return;
      } catch {
        if (stillCurrent()) {
          setBackendStatus('waking');
        }
      }
    }
  }, []);

  const recoverConnection = useCallback(() => {
    setBackendStatus('waking');
    void checkHealth();
  }, [checkHealth]);

  useEffect(() => {
    void checkHealth();
  }, [checkHealth]);

  // Keep the free Render API warm while the tab stays open.
  useEffect(() => {
    const id = setInterval(() => {
      void fetchHealth()
        .then(() => setBackendStatus('online'))
        .catch(() => {
          setBackendStatus('waking');
          void checkHealth();
        });
    }, KEEP_ALIVE_MS);
    return () => clearInterval(id);
  }, [checkHealth]);

  // Re-probe when the jury tab comes back to the foreground.
  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }
    const onVisibility = () => {
      if (document.visibilityState !== 'visible') {
        return;
      }
      void fetchHealth()
        .then(() => setBackendStatus('online'))
        .catch(() => {
          setBackendStatus('waking');
          void checkHealth();
        });
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, [checkHealth]);

  const openConversation = useCallback(
    async (id: string) => {
      setIsLoadingHistory(true);
      try {
        const history = await fetchConversation(id);
        setMessages(toChatMessages(history.messages));
        setConversationId(history.conversation_id);
        setBackendStatus('online');
        return true;
      } catch (error) {
        if (isLikelyOffline(error)) {
          recoverConnection();
        }
        return false;
      } finally {
        setIsLoadingHistory(false);
      }
    },
    [recoverConnection],
  );

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
          recoverConnection();
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
    [conversationId, errorText, isSending, locale, recoverConnection],
  );

  const sendImage = useCallback(
    async (input: string | ImageUploadInput): Promise<string | null> => {
      const asset: ImageUploadInput =
        typeof input === 'string' ? { uri: input } : input;
      if (!asset.uri || isSending) {
        return null;
      }

      const userMessage: ChatMessage = {
        id: createId(),
        role: 'user',
        content: t('photoSent'),
        imageUri: asset.uri,
        createdAt: new Date().toISOString(),
      };

      setMessages((current) => [...current, userMessage]);
      setIsSending(true);

      try {
        const vision = await identifyImage(asset);
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
          recoverConnection();
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
    [conversationId, errorText, isSending, locale, recoverConnection, t],
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
