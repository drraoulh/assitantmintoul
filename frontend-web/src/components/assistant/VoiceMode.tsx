'use client';

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent,
} from 'react';
import { createPortal } from 'react-dom';
import { Loader2, Mic, Volume2, X } from 'lucide-react';

import { audioPlayback } from '@/lib/audio/playback';
import { useLocale } from '@/lib/i18n';
import { VoiceSocket, blobToBase64 } from '@/lib/websocket/voice';
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

const MAX_RECORD_MS = 20_000;
const MIN_RECORD_MS = 800;

function phaseCopy(phase: VoicePhase): {
  title: string;
  subtitle: string;
  action: string;
} {
  switch (phase) {
    case 'listening':
      return {
        title: 'Je vous écoute',
        subtitle: 'Parlez naturellement, comme à un guide.',
        action: 'Relâchez pour envoyer',
      };
    case 'thinking':
      return {
        title: 'Je prépare la réponse',
        subtitle: 'Compréhension et recherche en cours…',
        action: 'Patientez',
      };
    case 'speaking':
      return {
        title: 'Réponse en cours',
        subtitle: 'Écoutez le guide, ou appuyez pour reparler.',
        action: 'Appuyer pour interrompre',
      };
    default:
      return {
        title: 'Prêt à vous écouter',
        subtitle: 'Maintenez le micro pour parler, relâchez pour envoyer.',
        action: 'Maintenir pour parler',
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
  const holdingRef = useRef(false);
  const shutdownRef = useRef<() => void>(() => undefined);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  const clearMaxTimer = useCallback(() => {
    if (maxTimerRef.current !== undefined) {
      clearTimeout(maxTimerRef.current);
      maxTimerRef.current = undefined;
    }
  }, []);

  const stopRecorder = useCallback(() => {
    clearMaxTimer();
    try {
      if (mediaRecorderRef.current?.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
    } catch {
      /* ignore */
    }
    mediaRecorderRef.current = null;
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    mediaStreamRef.current = null;
  }, [clearMaxTimer]);

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
    stopRecorder();
    chunksRef.current = [];
    setPhase('idle');
  }, [clearMaxTimer, stopRecorder]);

  const ensureSocket = useCallback(async () => {
    if (socketRef.current) return socketRef.current;

    const socket = new VoiceSocket();
    socketRef.current = socket;
    assistantAccRef.current = '';

    await socket.connect((ev) => {
      if (ev.type === 'status') {
        const p = `${ev.phase || ''} ${ev.message || ''}`.toLowerCase();
        if (/transcrib/.test(p)) setPhase('thinking');
        else if (/think|analy|process|llm|rag/.test(p)) setPhase('thinking');
        else if (/speak|tts|audio|play/.test(p)) setPhase('speaking');
      }

      if (ev.type === 'transcript' && ev.text) {
        setUserText(ev.text);
        onExchange({ userText: ev.text });
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
        onExchange({
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
      }

      if (ev.type === 'interrupted') {
        sendingRef.current = false;
        if (phaseRef.current !== 'listening') {
          setPhase('idle');
        }
      }

      if (ev.type === 'error') {
        sendingRef.current = false;
        audioPlayback.stop();
        const soft =
          ev.code === 'empty_transcript' ||
          /parole détectée|no speech/i.test(ev.message || '');
        const tip = soft
          ? 'Je n’ai rien entendu. Appuyez pour réessayer.'
          : ev.message || 'La voix est momentanément indisponible.';
        setHint(tip);
        onExchange(soft ? { tip } : { error: tip });
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
  }, [onExchange]);

  const startListening = useCallback(async () => {
    if (sendingRef.current) return;
    setHint(null);
    audioPlayback.stop();
    try {
      socketRef.current?.interrupt();
    } catch {
      /* ignore */
    }

    setPhase('listening');
    assistantAccRef.current = '';
    // Keep last transcripts visible until new ones arrive

    try {
      await ensureSocket();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          channelCount: 1,
        },
      });
      mediaStreamRef.current = stream;
      const mime = pickRecorderMime();
      const recorder = mime
        ? new MediaRecorder(stream, { mimeType: mime })
        : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];
      recordStartedAtRef.current = Date.now();
      recorder.ondataavailable = (e) => {
        if (e.data.size) chunksRef.current.push(e.data);
      };
      recorder.start();

      clearMaxTimer();
      maxTimerRef.current = window.setTimeout(() => {
        void finishRef.current();
      }, MAX_RECORD_MS);

      // User already released while mic was arming
      if (!holdingRef.current) {
        void finishRef.current();
      }
    } catch (err) {
      const msg =
        err instanceof Error && /Permission|NotAllowed/i.test(err.message)
          ? 'Micro non autorisé. Autorisez l’accès au micro dans le navigateur.'
          : 'Impossible d’accéder au micro.';
      setHint(msg);
      onExchange({ error: msg });
      setPhase('idle');
      stopRecorder();
    }
  }, [clearMaxTimer, ensureSocket, onExchange, stopRecorder]);

  const finishListeningAndSend = useCallback(async () => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || sendingRef.current) return;

    const elapsed = Date.now() - recordStartedAtRef.current;
    if (elapsed < MIN_RECORD_MS) {
      const tip =
        'Enregistrement trop court. Maintenez un peu plus longtemps, puis renvoyez.';
      setHint(tip);
      stopRecorder();
      chunksRef.current = [];
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

    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    mediaStreamRef.current = null;
    mediaRecorderRef.current = null;

    const mime =
      (recorder.mimeType || 'audio/webm').split(';')[0] || 'audio/webm';
    const blob = new Blob(chunksRef.current, { type: mime });
    chunksRef.current = [];

    if (blob.size < 1200) {
      const tip = 'Je n’ai rien entendu. Appuyez pour réessayer.';
      setHint(tip);
      sendingRef.current = false;
      setPhase('idle');
      return;
    }

    try {
      const socket = await ensureSocket();
      const b64 = await blobToBase64(blob);
      socket.sendAudioBase64(b64, mime, locale);
    } catch (err) {
      const tip =
        err instanceof Error
          ? err.message
          : 'Envoi vocal impossible. Réessayez.';
      setHint(tip);
      onExchange({ error: tip });
      sendingRef.current = false;
      setPhase('idle');
    }
  }, [clearMaxTimer, ensureSocket, locale, onExchange, stopRecorder]);

  useEffect(() => {
    finishRef.current = finishListeningAndSend;
  }, [finishListeningAndSend]);

  const onOrbPress = useCallback(() => {
    if (phase === 'thinking') return;
    if (phase === 'speaking') {
      audioPlayback.stop();
      try {
        socketRef.current?.interrupt();
      } catch {
        /* ignore */
      }
      // After interrupt, wait for hold to speak again
      setPhase('idle');
      setHint(null);
    }
  }, [phase]);

  const onOrbPointerDown = useCallback(
    (e: PointerEvent<HTMLButtonElement>) => {
      if (phase === 'thinking' || phase === 'speaking') return;
      holdingRef.current = true;
      e.currentTarget.setPointerCapture(e.pointerId);
      void startListening();
    },
    [phase, startListening],
  );

  const onOrbPointerUp = useCallback(
    (e: PointerEvent<HTMLButtonElement>) => {
      holdingRef.current = false;
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
      if (phaseRef.current === 'listening') {
        void finishListeningAndSend();
      }
    },
    [finishListeningAndSend],
  );

  const onOrbPointerCancel = useCallback(() => {
    holdingRef.current = false;
    if (phaseRef.current === 'listening') {
      stopRecorder();
      chunksRef.current = [];
      setPhase('idle');
      setHint('Enregistrement annulé.');
    }
  }, [stopRecorder]);

  // Reset / cleanup when closing — keep shutdown out of deps to avoid
  // re-running cleanup on every callback identity change while open.
  useEffect(() => {
    shutdownRef.current = shutdown;
  }, [shutdown]);

  useEffect(() => {
    if (!open) {
      shutdownRef.current();
      setUserText('');
      setAssistantText('');
      setHint(null);
      return;
    }
    setPhase('idle');
    setHint(null);
    return () => {
      shutdownRef.current();
    };
  }, [open]);

  // Escape to close
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
            onPointerDown={onOrbPointerDown}
            onPointerUp={onOrbPointerUp}
            onPointerCancel={onOrbPointerCancel}
            onContextMenu={(e) => e.preventDefault()}
            disabled={phase === 'thinking'}
            aria-label={copy.action}
            className={`relative flex h-36 w-36 touch-none items-center justify-center rounded-full shadow-[0_0_0_12px_rgba(214,168,79,0.15)] transition select-none disabled:cursor-wait disabled:opacity-70 md:h-44 md:w-44 ${
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
            Les échanges restent aussi dans le chat quand vous fermez.
          </p>
        </div>
      </div>
    </div>,
    document.body,
  );
}
