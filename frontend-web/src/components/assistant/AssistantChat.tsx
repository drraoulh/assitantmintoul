'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import {
  Camera,
  Compass,
  Hotel,
  Landmark,
  MapPin,
  Mic,
  SendHorizontal,
  Square,
  Trees,
  Utensils,
  Volume2,
} from 'lucide-react';

import { ResponseRenderer } from '@/components/assistant/ResponseRenderer';
import { AssistantMark } from '@/components/brand/AssistantMark';
import {
  VoiceMode,
  type VoiceExchange,
} from '@/components/assistant/VoiceMode';
import { Button, ErrorState, Input, ThinkingDots } from '@/components/ui';
import { friendlyError, sendChatMessage, synthesizeSpeech } from '@/lib/api/client';
import { audioPlayback } from '@/lib/audio/playback';
import { speakOnDevice, splitForSpeech, stopDeviceSpeech } from '@/lib/audio/tts';
import { useLocale } from '@/lib/i18n';
import { answerLocalPhrase } from '@/lib/languages/local-phrase';
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
  /** Native local-language recording URL (Mbouda / Medumba). */
  phraseAudioUrl?: string | null;
  guideLine?: string | null;
}

const SUGGESTIONS = [
  { icon: MapPin, label: 'Lieux près de moi', q: 'Je suis à Bafoussam et je veux visiter un site touristique.' },
  { icon: Compass, label: 'Planifier un voyage', q: 'Propose un itinéraire de 3 jours à Limbé.' },
  { icon: Landmark, label: 'Parler local', q: 'How do you say good morning in Mbouda?' },
  { icon: Trees, label: 'Explorer la nature', q: 'Quels parcs naturels vérifiés recommandez-vous ?' },
  { icon: Utensils, label: 'Découvrir la gastronomie', q: "C'est quoi la nourriture traditionnelle au Sud-Ouest ?" },
  { icon: Hotel, label: 'Trouver un hôtel', q: 'Propose un hôtel vérifié à Douala.' },
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
    stopDeviceSpeech();
    audioPlayback.stop();
    setSpeakingMsgId(null);
  }, []);

  async function playLocalCoach(msg: Msg) {
    const guide = msg.guideLine?.trim() || msg.content.split('\n')[0]?.trim();
    const url = msg.phraseAudioUrl;
    if (!guide && !url) return;

    stopAllAudio();
    setSpeakingMsgId(msg.id);
    try {
      if (guide) {
        await speakOnDevice(guide, locale);
      }
      if (url) {
        audioPlayback.enqueueUrl(url);
        await audioPlayback.waitUntilIdle();
      }
    } finally {
      setSpeakingMsgId(null);
    }
  }

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
      const local = answerLocalPhrase(trimmed, locale === 'en' ? 'en' : 'fr');
      if (local) {
        const id = `${Date.now()}-a`;
        const msg: Msg = {
          id,
          role: 'assistant',
          content: local.answer,
          phraseAudioUrl: local.audioUrl,
          guideLine: local.guideLine,
        };
        setMessages((m) => [...m, msg]);
        setSending(false);
        void playLocalCoach(msg);
        return;
      }

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

    if (msg.phraseAudioUrl || msg.guideLine) {
      await playLocalCoach(msg);
      return;
    }

    stopAllAudio();
    setSpeakingMsgId(msg.id);
    const abort = new AbortController();
    ttsAbortRef.current = abort;

    try {
      const segments = splitForSpeech(text);
      let usedServer = false;
      for (const segment of segments) {
        if (abort.signal.aborted) return;
        try {
          const blob = await synthesizeSpeech(segment, { signal: abort.signal });
          if (abort.signal.aborted) return;
          if (!usedServer) {
            audioPlayback.stop();
            usedServer = true;
          }
          audioPlayback.enqueueBlob(blob);
        } catch (error) {
          if (abort.signal.aborted) return;
          if (usedServer) throw error;
          await speakOnDevice(text, locale);
          return;
        }
      }
      if (usedServer) await audioPlayback.waitUntilIdle();
    } catch (error) {
      if (abort.signal.aborted) return;
      try {
        await speakOnDevice(text, locale);
        return;
      } catch {
        /* fall through */
      }
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
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-gray-100">
      <header className="shrink-0 border-b border-gray-200 bg-white px-4 py-3 md:px-6">
        <div className="mx-auto flex max-w-5xl items-center gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-lg font-bold text-[#007A5E] md:text-xl">
              {t('assistant.title')}
            </h1>
            <p className="truncate text-xs text-[#535557] md:text-sm">
              Votre guide intelligent pour découvrir le Cameroun.
            </p>
          </div>
          {(audioPlaying || speakingMsgId) && (
            <button
              type="button"
              onClick={stopAllAudio}
              className="inline-flex items-center gap-1.5 rounded-full bg-[#CE1126] px-4 py-2 text-xs font-semibold text-white"
              aria-label="Arrêter la lecture"
            >
              <Square className="h-3.5 w-3.5 fill-current" aria-hidden />
              Stop
            </button>
          )}
          <button
            type="button"
            onClick={openVoice}
            className="inline-flex items-center gap-1.5 rounded-full bg-[#007A5E] px-4 py-2 text-xs font-semibold text-white shadow-md hover:bg-[#00614b]"
            aria-label="Ouvrir le mode vocal"
          >
            <Mic className="h-3.5 w-3.5" aria-hidden />
            Vocal
          </button>
        </div>
      </header>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain px-4 py-6 md:px-6">
        {messages.length === 0 && !sending ? (
          <div className="mx-auto max-w-5xl">
            <div className="text-center">
              <AssistantMark size="lg" className="mx-auto" />
              <p className="mt-5 text-3xl font-bold tracking-tight text-black md:text-4xl">
                Posez votre question sur le{' '}
                <span className="text-[#CE1126]">Cameroun</span>
              </p>
              <p className="mx-auto mt-3 max-w-xl text-lg font-semibold text-[#007A5E]">
                Je suis SmartMboa. Sites, culture, nature et itinéraires.
              </p>
              <button
                type="button"
                onClick={openVoice}
                className="mt-6 inline-flex items-center gap-2 rounded-full bg-[#007A5E] px-8 py-3 text-sm font-bold text-white shadow-md hover:bg-[#00614b]"
              >
                <Mic className="h-4 w-4" aria-hidden />
                Parler au guide
              </button>
            </div>
            <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.label}
                  type="button"
                  onClick={() => void ask(s.q)}
                  className="rounded-lg bg-white p-5 text-left shadow-lg transition duration-300 hover:scale-[1.02]"
                >
                  <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[#FCD116]/50">
                    <s.icon className="h-6 w-6 text-[#007A5E]" aria-hidden />
                  </span>
                  <span className="block text-base font-bold text-[#007A5E]">{s.label}</span>
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
                      : msg.phraseAudioUrl
                        ? 'Écouter la voix locale'
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
                      {msg.phraseAudioUrl ? 'Voix locale' : 'Lire'}
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
              <div className="rounded-xl bg-white px-4 py-4 shadow-lg">
                <ResponseRenderer text={msg.content} ui={msg.ui} />
              </div>
            ) : msg.isError ? (
              <ErrorState message={msg.content} />
            ) : (
              <div className="rounded-2xl bg-[#007A5E] px-4 py-3 text-white shadow-md">
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
        className="shrink-0 bg-white p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-[0_-8px_24px_rgba(0,0,0,0.04)] md:p-4"
      >
        <div className="mx-auto flex max-w-3xl items-center gap-2 rounded-full border border-gray-200 bg-white p-2 shadow-lg">
          <button
            type="button"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#FCD116]/50 text-[#007A5E]"
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
            className="min-w-0 flex-1 border-0 shadow-none focus:ring-0"
            aria-label="Message"
            disabled={sending}
          />

          <button
            type="button"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#FCD116] text-[#1a1a1a]"
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
            className="bg-[#007A5E] hover:bg-[#00614b]"
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
