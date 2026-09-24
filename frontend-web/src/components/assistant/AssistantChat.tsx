'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import { ResponseRenderer } from '@/components/assistant/ResponseRenderer';
import { Button, ErrorState, Input } from '@/components/ui';
import {
  friendlyError,
  listTouristSites,
  sendChatMessage,
} from '@/lib/api/client';
import { useLocale } from '@/lib/i18n';
import { inferResponseKind, sourcesToMarkers } from '@/lib/utils/response';
import {
  VoiceSocket,
  blobToBase64,
} from '@/lib/websocket/voice';
import type { ChatSource, MapMarker, TouristSite } from '@/lib/types';

interface Msg {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  markers?: MapMarker[];
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
      const kind = inferResponseKind(res.message, res.sources);
      const markers = sourcesToMarkers(sitesCache, res.sources);
      setMessages((m) => [
        ...m,
        {
          id: `${Date.now()}-a`,
          role: 'assistant',
          content: res.message,
          sources: res.sources,
          markers,
          // kind used by renderer via infer again
        },
      ]);
      void kind;
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
    <div className="flex min-h-[70vh] flex-col rounded-3xl border border-[var(--line)] bg-white shadow-sm">
      <div className="border-b border-[var(--line)] px-5 py-4">
        <h1 className="font-display text-2xl text-[var(--green-deep)]">
          {t('assistant.title')}
        </h1>
        {voicePhase ? (
          <p className="mt-1 text-sm text-[var(--green)]">🎙️ {voicePhase}</p>
        ) : null}
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto px-5 py-6">
        {messages.length === 0 && !sending ? (
          <p className="text-sm text-[var(--muted)]">{t('home.assistantHint')}</p>
        ) : null}
        {messages.map((msg) => (
          <div key={msg.id} className={msg.role === 'user' ? 'ml-8' : 'mr-4'}>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              {msg.role === 'user' ? t('assistant.you') : t('assistant.bot')}
            </p>
            {msg.role === 'assistant' && !msg.isError ? (
              <ResponseRenderer
                text={msg.content}
                kind={inferResponseKind(msg.content, msg.sources)}
                sources={msg.sources}
                markers={msg.markers}
              />
            ) : msg.isError ? (
              <ErrorState message={msg.content} />
            ) : (
              <div className="rounded-2xl bg-[var(--green)] px-4 py-3 text-[var(--ivory)]">
                {msg.content}
              </div>
            )}
          </div>
        ))}
        {sending ? (
          <p className="text-sm text-[var(--muted)]">{t('assistant.thinking')}</p>
        ) : null}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={onSubmit}
        className="flex flex-wrap items-center gap-2 border-t border-[var(--line)] p-4"
      >
        <Button type="button" variant="secondary" onClick={() => fileRef.current?.click()}>
          📷
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) {
              window.location.href = '/vision';
            }
          }}
        />
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t('home.placeholder')}
          className="min-w-[12rem] flex-1"
        />
        <Button type="button" variant="secondary" onClick={() => void startVoice()}>
          🎙️
        </Button>
        <Button type="submit" disabled={sending}>
          ➤
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

export function AssistantPageClient() {
  const params = useSearchParams();
  const q = params.get('q') ?? undefined;
  const voice = params.get('voice') === '1';
  return <AssistantChat initialQuestion={q} autoVoice={voice} />;
}
