'use client';

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import { Loader2, Mic, Volume2, X } from 'lucide-react';

import { friendlyError, transcribeAudio } from '@/lib/api/client';
import { audioPlayback } from '@/lib/audio/playback';
import { useLocale } from '@/lib/i18n';
import { VoiceSocket } from '@/lib/websocket/voice';
import type { StructuredChatUI } from '@/lib/types';

export type VoicePhase = 'idle' | 'listening' | 'thinking' | 'speaking';

export type VoiceExchange = {
  userText?: string;
  assistantText?: string;
  ui?: StructuredChatUI | null;
  conversationId?: string;
  tip?: string;
  error?: string;
};

const MAX_RECORD_MS = 25_000;
/** Actual recording time after MediaRecorder has started. */
const MIN_RECORD_MS = 1_200;
/** WebM headers alone can exceed 1–2KB with almost no audio. */
const MIN_BLOB_BYTES = 8_000;

function phaseCopy(phase: VoicePhase): {
  title: string;
  subtitle: string;
  action: string;
} {
  switch (phase) {
    case 'listening':
      return {
        title: 'Je vous écoute',
        subtitle: 'Parlez clairement, puis appuyez pour envoyer.',
        action: 'Appuyer pour envoyer',
      };
    case 'thinking':
      return {
        title: 'Je comprends…',
        subtitle: 'Transcription puis réponse du guide.',
        action: 'Patientez',
      };
    case 'speaking':
      return {
        title: 'Réponse en cours',
        subtitle: 'Écoutez le guide, ou appuyez pour interrompre.',
        action: 'Appuyer pour interrompre',
      };
    default:
      return {
        title: 'Prêt à vous écouter',
        subtitle: 'Appuyez sur le micro, parlez, puis renvoyez.',
        action: 'Appuyer pour parler',
      };
  }
}

function VoiceWave({ active }: { active: boolean }) {
  return (
    <div className="flex h-8 items-end justify-center gap-1.5" aria-hidden>
      {[0, 1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className={`w-1.5 rounded-full bg-[var(--gold)] transition-all ${
            active ? 'animate-pulse' : 'opacity-40'
          }`}
          style={{
            height: active ? `${14 + ((i * 7) % 18)}px` : '8px',
            animationDelay: `${i * 80}ms`,
          }}
        />
      ))}
    </div>
  );
}

function pickRecorderMime(): string | undefined {
  if (typeof MediaRecorder === 'undefined') return undefined;
  if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus'))
    return 'audio/webm;codecs=opus';
  if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm';
  if (MediaRecorder.isTypeSupported('audio/mp4')) return 'audio/mp4';
  return undefined;
}

function extForMime(mime: string): string {
  const m = mime.toLowerCase();
  if (m.includes('mp4') || m.includes('m4a')) return 'm4a';
  if (m.includes('ogg')) return 'ogg';
  if (m.includes('wav')) return 'wav';
  return 'webm';
}

