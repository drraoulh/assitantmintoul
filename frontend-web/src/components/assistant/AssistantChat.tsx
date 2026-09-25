'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import {
  Camera,
  Mic,
  SendHorizontal,
  Sparkles,
  Square,
  Volume2,
} from 'lucide-react';

import { ResponseRenderer } from '@/components/assistant/ResponseRenderer';
import {
  VoiceMode,
  type VoiceExchange,
} from '@/components/assistant/VoiceMode';
import { Button, ErrorState, Input, ThinkingDots } from '@/components/ui';
import { friendlyError, sendChatMessage, synthesizeSpeech } from '@/lib/api/client';
import { audioPlayback } from '@/lib/audio/playback';
import { useLocale } from '@/lib/i18n';
import { structuredFromChatResponse } from '@/lib/utils/response';
import type { StructuredChatUI } from '@/lib/types';

interface Msg {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  ui?: StructuredChatUI | null;
  isError?: boolean;
  isTip?: boolean;
  streaming?: boolean;
}

const SUGGESTIONS = [
  { label: '📍 Lieux près de moi', q: 'Je suis à Bafoussam et je veux visiter un site touristique.' },
  { label: '🗺️ Planifier un voyage', q: 'Propose un itinéraire de 3 jours à Limbé.' },
  { label: '🏛️ Découvrir la culture', q: 'Parle-moi de la culture et des chefferies au Cameroun.' },
  { label: '🌿 Explorer la nature', q: 'Quels parcs naturels vérifiés recommandez-vous ?' },
  { label: '🍲 Découvrir la gastronomie', q: "C'est quoi la nourriture traditionnelle au Sud-Ouest ?" },
  { label: '🏨 Trouver un hôtel', q: 'Propose un hôtel vérifié à Douala.' },
] as const;

