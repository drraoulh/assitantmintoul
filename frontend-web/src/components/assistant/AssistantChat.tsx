'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { Camera, Mic, SendHorizontal } from 'lucide-react';

import { ResponseRenderer } from '@/components/assistant/ResponseRenderer';
import { Button, ErrorState, Input, ThinkingDots } from '@/components/ui';
import {
  friendlyError,
  listTouristSites,
  sendChatMessage,
} from '@/lib/api/client';
import { useLocale } from '@/lib/i18n';
import {
  chatMarkersFromResponse,
  resolveResponseKind,
} from '@/lib/utils/response';
import {
  VoiceSocket,
  blobToBase64,
} from '@/lib/websocket/voice';
import type {
  ChatBudget,
  ChatHotel,
  ChatItinerary,
  ChatPlace,
  ChatSource,
  ChatVisionPayload,
  MapMarker,
  ResponseKind,
  TouristSite,
} from '@/lib/types';

interface Msg {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  markers?: MapMarker[];
  places?: ChatPlace[] | null;
  itinerary?: ChatItinerary | null;
  budget?: ChatBudget | null;
  hotels?: ChatHotel[] | null;
  vision?: ChatVisionPayload | null;
  kind?: ResponseKind;
  isError?: boolean;
}

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
  const [voicePhase, setVoicePhase] = useState<string | null>(null);
  const [sitesCache, setSitesCache] = useState<TouristSite[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void listTouristSites()
      .then((r) => setSitesCache(r.items))
      .catch(() => undefined);
  }, []);

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
      const kind = resolveResponseKind(res);
      const markers = chatMarkersFromResponse(res, sitesCache);
      setMessages((m) => [
        ...m,
        {
          id: `${Date.now()}-a`,
          role: 'assistant',
          content: res.message || res.text || '',
          sources: res.sources ?? res.ui_sources ?? undefined,
          markers,
          places: res.places,
          itinerary: res.itinerary,
          budget: res.budget,
          hotels: res.hotels,
          vision: res.vision,
          kind,
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
    setVoicePhase(t('assistant.listening'));
    const socket = new VoiceSocket();
    let assistantText = '';
    try {
      await socket.connect((ev) => {
        if (ev.type === 'status') {
          setVoicePhase(ev.message || ev.phase || t('assistant.listening'));
        }
        if (ev.type === 'transcript' && ev.text) {
          setMessages((m) => [
            ...m,
            { id: `${Date.now()}-vt`, role: 'user', content: ev.text },
          ]);
        }
        if (ev.type === 'token' && ev.text) {
          assistantText += ev.text;
          setVoicePhase(null);
          setMessages((m) => {
            const last = m[m.length - 1];
            if (last?.role === 'assistant' && last.id.startsWith('stream-')) {
              return [...m.slice(0, -1), { ...last, content: assistantText }];
            }
            return [
              ...m,
              { id: `stream-${Date.now()}`, role: 'assistant', content: assistantText },
            ];
          });
        }
        if (ev.type === 'assistant_text' && ev.text) {
          assistantText = ev.text;
        }
        if (ev.type === 'audio_chunk' && ev.data) {
          void playChunk(ev.data);
        }
        if (ev.type === 'turn_done' || ev.type === 'error') {
          setVoicePhase(null);
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
      setVoicePhase(t('assistant.thinking'));
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

  return (
    <div className="flex min-h-[calc(100svh-8rem)] flex-col bg-[var(--ivory)] lg:min-h-[75vh] lg:rounded-3xl lg:border lg:border-[var(--line)] lg:bg-white lg:shadow-[var(--shadow-soft)]">
      <div className="border-b border-[var(--line)] px-5 py-5">
        <h1 className="font-display text-2xl font-bold text-[var(--green-deep)]">
          {t('assistant.title')}
        </h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Votre guide intelligent pour découvrir le Cameroun.
        </p>
        {voicePhase ? (
          <p className="mt-2 text-sm font-medium text-[var(--green)]" aria-live="polite">
            {voicePhase}
          </p>
        ) : null}
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto px-4 py-6 md:px-6">
        {messages.length === 0 && !sending ? (
          <div className="mx-auto max-w-md py-10 text-center">
            <p className="font-display text-xl font-semibold text-[var(--green-deep)]">
              Bonjour
            </p>
            <p className="mt-2 text-sm text-[var(--muted)]">{t('home.assistantHint')}</p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {[
                'Je suis à Bafoussam et je veux visiter un site touristique.',
                'Propose un itinéraire de 3 jours à Limbé.',
                'Quels parcs naturels vérifiés recommandez-vous ?',
              ].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => void ask(s)}
                  className="rounded-full border border-[var(--line)] bg-white px-3 py-1.5 text-left text-xs text-[var(--ink)] hover:border-[var(--gold)]"
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
            className={msg.role === 'user' ? 'ml-auto max-w-[90%] md:max-w-[75%]' : 'mr-auto max-w-[95%] md:max-w-[90%]'}
          >
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">
              {msg.role === 'user' ? t('assistant.you') : t('assistant.bot')}
            </p>
            {msg.role === 'assistant' && !msg.isError ? (
              <div className="rounded-2xl bg-white px-4 py-4 shadow-sm ring-1 ring-[var(--line)] lg:shadow-none lg:ring-0 lg:px-0 lg:py-0">
                <ResponseRenderer
                  text={msg.content}
                  kind={msg.kind ?? 'SIMPLE_ANSWER'}
                  sources={msg.sources}
                  markers={msg.markers}
                  places={msg.places}
                  itinerary={msg.itinerary}
                  budget={msg.budget}
                  hotels={msg.hotels}
                  vision={msg.vision}
                />
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
        {sending ? <ThinkingDots /> : null}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={onSubmit}
        className="sticky bottom-0 flex items-center gap-2 border-t border-[var(--line)] bg-[var(--ivory)]/95 p-3 backdrop-blur-md lg:static lg:bg-white lg:p-4"
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
            if (e.target.files?.[0]) {
              window.location.href = '/vision';
            }
          }}
        />
        <Input
          id="assistant-message"
          name="message"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t('home.placeholder')}
          className="min-w-0 flex-1"
          aria-label="Message"
        />
        <button
          type="button"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--mint-soft)] text-[var(--green-deep)]"
          aria-label="Microphone"
          onClick={() => void startVoice()}
        >
          <Mic className="h-5 w-5" />
        </button>
        <Button type="submit" disabled={sending || !input.trim()} aria-label="Envoyer">
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