export function VoiceMode({
  open,
  onClose,
  conversationId,
  onExchange,
}: {
  open: boolean;
  onClose: () => void;
  conversationId?: string;
  onExchange: (exchange: VoiceExchange) => void;
}) {
  const { locale } = useLocale();
  const [phase, setPhase] = useState<VoicePhase>('idle');
  const [userText, setUserText] = useState('');
  const [assistantText, setAssistantText] = useState('');
  const [hint, setHint] = useState<string | null>(null);
  const [micReady, setMicReady] = useState(false);
  const [mounted, setMounted] = useState(false);

  const socketRef = useRef<VoiceSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const recordStartedAtRef = useRef(0);
  const maxTimerRef = useRef<number | undefined>(undefined);
  const sendingRef = useRef(false);
  const assistantAccRef = useRef('');
  const phaseRef = useRef<VoicePhase>('idle');
  const conversationIdRef = useRef(conversationId);
  const finishRef = useRef<() => Promise<void>>(async () => undefined);
  const shutdownRef = useRef<() => void>(() => undefined);
  const onExchangeRef = useRef(onExchange);
  const localeRef = useRef(locale);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  useEffect(() => {
    onExchangeRef.current = onExchange;
  }, [onExchange]);

  useEffect(() => {
    localeRef.current = locale;
  }, [locale]);

  const clearMaxTimer = useCallback(() => {
    if (maxTimerRef.current !== undefined) {
      clearTimeout(maxTimerRef.current);
      maxTimerRef.current = undefined;
    }
  }, []);

  const stopRecorderOnly = useCallback(() => {
    clearMaxTimer();
    try {
      if (mediaRecorderRef.current?.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
    } catch {
      /* ignore */
    }
    mediaRecorderRef.current = null;
    chunksRef.current = [];
  }, [clearMaxTimer]);

  const releaseMic = useCallback(() => {
    stopRecorderOnly();
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    mediaStreamRef.current = null;
    setMicReady(false);
  }, [stopRecorderOnly]);

  const shutdown = useCallback(() => {
    sendingRef.current = false;
    clearMaxTimer();
    audioPlayback.stop();
    try {
      socketRef.current?.interrupt();
    } catch {
      /* ignore */
    }
    try {
      socketRef.current?.close();
    } catch {
      /* ignore */
    }
    socketRef.current = null;
    releaseMic();
    setPhase('idle');
  }, [clearMaxTimer, releaseMic]);

  const armMic = useCallback(async (): Promise<MediaStream> => {
    if (mediaStreamRef.current) {
      const live = mediaStreamRef.current.getAudioTracks().some((t) => t.readyState === 'live');
      if (live) {
        setMicReady(true);
        return mediaStreamRef.current;
      }
      releaseMic();
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
    });
    mediaStreamRef.current = stream;
    setMicReady(true);
    return stream;
  }, [releaseMic]);

  const ensureSocket = useCallback(async () => {
    if (socketRef.current) return socketRef.current;

    const socket = new VoiceSocket();
    socketRef.current = socket;
    assistantAccRef.current = '';

    await socket.connect((ev) => {
      if (ev.type === 'status') {
        const p = `${ev.phase || ''} ${ev.message || ''}`.toLowerCase();
        if (/transcrib|think|analy|process|llm|rag/.test(p)) setPhase('thinking');
        else if (/speak|tts|audio|play/.test(p)) setPhase('speaking');
      }

      if (ev.type === 'transcript' && ev.text) {
        setUserText(ev.text);
        onExchangeRef.current({ userText: ev.text });
      }

      if (ev.type === 'token' && ev.text) {
        assistantAccRef.current += ev.text;
        setAssistantText(assistantAccRef.current);
        setPhase('speaking');
      }

      if (ev.type === 'assistant_text' && ev.text) {
        assistantAccRef.current = ev.text;
        setAssistantText(ev.text);
      }

      if (ev.type === 'audio_chunk' && ev.data) {
        setPhase('speaking');
        audioPlayback.enqueueBase64(ev.data);
      }

      if (ev.type === 'turn_done') {
        sendingRef.current = false;
        const text = assistantAccRef.current;
        onExchangeRef.current({
          assistantText: text || undefined,
          ui: ev.ui ?? null,
          conversationId: ev.conversation_id,
        });
        if (ev.conversation_id) conversationIdRef.current = ev.conversation_id;
        try {
          socket.close();
        } catch {
          /* ignore */
        }
        socketRef.current = null;
        setPhase('idle');
        setHint(null);
        assistantAccRef.current = '';
        // Keep mic warm for next turn
        void armMic().catch(() => setMicReady(false));
      }

      if (ev.type === 'interrupted') {
        sendingRef.current = false;
        if (phaseRef.current !== 'listening') setPhase('idle');
      }

      if (ev.type === 'error') {
        sendingRef.current = false;
        audioPlayback.stop();
        const tip = ev.message || 'La voix est momentanément indisponible.';
        setHint(tip);
        onExchangeRef.current({ error: tip });
        setPhase('idle');
        try {
          socket.close();
        } catch {
          /* ignore */
        }
        socketRef.current = null;
      }
    });

    return socket;
  }, [armMic]);

  const startListening = useCallback(async () => {
    if (sendingRef.current || phaseRef.current === 'listening') return;
    setHint(null);
    audioPlayback.stop();
    try {
      socketRef.current?.interrupt();
    } catch {
      /* ignore */
    }

    setPhase('listening');
    assistantAccRef.current = '';

    try {
      const stream = await armMic();
      const mime = pickRecorderMime();
      const recorder = mime
        ? new MediaRecorder(stream, { mimeType: mime })
        : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];
      recordStartedAtRef.current = Date.now();
      recorder.ondataavailable = (e) => {
        if (e.data?.size) chunksRef.current.push(e.data);
      };
      // Timeslices → real audio frames accumulate (more reliable for STT)
      recorder.start(250);

      clearMaxTimer();
      maxTimerRef.current = window.setTimeout(() => {
        void finishRef.current();
      }, MAX_RECORD_MS);
    } catch (err) {
      const msg =
        err instanceof Error && /Permission|NotAllowed|NotFound/i.test(err.message)
          ? 'Micro non autorisé. Autorisez l’accès au micro dans le navigateur.'
          : 'Impossible d’accéder au micro.';
      setHint(msg);
      onExchangeRef.current({ error: msg });
      setPhase('idle');
      stopRecorderOnly();
    }
  }, [armMic, clearMaxTimer, stopRecorderOnly]);

  const finishListeningAndSend = useCallback(async () => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || sendingRef.current) return;

    const elapsed = Date.now() - recordStartedAtRef.current;
    if (elapsed < MIN_RECORD_MS) {
      const tip =
        'Enregistrement trop court. Parlez au moins une à deux secondes, puis renvoyez.';
      setHint(tip);
      stopRecorderOnly();
      setPhase('idle');
      return;
    }

    sendingRef.current = true;
    setPhase('thinking');
    clearMaxTimer();

    await new Promise<void>((resolve) => {
      const done = () => resolve();
      recorder.onstop = done;
      try {
        if (recorder.state === 'recording') {
          try {
            recorder.requestData();
          } catch {
            /* ignore */
          }
          recorder.stop();
        } else done();
      } catch {
        done();
      }
    });

    // Keep mic stream warm; only clear recorder
    mediaRecorderRef.current = null;

    const mimeFull = recorder.mimeType || 'audio/webm';
    const mime = mimeFull.split(';')[0] || 'audio/webm';
    const blob = new Blob(chunksRef.current, { type: mimeFull });
    chunksRef.current = [];

    if (blob.size < MIN_BLOB_BYTES) {
      const tip =
        'Je n’ai presque rien capté. Rapprochez-vous du micro et reparlez un peu plus longtemps.';
      setHint(tip);
      onExchangeRef.current({ tip });
      sendingRef.current = false;
      setPhase('idle');
      return;
    }

    try {
      // STT via HTTP (reliable convert→Whisper), then WS text for LLM + TTS stream
      const { text } = await transcribeAudio(blob, {
        mimeType: mime,
        filename: `recording.${extForMime(mime)}`,
      });

      if (!text) {
        const tip =
          'Je n’ai pas compris. Parlez plus distinctement près du micro, puis réessayez.';
        setHint(tip);
        onExchangeRef.current({ tip });
        sendingRef.current = false;
        setPhase('idle');
        return;
      }

      setUserText(text);
      onExchangeRef.current({ userText: text });
      assistantAccRef.current = '';
      setAssistantText('');

      const socket = await ensureSocket();
      socket.sendText(text, localeRef.current);
      setPhase('thinking');
    } catch (err) {
      const tip = friendlyError(err);
      setHint(tip);
      onExchangeRef.current({ error: tip });
      sendingRef.current = false;
      setPhase('idle');
    }
  }, [clearMaxTimer, ensureSocket, stopRecorderOnly]);

  useEffect(() => {
    finishRef.current = finishListeningAndSend;
  }, [finishListeningAndSend]);

  useEffect(() => {
    shutdownRef.current = shutdown;
  }, [shutdown]);

  const onOrbPress = useCallback(() => {
    if (phase === 'thinking') return;
    if (phase === 'idle') {
      void startListening();
      return;
    }
    if (phase === 'listening') {
      void finishListeningAndSend();
      return;
    }
    if (phase === 'speaking') {
      audioPlayback.stop();
      try {
        socketRef.current?.interrupt();
      } catch {
        /* ignore */
      }
      try {
        socketRef.current?.close();
      } catch {
        /* ignore */
      }
      socketRef.current = null;
      sendingRef.current = false;
      setPhase('idle');
      setHint(null);
      void startListening();
    }
  }, [finishListeningAndSend, phase, startListening]);

  // Open / close lifecycle
  useEffect(() => {
    if (!open) {
      shutdownRef.current();
      setUserText('');
      setAssistantText('');
      setHint(null);
      setMicReady(false);
      return;
    }
    setPhase('idle');
    setHint(null);
    // Pre-warm mic so first tap records immediately (better STT)
    void armMic().catch(() => {
      setMicReady(false);
      setHint('Autorisez le micro pour parler au guide.');
    });
    return () => {
      shutdownRef.current();
    };
  }, [open, armMic]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        shutdownRef.current();
        onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open || !mounted) return null;

  const copy = phaseCopy(phase);
  const live = phase === 'listening' || phase === 'speaking';

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex flex-col bg-[var(--green-deep)] text-white"
      role="dialog"
      aria-modal="true"
      aria-label="Mode vocal SmartMboa"
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          background:
            'radial-gradient(ellipse 80% 50% at 50% 20%, rgba(214,168,79,0.35), transparent 60%), radial-gradient(ellipse 60% 40% at 80% 90%, rgba(26,122,86,0.5), transparent)',
        }}
        aria-hidden
      />

      <header className="relative z-10 flex items-center justify-between px-4 pb-2 pt-[max(1rem,env(safe-area-inset-top))] md:px-8">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--gold-soft)]">
            SmartMboa
          </p>
          <h2 className="font-display text-xl font-bold md:text-2xl">Mode vocal</h2>
          <p className="mt-0.5 text-xs text-white/55">
            STT · transcription &nbsp;·&nbsp; TTS · réponse parlée
            {micReady ? ' · micro prêt' : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            shutdown();
            onClose();
          }}
          className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-2 text-sm font-semibold backdrop-blur hover:bg-white/20"
          aria-label="Fermer le mode vocal"
        >
          <X className="h-4 w-4" aria-hidden />
          Fermer
        </button>
      </header>

      <div className="relative z-10 flex min-h-0 flex-1 flex-col items-center justify-between px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-4 md:px-8">
        <div className="w-full max-w-lg space-y-3 text-center">
          <p className="font-display text-2xl font-semibold md:text-3xl" aria-live="polite">
            {copy.title}
          </p>
          <p className="text-sm text-white/75 md:text-base">{copy.subtitle}</p>
          <VoiceWave active={live} />
        </div>

        <div className="flex flex-col items-center gap-5 py-6">
          <button
            type="button"
            onClick={onOrbPress}
            disabled={phase === 'thinking'}
            aria-label={copy.action}
            className={`relative flex h-36 w-36 items-center justify-center rounded-full shadow-[0_0_0_12px_rgba(214,168,79,0.15)] transition select-none disabled:cursor-wait disabled:opacity-70 md:h-44 md:w-44 ${
              phase === 'listening'
                ? 'bg-[var(--danger)] shadow-[0_0_0_16px_rgba(180,35,24,0.25)]'
                : phase === 'speaking'
                  ? 'bg-[var(--gold)] text-[var(--green-deep)]'
                  : 'bg-white text-[var(--green-deep)]'
            }`}
          >
            {phase === 'listening' ? (
              <span className="absolute inset-0 animate-ping rounded-full bg-[var(--danger)] opacity-30" />
            ) : null}
            {phase === 'thinking' ? (
              <Loader2 className="relative h-12 w-12 animate-spin" aria-hidden />
            ) : phase === 'speaking' ? (
              <Volume2 className="relative h-12 w-12" aria-hidden />
            ) : (
              <Mic className="relative h-12 w-12" aria-hidden />
            )}
          </button>
          <p className="text-sm font-semibold text-[var(--gold-soft)]">{copy.action}</p>
        </div>

        <div className="w-full max-w-lg space-y-3">
          {hint ? (
            <p
              className="rounded-2xl bg-white/10 px-4 py-3 text-center text-sm text-[var(--gold-soft)]"
              role="status"
            >
              {hint}
            </p>
          ) : null}
          {(userText || assistantText) && (
            <div className="max-h-40 space-y-2 overflow-y-auto rounded-2xl bg-black/20 p-4 text-left text-sm backdrop-blur">
              {userText ? (
                <p>
                  <span className="font-semibold text-[var(--gold-soft)]">Vous · </span>
                  {userText}
                </p>
              ) : null}
              {assistantText ? (
                <p>
                  <span className="font-semibold text-[var(--gold-soft)]">SmartMboa · </span>
                  {assistantText}
                </p>
              ) : null}
            </div>
          )}
          <p className="text-center text-xs text-white/50">
            Les échanges restent aussi dans le chat. Lire / Stop restent dispo sur les réponses texte.
          </p>
        </div>
      </div>
    </div>,
    document.body,
  );
}
