'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { Camera, Mic, SendHorizontal, Sparkles } from 'lucide-react';

import { ResponseRenderer } from '@/components/assistant/ResponseRenderer';
import { Button, ErrorState, Input, ThinkingDots } from '@/components/ui';
import { friendlyError, sendChatMessage } from '@/lib/api/client';
import { useLocale } from '@/lib/i18n';
import { structuredFromChatResponse } from '@/lib/utils/response';
import { VoiceSocket, blobToBase64 } from '@/lib/websocket/voice';
import type { StructuredChatUI } from '@/lib/types';

interface Msg {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  ui?: StructuredChatUI | null;
  isError?: boolean;
  streaming?: boolean;
}

const SUGGESTIONS = [
  'Je suis à Bafoussam et je veux visiter un site touristique.',
  'Propose un itinéraire de 3 jours à Limbé.',
  'Quels parcs naturels vérifiés recommandez-vous ?',
  'Propose un hôtel vérifié à Douala.',
] as const;

type VoicePhase = 'listening' | 'thinking' | 'speaking' | null;

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
  const [voicePhase, setVoicePhase] = useState<VoicePhase>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const streamMsgId = useRef<string | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending, voicePhase]);

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;
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
    if (initialQuestion) {
      started.current = true;
      void ask(initialQuestion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuestion]);

  async function startVoice() {
    setVoicePhase('listening');
    const socket = new VoiceSocket();
    let assistantText = '';
    streamMsgId.current = null;

    try {
      await socket.connect((ev) => {
        if (ev.type === 'status') {
          const phase = (ev.phase || '').toLowerCase();
          const msg = (ev.message || '').toLowerCase();
          if (/listen|écoute|recording|mic/.test(`${phase} ${msg}`)) {
            setVoicePhase('listening');
          } else if (/think|analy|process|llm|rag/.test(`${phase} ${msg}`)) {
            setVoicePhase('thinking');
          } else if (/speak|tts|audio|play/.test(`${phase} ${msg}`)) {
            setVoicePhase('speaking');
          } else if (ev.message || ev.phase) {
            setVoicePhase('thinking');
          }
        }
        if (ev.type === 'transcript' && ev.text) {
          setMessages((m) => [
            ...m,
            { id: `${Date.now()}-vt`, role: 'user', content: ev.text },
          ]);
        }
        if (ev.type === 'token' && ev.text) {
          assistantText += ev.text;
          setVoicePhase('speaking');
          setMessages((m) => {
            const sid = streamMsgId.current;
            if (sid) {
              return m.map((msg) =>
                msg.id === sid
                  ? { ...msg, content: assistantText, streaming: true }
                  : msg,
              );
            }
            const id = `stream-${Date.now()}`;
            streamMsgId.current = id;
            return [
              ...m,
              {
                id,
                role: 'assistant',
                content: assistantText,
                streaming: true,
              },
            ];
          });
        }
        if (ev.type === 'assistant_text' && ev.text) {
          assistantText = ev.text;
          setMessages((m) => {
            const sid = streamMsgId.current;
            if (sid) {
              return m.map((msg) =>
                msg.id === sid ? { ...msg, content: assistantText } : msg,
              );
            }
            const id = `stream-${Date.now()}`;
            streamMsgId.current = id;
            return [
              ...m,
              { id, role: 'assistant', content: assistantText, streaming: true },
            ];
          });
        }
        if (ev.type === 'audio_chunk' && ev.data) {
          setVoicePhase('speaking');
          void playChunk(ev.data);
        }
        if (ev.type === 'turn_done') {
          if (ev.conversation_id) setConversationId(ev.conversation_id);
          const ui = ev.ui ?? null;
          setMessages((m) => {
            const sid = streamMsgId.current;
            if (sid) {
              return m.map((msg) =>
                msg.id === sid
                  ? {
                      ...msg,
                      content: assistantText || msg.content,
                      ui: ui ?? undefined,
                      streaming: false,
                    }
                  : msg,
              );
            }
            if (assistantText || ui) {
              return [
                ...m,
                {
                  id: `${Date.now()}-a`,
                  role: 'assistant',
                  content: assistantText,
                  ui: ui ?? undefined,
                },
              ];
            }
            return m;
          });
          streamMsgId.current = null;
          setVoicePhase(null);
          socket.close();
        }
        if (ev.type === 'error') {
          setVoicePhase(null);
          setMessages((m) => [
            ...m,
            {
              id: `${Date.now()}-ve`,
              role: 'assistant',
              content: ev.message || 'La voix est momentanément indisponible.',
              isError: true,
            },
          ]);
          socket.close();
        }
      });

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size) chunks.push(e.data);
      };
      recorder.start();
      await new Promise((r) => setTimeout(r, 4000));
      recorder.stop();
      await new Promise((r) => {
        recorder.onstop = () => r(null);
      });
      stream.getTracks().forEach((tr) => tr.stop());
      const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
      const b64 = await blobToBase64(blob);
      setVoicePhase('thinking');
      socket.sendAudioBase64(b64, blob.type || 'audio/webm');
      socket.send({ type: 'utterance', locale });
    } catch (error) {
      setVoicePhase(null);
      setMessages((m) => [
        ...m,
        {
          id: `${Date.now()}-ve`,
          role: 'assistant',
          content: friendlyError(error),
          isError: true,
        },
      ]);
      socket.close();
    }
  }

  useEffect(() => {
    if (autoVoice && !started.current) {
      started.current = true;
      void startVoice();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoVoice]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(input);
  }

  const voiceLabel =
    voicePhase === 'listening'
      ? t('assistant.listening')
      : voicePhase === 'thinking'
        ? t('assistant.thinking')
        : voicePhase === 'speaking'
          ? 'SmartMboa parle…'
          : null;

  return (
    <div className="flex min-h-[calc(100svh-8rem)] flex-col bg-[var(--ivory)] lg:min-h-[78vh] lg:rounded-3xl lg:border lg:border-[var(--line)] lg:bg-white lg:shadow-[var(--shadow-soft)]">
      <header className="border-b border-[var(--line)] px-5 py-5">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--green-deep)] text-white">
            <Sparkles className="h-4 w-4" aria-hidden />
          </span>
          <div>
            <h1 className="font-display text-xl font-bold text-[var(--green-deep)] md:text-2xl">
              {t('assistant.title')}
            </h1>
            <p className="text-sm text-[var(--muted)]">
              Votre guide intelligent pour découvrir le Cameroun.
            </p>
          </div>
        </div>
        {voiceLabel ? (
          <p
            className="mt-3 inline-flex items-center gap-2 rounded-full bg-[var(--mint-soft)] px-3 py-1 text-sm font-medium text-[var(--green)]"
            aria-live="polite"
          >
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--green)] opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--green)]" />
            </span>
            {voiceLabel}
          </p>
        ) : null}
      </header>

      <div className="flex-1 space-y-6 overflow-y-auto px-4 py-6 md:px-6">
        {messages.length === 0 && !sending ? (
          <div className="mx-auto max-w-lg py-8 text-center">
            <p className="font-display text-2xl font-semibold text-[var(--green-deep)]">
              Bonjour
            </p>
            <p className="mt-2 text-sm text-[var(--muted)]">{t('home.assistantHint')}</p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => void ask(s)}
                  className="rounded-full border border-[var(--line)] bg-white px-3.5 py-2 text-left text-xs text-[var(--ink)] transition hover:border-[var(--gold)] hover:bg-[var(--mint-soft)]"
                >
                  {s}
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
                : 'mr-auto max-w-[98%] md:max-w-[92%]'
            }
          >
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">
              {msg.role === 'user' ? t('assistant.you') : t('assistant.bot')}
              {msg.streaming ? ' · …' : ''}
            </p>
            {msg.role === 'assistant' && !msg.isError ? (
              <div className="rounded-2xl bg-white px-4 py-4 shadow-sm ring-1 ring-[var(--line)] lg:bg-transparent lg:px-0 lg:py-1 lg:shadow-none lg:ring-0">
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
        className="sticky bottom-0 z-10 flex items-center gap-2 border-t border-[var(--line)] bg-[var(--ivory)]/95 p-3 backdrop-blur-md lg:static lg:bg-white lg:p-4"
      >
        <button
          type="button"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--mint-soft)] text-[var(--green-deep)]"
          aria-label="Ouvrir la vision"
          onClick={() => fileRef.current?.click()}
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
          placeholder="Demandez-moi quelque chose…"
          className="min-w-0 flex-1"
          aria-label="Message"
          disabled={sending || !!voicePhase}
        />
        <button
          type="button"
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full ${
            voicePhase
              ? 'bg-[var(--gold)] text-[var(--green-deep)]'
              : 'bg-[var(--mint-soft)] text-[var(--green-deep)]'
          }`}
          aria-label="Micro — parler à SmartMboa"
          disabled={sending || !!voicePhase}
          onClick={() => void startVoice()}
        >
          <Mic className="h-5 w-5" />
        </button>
        <Button
          type="submit"
          disabled={sending || !input.trim() || !!voicePhase}
          aria-label="Envoyer"
        >
          <SendHorizontal className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}

const audioQueue: string[] = [];
let playing = false;

async function playChunk(b64: string) {
  audioQueue.push(b64);
  if (playing) return;
  playing = true;
  while (audioQueue.length) {
    const chunk = audioQueue.shift()!;
    const bytes = Uint8Array.from(atob(chunk), (c) => c.charCodeAt(0));
    const blob = new Blob([bytes], { type: 'audio/mpeg' });
    const url = URL.createObjectURL(blob);
    await new Promise<void>((resolve) => {
      const audio = new Audio(url);
      audio.onended = () => {
        URL.revokeObjectURL(url);
        resolve();
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        resolve();
      };
      void audio.play().catch(() => resolve());
    });
  }
  playing = false;
}

/** @deprecated Prefer AssistantChat with searchParams props from the page. */
export function AssistantPageClient({
  initialQuestion,
  autoVoice,
}: {
  initialQuestion?: string;
  autoVoice?: boolean;
}) {
  return <AssistantChat initialQuestion={initialQuestion} autoVoice={autoVoice} />;
}