export function AssistantChat({
  initialQuestion,
  autoVoice,
}: {
  initialQuestion?: string;
  autoVoice?: boolean;
}) {
  const { t, locale } = useLocale();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [conversationId, setConversationId] = useState<string>();
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [speakingMsgId, setSpeakingMsgId] = useState<string | null>(null);
  const [audioPlaying, setAudioPlaying] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const ttsAbortRef = useRef<AbortController | null>(null);
  const streamAssistantIdRef = useRef<string | null>(null);

  useEffect(() => {
    return audioPlayback.subscribe(setAudioPlaying);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  const stopAllAudio = useCallback(() => {
    ttsAbortRef.current?.abort();
    ttsAbortRef.current = null;
    audioPlayback.stop();
    setSpeakingMsgId(null);
  }, []);

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending || voiceOpen) return;
    stopAllAudio();
    setSending(true);
    setMessages((m) => [
      ...m,
      { id: `${Date.now()}-u`, role: 'user', content: trimmed },
    ]);
    setInput('');
    try {
      const res = await sendChatMessage({
        message: trimmed,
        conversation_id: conversationId,
        locale,
      });
      setConversationId(res.conversation_id);
      setMessages((m) => [
        ...m,
        {
          id: `${Date.now()}-a`,
          role: 'assistant',
          content: res.message || res.text || '',
          ui: structuredFromChatResponse(res),
        },
      ]);
    } catch (error) {
      setMessages((m) => [
        ...m,
        {
          id: `${Date.now()}-e`,
          role: 'assistant',
          content: friendlyError(error),
          isError: true,
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  useEffect(() => {
    if (started.current) return;
    if (autoVoice) {
      started.current = true;
      setVoiceOpen(true);
      return;
    }
    if (initialQuestion) {
      started.current = true;
      void ask(initialQuestion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuestion, autoVoice]);

  const handleVoiceExchange = useCallback((ex: VoiceExchange) => {
    if (ex.conversationId) setConversationId(ex.conversationId);

    if (ex.userText) {
      setMessages((m) => [
        ...m,
        { id: `${Date.now()}-vu`, role: 'user', content: ex.userText! },
      ]);
    }

    if (ex.assistantText || ex.ui) {
      setMessages((m) => {
        const sid = streamAssistantIdRef.current;
        if (sid) {
          streamAssistantIdRef.current = null;
          return m.map((msg) =>
            msg.id === sid
              ? {
                  ...msg,
                  content: ex.assistantText || msg.content,
                  ui: ex.ui ?? msg.ui,
                  streaming: false,
                }
              : msg,
          );
        }
        return [
          ...m,
          {
            id: `${Date.now()}-va`,
            role: 'assistant',
            content: ex.assistantText || '',
            ui: ex.ui ?? undefined,
          },
        ];
      });
    }

    if (ex.tip) {
      setMessages((m) => [
        ...m,
        {
          id: `${Date.now()}-tip`,
          role: 'assistant',
          content: ex.tip!,
          isTip: true,
        },
      ]);
    }

    if (ex.error) {
      setMessages((m) => [
        ...m,
        {
          id: `${Date.now()}-ve`,
          role: 'assistant',
          content: ex.error!,
          isError: true,
        },
      ]);
    }
  }, []);

  async function speakMessage(msg: Msg) {
    const text = msg.content?.trim();
    if (!text || msg.isError || msg.isTip) return;

    if (speakingMsgId === msg.id) {
      stopAllAudio();
      return;
    }

    stopAllAudio();
    setSpeakingMsgId(msg.id);
    const abort = new AbortController();
    ttsAbortRef.current = abort;

    try {
      const blob = await synthesizeSpeech(text, { signal: abort.signal });
      if (abort.signal.aborted) return;
      await audioPlayback.playExclusive(blob);
    } catch (error) {
      if (abort.signal.aborted) return;
      setMessages((m) => [
        ...m,
        {
          id: `${Date.now()}-tts`,
          role: 'assistant',
          content: friendlyError(error),
          isError: true,
        },
      ]);
    } finally {
      if (ttsAbortRef.current === abort) ttsAbortRef.current = null;
      setSpeakingMsgId((id) => (id === msg.id ? null : id));
    }
  }

  useEffect(() => {
    return () => {
      stopAllAudio();
    };
  }, [stopAllAudio]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(input);
  }

  function openVoice() {
    stopAllAudio();
    setVoiceOpen(true);
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-[var(--ivory)]">
      <header className="shrink-0 border-b border-[var(--line)] bg-white/90 px-4 py-3 backdrop-blur-md md:px-6">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--green-deep)] text-white">
            <Sparkles className="h-4 w-4" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-lg font-bold text-[var(--green-deep)] md:text-xl">
              {t('assistant.title')}
            </h1>
            <p className="truncate text-xs text-[var(--muted)] md:text-sm">
              Votre guide intelligent pour découvrir le Cameroun.
            </p>
          </div>
          {(audioPlaying || speakingMsgId) && (
            <button
              type="button"
              onClick={stopAllAudio}
              className="inline-flex items-center gap-1.5 rounded-full bg-[var(--danger)] px-3 py-1.5 text-xs font-semibold text-white"
              aria-label="Arrêter la lecture"
            >
              <Square className="h-3.5 w-3.5 fill-current" aria-hidden />
              Stop
            </button>
          )}
          <button
            type="button"
            onClick={openVoice}
            className="inline-flex items-center gap-1.5 rounded-full bg-[var(--green-deep)] px-3 py-1.5 text-xs font-semibold text-white"
            aria-label="Ouvrir le mode vocal"
          >
            <Mic className="h-3.5 w-3.5" aria-hidden />
            Vocal
          </button>
        </div>
      </header>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain px-4 py-4 md:px-6">
        {messages.length === 0 && !sending ? (
          <div className="mx-auto max-w-lg py-6 text-center">
            <p className="font-display text-2xl font-semibold text-[var(--green-deep)]">
              Bonjour
            </p>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Je suis SmartMboa, votre guide intelligent pour découvrir le Cameroun.
            </p>
            <button
              type="button"
              onClick={openVoice}
              className="mt-5 inline-flex items-center gap-2 rounded-full bg-[var(--green-deep)] px-5 py-3 text-sm font-semibold text-white shadow-[var(--shadow-soft)] transition hover:bg-[var(--green)]"
            >
              <Mic className="h-4 w-4" aria-hidden />
              Parler au guide
            </button>
            <div className="mt-6 flex gap-2 overflow-x-auto pb-2 no-scrollbar md:flex-wrap md:justify-center md:overflow-visible">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.label}
                  type="button"
                  onClick={() => void ask(s.q)}
                  className="shrink-0 rounded-full border border-[var(--line)] bg-white px-3.5 py-2 text-left text-xs text-[var(--ink)] transition hover:border-[var(--gold)] hover:bg-[var(--mint-soft)]"
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={
              msg.role === 'user'
                ? 'ml-auto max-w-[90%] md:max-w-[75%]'
                : 'mr-auto w-full max-w-[98%] md:max-w-[92%]'
            }
          >
            <div className="mb-1 flex items-center gap-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">
                {msg.role === 'user' ? t('assistant.you') : t('assistant.bot')}
                {msg.streaming ? ' · …' : ''}
              </p>
              {msg.role === 'assistant' &&
              !msg.isError &&
              !msg.isTip &&
              msg.content.trim() ? (
                <button
                  type="button"
                  onClick={() => void speakMessage(msg)}
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold transition ${
                    speakingMsgId === msg.id
                      ? 'bg-[var(--danger)] text-white'
                      : 'bg-[var(--mint-soft)] text-[var(--green-deep)] hover:bg-[var(--line)]'
                  }`}
                  aria-label={
                    speakingMsgId === msg.id
                      ? 'Arrêter la lecture'
                      : 'Lire la réponse'
                  }
                >
                  {speakingMsgId === msg.id ? (
                    <>
                      <Square className="h-3 w-3 fill-current" aria-hidden />
                      Stop
                    </>
                  ) : (
                    <>
                      <Volume2 className="h-3.5 w-3.5" aria-hidden />
                      Lire
                    </>
                  )}
                </button>
              ) : null}
            </div>
            {msg.isTip ? (
              <div className="rounded-2xl border border-[var(--line)] bg-[var(--mint-soft)]/60 px-4 py-3 text-sm text-[var(--green-deep)]">
                {msg.content}
              </div>
            ) : msg.role === 'assistant' && !msg.isError ? (
              <div className="rounded-2xl bg-white px-4 py-4 shadow-sm ring-1 ring-[var(--line)]">
                <ResponseRenderer text={msg.content} ui={msg.ui} />
              </div>
            ) : msg.isError ? (
              <ErrorState message={msg.content} />
            ) : (
              <div className="rounded-2xl bg-[var(--green-deep)] px-4 py-3 text-white">
                {msg.content}
              </div>
            )}
          </div>
        ))}

        {sending ? <ThinkingDots label="SmartMboa réfléchit…" /> : null}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={onSubmit}
        className="shrink-0 border-t border-[var(--line)] bg-white/95 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur-md md:p-4"
      >
        <div className="mx-auto flex max-w-4xl items-center gap-2">
          <button
            type="button"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--mint-soft)] text-[var(--green-deep)]"
            aria-label="Ouvrir la vision"
            onClick={() => fileRef.current?.click()}
            disabled={sending}
          >
            <Camera className="h-5 w-5" />
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.[0]) window.location.href = '/vision';
            }}
          />
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Posez votre question…"
            className="min-w-0 flex-1"
            aria-label="Message"
            disabled={sending}
          />

          <button
            type="button"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--green-deep)] text-white"
            aria-label="Ouvrir le mode vocal"
            disabled={sending}
            onClick={openVoice}
          >
            <Mic className="h-5 w-5" />
          </button>

          <Button
            type="submit"
            disabled={sending || !input.trim()}
            aria-label="Envoyer"
          >
            <SendHorizontal className="h-4 w-4" />
          </Button>
        </div>
      </form>

      <VoiceMode
        open={voiceOpen}
        onClose={() => setVoiceOpen(false)}
        conversationId={conversationId}
        onExchange={handleVoiceExchange}
      />
    </div>
  );
}

export function AssistantPageClient({
  initialQuestion,
  autoVoice,
}: {
  initialQuestion?: string;
  autoVoice?: boolean;
}) {
  return <AssistantChat initialQuestion={initialQuestion} autoVoice={autoVoice} />;
}
