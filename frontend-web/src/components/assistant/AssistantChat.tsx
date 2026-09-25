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
import { Button, ErrorState, Input, ThinkingDots } from '@/components/ui';
import { friendlyError, sendChatMessage, synthesizeSpeech } from '@/lib/api/client';
import { audioPlayback } from '@/lib/audio/playback';
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
  /** Soft tip (e.g. empty mic) — not a hard failure banner */
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

/** Max recording length as safety net (user should stop earlier). */
const MAX_RECORD_MS = 20_000;
const MIN_RECORD_MS = 800;

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
  const [speakingMsgId, setSpeakingMsgId] = useState<string | null>(null);
  const [audioPlaying, setAudioPlaying] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const streamMsgId = useRef<string | null>(null);

  const voiceSocketRef = useRef<VoiceSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recordChunksRef = useRef<BlobPart[]>([]);
  const recordStartedAtRef = useRef(0);
  const maxRecordTimerRef = useRef<number | undefined>(undefined);
  const ttsAbortRef = useRef<AbortController | null>(null);
  const sendingAudioRef = useRef(false);

  useEffect(() => {
    return audioPlayback.subscribe(setAudioPlaying);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending, voicePhase]);

  const cleanupMedia = useCallback(() => {
    if (maxRecordTimerRef.current !== undefined) {
      clearTimeout(maxRecordTimerRef.current);
      maxRecordTimerRef.current = undefined;
    }
    try {
      mediaRecorderRef.current?.stop();
    } catch {
      /* already stopped */
    }
    mediaRecorderRef.current = null;
    mediaStreamRef.current?.getTracks().forEach((tr) => tr.stop());
    mediaStreamRef.current = null;
    recordChunksRef.current = [];
  }, []);

  const stopAllAudio = useCallback(() => {
    ttsAbortRef.current?.abort();
    ttsAbortRef.current = null;
    audioPlayback.stop();
    setSpeakingMsgId(null);
  }, []);

  const stopVoiceSession = useCallback(() => {
    sendingAudioRef.current = false;
    try {
      voiceSocketRef.current?.interrupt();
    } catch {
      /* ignore */
    }
    try {
      voiceSocketRef.current?.close();
    } catch {
      /* ignore */
    }
    voiceSocketRef.current = null;
    cleanupMedia();
    stopAllAudio();
    setVoicePhase(null);
    streamMsgId.current = null;
  }, [cleanupMedia, stopAllAudio]);

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending || voicePhase) return;
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
    if (initialQuestion) {
      started.current = true;
      void ask(initialQuestion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuestion]);

  const finishRecordingAndSend = useCallback(async () => {
    const recorder = mediaRecorderRef.current;
    const socket = voiceSocketRef.current;
    if (!recorder || !socket || sendingAudioRef.current) {
      if (!recorder || !socket) stopVoiceSession();
      return;
    }

    const elapsed = Date.now() - recordStartedAtRef.current;
    if (elapsed < MIN_RECORD_MS) {
      setMessages((m) => [
        ...m,
        {
          id: `${Date.now()}-ve`,
          role: 'assistant',
          content: 'Enregistrement trop court. Parlez un peu plus longtemps, puis appuyez sur Stop.',
          isError: true,
        },
      ]);
      stopVoiceSession();
      return;
    }

    sendingAudioRef.current = true;
    setVoicePhase('thinking');
    if (maxRecordTimerRef.current !== undefined) {
      clearTimeout(maxRecordTimerRef.current);
      maxRecordTimerRef.current = undefined;
    }

    // Flush final chunk, then stop
    await new Promise<void>((resolve) => {
      const done = () => resolve();
      recorder.onstop = done;
      try {
        if (recorder.state === 'recording') {
          try {
            recorder.requestData();
          } catch {
            /* some browsers */
          }
          recorder.stop();
        } else {
          done();
        }
      } catch {
        done();
      }
    });

    mediaStreamRef.current?.getTracks().forEach((tr) => tr.stop());
    mediaStreamRef.current = null;
    mediaRecorderRef.current = null;

    const mime = (recorder.mimeType || 'audio/webm').split(';')[0] || 'audio/webm';
    const blob = new Blob(recordChunksRef.current, { type: mime });
    recordChunksRef.current = [];

    if (blob.size < 1200) {
      setMessages((m) => [
        ...m,
        {
          id: `${Date.now()}-ve`,
          role: 'assistant',
          content: 'Enregistrement trop court. Parlez un peu plus longtemps, puis appuyez sur Stop.',
          isError: true,
        },
      ]);
      stopVoiceSession();
      return;
    }

    try {
      const b64 = await blobToBase64(blob);
      // Single WS message — never follow with bare `utterance` (cancels the turn).
      socket.sendAudioBase64(b64, mime, locale);
    } catch (error) {
      setMessages((m) => [
        ...m,
        {
          id: `${Date.now()}-ve`,
          role: 'assistant',
          content: friendlyError(error),
          isError: true,
        },
      ]);
      stopVoiceSession();
    }
  }, [locale, stopVoiceSession]);

  async function startVoice() {
    if (voicePhase === 'listening') {
      await finishRecordingAndSend();
      return;
    }
    if (voicePhase === 'thinking' || voicePhase === 'speaking') {
      stopVoiceSession();
      return;
    }

    stopAllAudio();
    setVoicePhase('listening');
    streamMsgId.current = null;
    sendingAudioRef.current = false;

    const socket = new VoiceSocket();
    voiceSocketRef.current = socket;
    let assistantText = '';

    try {
      await socket.connect((ev) => {
        if (ev.type === 'status') {
          const phase = (ev.phase || '').toLowerCase();
          const msg = (ev.message || '').toLowerCase();
          const blob = `${phase} ${msg}`;
          if (/listen|écoute|recording|mic/.test(blob)) setVoicePhase('listening');
          else if (/think|analy|process|llm|rag|transcrib/.test(blob))
            setVoicePhase('thinking');
          else if (/speak|tts|audio|play/.test(blob)) setVoicePhase('speaking');
          else if (ev.message || ev.phase) setVoicePhase('thinking');
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
              { id, role: 'assistant', content: assistantText, streaming: true },
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
          audioPlayback.enqueueBase64(ev.data);
        }
        if (ev.type === 'turn_done') {
          sendingAudioRef.current = false;
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
          voiceSocketRef.current = null;
          cleanupMedia();
        }
        if (ev.type === 'interrupted') {
          // Ignore mid-flight interrupt we didn't ask for only if still sending
          if (!sendingAudioRef.current) {
            setVoicePhase(null);
            streamMsgId.current = null;
          }
        }
        if (ev.type === 'error') {
          sendingAudioRef.current = false;
          setVoicePhase(null);
          const soft =
            ev.code === 'empty_transcript' ||
            /parole détectée|no speech/i.test(ev.message || '');
          setMessages((m) => [
            ...m,
            soft
              ? {
                  id: `${Date.now()}-ve`,
                  role: 'assistant',
                  content:
                    'Aucune parole détectée. Parlez clairement près du micro, puis appuyez sur Stop.',
                  isTip: true,
                }
              : {
                  id: `${Date.now()}-ve`,
                  role: 'assistant',
                  content: ev.message || 'La voix est momentanément indisponible.',
                  isError: true,
                },
          ]);
          socket.close();
          voiceSocketRef.current = null;
          cleanupMedia();
          stopAllAudio();
        }
      });

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          channelCount: 1,
        },
      });
      mediaStreamRef.current = stream;
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : MediaRecorder.isTypeSupported('audio/mp4')
            ? 'audio/mp4'
            : undefined;
      const recorder = mime
        ? new MediaRecorder(stream, { mimeType: mime })
        : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      recordChunksRef.current = [];
      recordStartedAtRef.current = Date.now();
      recorder.ondataavailable = (e) => {
        if (e.data.size) recordChunksRef.current.push(e.data);
      };
      // Prefer one blob on stop (more reliable headers for STT) vs timeslices
      recorder.start();

      maxRecordTimerRef.current = window.setTimeout(() => {
        void finishRecordingAndSend();
      }, MAX_RECORD_MS);
    } catch (error) {
      setMessages((m) => [
        ...m,
        {
          id: `${Date.now()}-ve`,
          role: 'assistant',
          content: friendlyError(error),
          isError: true,
        },
      ]);
      stopVoiceSession();
    }
  }

  async function speakMessage(msg: Msg) {
    const text = msg.content?.trim();
    if (!text || msg.isError) return;

    if (speakingMsgId === msg.id) {
      stopAllAudio();
      return;
    }

    if (voicePhase) stopVoiceSession();

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
    if (autoVoice && !started.current) {
      started.current = true;
      void startVoice();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoVoice]);

  useEffect(() => {
    return () => {
      stopVoiceSession();
    };
  }, [stopVoiceSession]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(input);
  }

  const voiceLabel =
    voicePhase === 'listening'
      ? 'Écoute… appuyez sur Stop pour envoyer'
      : voicePhase === 'thinking'
        ? t('assistant.thinking')
        : voicePhase === 'speaking'
          ? 'SmartMboa parle…'
          : null;

  const busy = sending || !!voicePhase;

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
          {(voicePhase || audioPlaying || speakingMsgId) && (
            <button
              type="button"
              onClick={() => {
                if (voicePhase) stopVoiceSession();
                else stopAllAudio();
              }}
              className="inline-flex items-center gap-1.5 rounded-full bg-[var(--danger)] px-3 py-1.5 text-xs font-semibold text-white"
              aria-label="Arrêter la lecture ou le micro"
            >
              <Square className="h-3.5 w-3.5 fill-current" aria-hidden />
              Stop
            </button>
          )}
        </div>
        {voiceLabel ? (
          <p
            className="mt-2 inline-flex items-center gap-2 rounded-full bg-[var(--mint-soft)] px-3 py-1 text-sm font-medium text-[var(--green)]"
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

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain px-4 py-4 md:px-6">
        {messages.length === 0 && !sending ? (
          <div className="mx-auto max-w-lg py-6 text-center">
            <p className="font-display text-2xl font-semibold text-[var(--green-deep)]">
              Bonjour
            </p>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Je suis SmartMboa, votre guide intelligent pour découvrir le Cameroun.
            </p>
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
              {msg.role === 'assistant' && !msg.isError && msg.content.trim() ? (
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
            disabled={busy}
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
            disabled={busy}
          />

          {voicePhase || audioPlaying || speakingMsgId ? (
            <button
              type="button"
              className={`relative flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--danger)] text-white ${
                voicePhase === 'listening'
                  ? 'ring-2 ring-[var(--danger)] ring-offset-2'
                  : ''
              }`}
              aria-label={
                voicePhase === 'listening'
                  ? 'Stop — envoyer l’enregistrement'
                  : 'Stop — arrêter la voix'
              }
              onClick={() => {
                if (voicePhase === 'listening') void finishRecordingAndSend();
                else if (voicePhase) stopVoiceSession();
                else stopAllAudio();
              }}
            >
              {voicePhase === 'listening' ? (
                <span className="absolute inset-0 animate-ping rounded-full bg-[var(--danger)] opacity-30" />
              ) : null}
              <Square className="relative h-4 w-4 fill-current" />
            </button>
          ) : (
            <button
              type="button"
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--mint-soft)] text-[var(--green-deep)]"
              aria-label="Micro — parler à SmartMboa"
              disabled={sending}
              onClick={() => void startVoice()}
            >
              <Mic className="h-5 w-5" />
            </button>
          )}

          <Button
            type="submit"
            disabled={busy || !input.trim()}
            aria-label="Envoyer"
          >
            <SendHorizontal className="h-4 w-4" />
          </Button>
        </div>
      </form>
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
