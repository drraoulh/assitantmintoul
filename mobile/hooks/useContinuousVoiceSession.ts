import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';

import { useLocale } from '../i18n';
import { ApiError, transcribeAudio } from '../services/api';
import {
  VoiceSocket,
  uriToBase64,
  type VoiceServerEvent,
} from '../services/voiceSocket';
import { mimeFromRecordingUri } from '../utils/audioMime';

export type VoiceSessionPhase =
  | 'idle'
  | 'listening'
  | 'transcribing'
  | 'thinking'
  | 'speaking';

interface UseContinuousVoiceSessionOptions {
  active: boolean;
  sendMessage: (text: string) => Promise<string | null>;
  speak: (text: string) => Promise<void>;
  stopSpeaking: () => void;
  playBase64Mp3?: (base64: string, index: number) => Promise<void>;
  onExchange?: (userText: string, assistantText: string) => void;
}

export function useContinuousVoiceSession({
  active,
  sendMessage,
  speak,
  stopSpeaking,
  playBase64Mp3,
  onExchange,
}: UseContinuousVoiceSessionOptions) {
  const { locale, t } = useLocale();
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(recorder);

  const [phase, setPhase] = useState<VoiceSessionPhase>('idle');
  const [lastUserText, setLastUserText] = useState('');
  const [lastAssistantText, setLastAssistantText] = useState('');
  const [statusHint, setStatusHint] = useState(() => t('voice.idleHint'));

  const errorText = useCallback(
    (error: unknown): string => {
      if (error instanceof ApiError) {
        return error.message;
      }
      if (error instanceof Error && error.message) {
        return error.message;
      }
      return t('mic.unavailable');
    },
    [t],
  );
  const [handsFree, setHandsFree] = useState(false);
  const [micReady, setMicReady] = useState(false);

  const activeRef = useRef(active);
  const phaseRef = useRef<VoiceSessionPhase>('idle');
  const busyRef = useRef(false);
  const handsFreeRef = useRef(false);
  const preparedRef = useRef(false);
  const startListeningRef = useRef<() => Promise<void>>(async () => undefined);
  const socketRef = useRef<VoiceSocket | null>(null);
  const audioBuffersRef = useRef<Map<number, Uint8Array[]>>(new Map());
  const playChainRef = useRef(Promise.resolve());
  const clientPerfRef = useRef<{
    turnId: string;
    recordStart?: number;
    recordEnd?: number;
    sendStart?: number;
    firstToken?: number;
    assistantText?: number;
    firstAudioChunk?: number;
    audioDone?: number;
    turnDone?: number;
  } | null>(null);

  const logClientPerf = useCallback((label: string, extra?: Record<string, number>) => {
    const perf = clientPerfRef.current;
    if (!perf) {
      return;
    }
    const base = perf.sendStart ?? perf.recordEnd ?? perf.recordStart ?? Date.now();
    const line = {
      turnId: perf.turnId,
      label,
      sinceSendMs: Date.now() - base,
      ...extra,
    };
    // No secrets / no audio payloads — diagnostics only.
    console.info('[VOICE CLIENT PERF]', JSON.stringify(line));
  }, []);

  useEffect(() => {
    if (phaseRef.current === 'idle') {
      setStatusHint(t('voice.idleHint'));
    }
  }, [locale, t]);

  const decodeBase64ToBytes = useCallback((value: string): Uint8Array => {
    const binary =
      typeof atob === 'function'
        ? atob(value)
        : (() => {
            throw new Error('Base64 decode unavailable');
          })();
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  }, []);

  const bytesToBase64 = useCallback((chunks: Uint8Array[]): string => {
    let total = 0;
    for (const chunk of chunks) {
      total += chunk.length;
    }
    const merged = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }
    let binary = '';
    const step = 0x8000;
    for (let i = 0; i < merged.length; i += step) {
      binary += String.fromCharCode(...merged.subarray(i, i + step));
    }
    return btoa(binary);
  }, []);

  const setSessionPhase = useCallback((next: VoiceSessionPhase, hint: string) => {
    phaseRef.current = next;
    setPhase(next);
    setStatusHint(hint);
  }, []);

  const stopRecorderSafe = useCallback(async () => {
    try {
      if (recorder.getStatus().isRecording) {
        await recorder.stop();
      }
    } catch {
      // Recorder may already be stopped.
    }
    preparedRef.current = false;
  }, [recorder]);

  const handleSocketEvent = useCallback(
    (event: VoiceServerEvent) => {
      if (!activeRef.current) {
        return;
      }
      const perf = clientPerfRef.current;

      switch (event.type) {
        case 'status': {
          if (event.phase === 'transcribing') {
            setSessionPhase('transcribing', t('voice.understanding'));
          } else if (
            event.phase === 'thinking' ||
            event.phase === 'retrieving' ||
            event.phase === 'generating'
          ) {
            setSessionPhase('thinking', t('voice.thinkingShort'));
          } else if (event.phase === 'speaking') {
            setSessionPhase('speaking', t('voice.speakingInterrupt'));
            busyRef.current = false;
          }
          break;
        }
        case 'transcript': {
          const text = (event.text || '').trim();
          userTextRef.current = text;
          setLastUserText(text);
          logClientPerf('transcript');
          break;
        }
        case 'token': {
          if (perf && perf.firstToken == null) {
            perf.firstToken = Date.now();
            logClientPerf('first_token');
          }
          assistantAccRef.current += event.text || '';
          setLastAssistantText(assistantAccRef.current);
          break;
        }
        case 'assistant_text': {
          if (perf) {
            perf.assistantText = Date.now();
          }
          logClientPerf('assistant_text');
          assistantAccRef.current = event.text || assistantAccRef.current;
          setLastAssistantText(assistantAccRef.current);
          break;
        }
        case 'audio_chunk': {
          if (perf && perf.firstAudioChunk == null) {
            perf.firstAudioChunk = Date.now();
            logClientPerf('first_audio_chunk');
            // Phase 1.2: flip UI to speaking as soon as first bytes arrive —
            // do not wait for the full sentence MP3 (audio_done).
            setSessionPhase('speaking', t('voice.speakingInterrupt'));
            busyRef.current = false;
          }
          if (!playBase64Mp3) {
            break;
          }
          try {
            const part = decodeBase64ToBytes(event.data);
            const prev = audioBuffersRef.current.get(event.index) || [];
            prev.push(part);
            audioBuffersRef.current.set(event.index, prev);
          } catch {
            // ignore bad chunk
          }
          break;
        }
        case 'audio_done': {
          if (perf) {
            perf.audioDone = Date.now();
            if (perf.firstAudioChunk != null && (perf as { firstSpeech?: number }).firstSpeech == null) {
              (perf as { firstSpeech?: number }).firstSpeech = Date.now();
              logClientPerf('first_speech_play', {
                time_to_first_speech_ms:
                  Date.now() - (perf.sendStart ?? perf.recordEnd ?? Date.now()),
              });
            }
          }
          logClientPerf('audio_done');
          if (!playBase64Mp3) {
            break;
          }
          const parts = audioBuffersRef.current.get(event.index) || [];
          audioBuffersRef.current.delete(event.index);
          if (parts.length === 0) {
            break;
          }
          const base64 = bytesToBase64(parts);
          setSessionPhase('speaking', t('voice.speakingInterrupt'));
          busyRef.current = false;
          // Ordered playback chain: sequence 0 → 1 → 2 … (never reorder).
          playChainRef.current = playChainRef.current
            .then(async () => {
              if (!activeRef.current || phaseRef.current === 'idle') {
                return;
              }
              await playBase64Mp3(base64, event.index);
            })
            .catch(() => undefined);
          break;
        }
        case 'turn_done': {
          if (perf) {
            perf.turnDone = Date.now();
          }
          logClientPerf('turn_done');
          const user = userTextRef.current;
          const assistant = assistantAccRef.current;
          if (user && assistant) {
            onExchange?.(user, assistant);
          }
          void playChainRef.current.finally(() => {
            turnResolveRef.current?.();
            turnResolveRef.current = null;
            turnRejectRef.current = null;
          });
          break;
        }
        case 'interrupted': {
          audioBuffersRef.current.clear();
          break;
        }
        case 'error': {
          logClientPerf('error');
          turnRejectRef.current?.(new Error(event.message));
          turnResolveRef.current = null;
          turnRejectRef.current = null;
          break;
        }
        default:
          break;
      }
    },
    [bytesToBase64, decodeBase64ToBytes, logClientPerf, onExchange, playBase64Mp3, setSessionPhase, t],
  );

  const ensureSocket = useCallback(async (): Promise<VoiceSocket | null> => {
    // Prefer WebSocket on all platforms (incl. web). HTTP STT→chat→TTS remains
    // the fallback when connect fails (see processUtterance).
    if (socketRef.current?.ready) {
      return socketRef.current;
    }
    return new Promise((resolve) => {
      let settled = false;
      const socket = new VoiceSocket({
        onEvent: handleSocketEvent,
        onOpen: () => {
          if (!settled) {
            settled = true;
            socketRef.current = socket;
            resolve(socket);
          }
        },
        onError: () => {
          if (!settled) {
            settled = true;
            resolve(null);
          }
        },
        onClose: () => {
          if (socketRef.current === socket) {
            socketRef.current = null;
          }
        },
      });
      socketRef.current = socket;
      try {
        socket.connect();
      } catch {
        resolve(null);
        return;
      }
      setTimeout(() => {
        if (!settled) {
          settled = true;
          resolve(socket.ready ? socket : null);
        }
      }, 2500);
    });
  }, [handleSocketEvent]);

  const shutdown = useCallback(async () => {
    activeRef.current = false;
    busyRef.current = false;
    stopSpeaking();
    socketRef.current?.interrupt();
    socketRef.current?.close();
    socketRef.current = null;
    await stopRecorderSafe();
    setMicReady(false);
    setSessionPhase('idle', t('voice.closed'));
  }, [setSessionPhase, stopRecorderSafe, stopSpeaking, t]);

  const armRecorder = useCallback(async (): Promise<boolean> => {
    if (preparedRef.current) {
      return true;
    }

    const permission = await AudioModule.requestRecordingPermissionsAsync();
    if (!permission.granted) {
      setSessionPhase('idle', t('voice.micDenied'));
      return false;
    }
    if (!activeRef.current) {
      return false;
    }

    await setAudioModeAsync({
      playsInSilentMode: true,
      allowsRecording: true,
    });
    await recorder.prepareToRecordAsync();
    preparedRef.current = true;
    setMicReady(true);
    return true;
  }, [recorder, setSessionPhase, t]);

  const startListening = useCallback(async () => {
    if (!activeRef.current || busyRef.current) {
      return;
    }

    try {
      stopSpeaking();
      socketRef.current?.interrupt();
      const armed = await armRecorder();
      if (!armed || !activeRef.current) {
        return;
      }

      recorder.record();
      clientPerfRef.current = {
        turnId: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
        recordStart: Date.now(),
      };
      console.info('[VOICE CLIENT PERF]', JSON.stringify({ turnId: clientPerfRef.current.turnId, label: 'record_start' }));
      setSessionPhase('listening', t('voice.listeningAction'));
    } catch (error) {
      if (!activeRef.current) {
        return;
      }
      preparedRef.current = false;
      setSessionPhase('idle', errorText(error));
    }
  }, [armRecorder, errorText, recorder, setSessionPhase, stopSpeaking, t]);

  useEffect(() => {
    startListeningRef.current = startListening;
  }, [startListening]);

  const finishTurn = useCallback(
    async (hint: string) => {
      busyRef.current = false;
      if (!activeRef.current) {
        return;
      }
      if (handsFreeRef.current) {
        await startListeningRef.current();
        return;
      }
      void armRecorder();
      setSessionPhase('idle', hint);
    },
    [armRecorder, setSessionPhase],
  );

  const processUtteranceHttp = useCallback(async () => {
    const uri = recorder.uri;
    if (!uri) {
      await finishTurn(t('voice.recordingMissing'));
      return;
    }

    setSessionPhase('transcribing', t('voice.understanding'));
    const result = await transcribeAudio(uri, mimeFromRecordingUri(uri));
    const text = result.text.trim();

    if (!activeRef.current) {
      return;
    }

    if (!text || text === '.') {
      await finishTurn(t('voice.nothingHeard'));
      return;
    }

    setLastUserText(text);
    setSessionPhase('thinking', t('voice.thinkingShort'));
    const reply = await sendMessage(text);

    if (!activeRef.current) {
      return;
    }

    if (!reply) {
      await finishTurn(t('voice.noReply'));
      return;
    }

    setLastAssistantText(reply);
    setSessionPhase('speaking', t('voice.speakingInterrupt'));
    busyRef.current = false;
    await speak(reply);

    if (!activeRef.current || phaseRef.current !== 'speaking') {
      return;
    }

    await finishTurn(t('voice.idleHint'));
  }, [finishTurn, recorder.uri, sendMessage, setSessionPhase, speak, t]);

  const processUtteranceWs = useCallback(
    async (socket: VoiceSocket) => {
      const uri = recorder.uri;
      if (!uri) {
        await finishTurn(t('voice.recordingMissing'));
        return;
      }

      audioBuffersRef.current.clear();
      playChainRef.current = Promise.resolve();
      assistantAccRef.current = '';
      userTextRef.current = '';
      setLastAssistantText('');
      setSessionPhase('transcribing', t('voice.understanding'));

      const turnId =
        clientPerfRef.current?.turnId ||
        `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
      if (!clientPerfRef.current) {
        clientPerfRef.current = { turnId };
      }
      clientPerfRef.current.recordEnd = Date.now();
      logClientPerf('record_end');

      const audioBase64 = await uriToBase64(uri);
      const turnPromise = new Promise<void>((resolve, reject) => {
        turnResolveRef.current = resolve;
        turnRejectRef.current = reject;
      });

      clientPerfRef.current.sendStart = Date.now();
      logClientPerf('send_audio');
      socket.sendAudioBase64(audioBase64, mimeFromRecordingUri(uri), locale, turnId);
      await turnPromise;

      if (!activeRef.current) {
        return;
      }
      await playChainRef.current;
      if (!activeRef.current) {
        return;
      }
      await finishTurn(t('voice.idleHint'));
    },
    [finishTurn, locale, logClientPerf, recorder.uri, setSessionPhase, t],
  );

  const processUtterance = useCallback(async () => {
    if (busyRef.current || !activeRef.current) {
      return;
    }
    busyRef.current = true;

    try {
      if (recorderState.isRecording || phaseRef.current === 'listening') {
        await recorder.stop();
      }
      preparedRef.current = false;

      if (!activeRef.current) {
        return;
      }

      const socket = await ensureSocket();
      if (socket?.ready && playBase64Mp3) {
        try {
          await processUtteranceWs(socket);
          return;
        } catch (error) {
          // Fall through to HTTP path.
          if (!activeRef.current) {
            return;
          }
          setStatusHint(
            error instanceof Error
              ? error.message
              : t('voice.fallbackMode'),
          );
        }
      }

      await processUtteranceHttp();
    } catch (error) {
      if (!activeRef.current) {
        return;
      }
      setSessionPhase('idle', errorText(error));
      busyRef.current = false;
      void armRecorder();
    } finally {
      busyRef.current = false;
    }
  }, [
    armRecorder,
    ensureSocket,
    playBase64Mp3,
    processUtteranceHttp,
    processUtteranceWs,
    recorder,
    recorderState.isRecording,
    setSessionPhase,
    t,
  ]);

  const onOrbPress = useCallback(async () => {
    if (!activeRef.current) {
      return;
    }

    if (phaseRef.current === 'speaking') {
      stopSpeaking();
      socketRef.current?.interrupt();
      setSessionPhase('idle', t('voice.idleHint'));
      await startListeningRef.current();
      return;
    }

    if (phaseRef.current === 'listening' || recorderState.isRecording) {
      await processUtterance();
      return;
    }

    if (
      phaseRef.current === 'transcribing' ||
      phaseRef.current === 'thinking'
    ) {
      return;
    }

    await startListeningRef.current();
  }, [processUtterance, recorderState.isRecording, setSessionPhase, stopSpeaking, t]);

  const toggleHandsFree = useCallback(() => {
    setHandsFree((current) => {
      const next = !current;
      handsFreeRef.current = next;
      return next;
    });
  }, []);

  useEffect(() => {
    activeRef.current = active;

    if (!active) {
      void shutdown();
      return;
    }

    setSessionPhase('idle', t('voice.idleHint'));
    void armRecorder();
    void ensureSocket();

    return () => {
      activeRef.current = false;
      busyRef.current = false;
      stopSpeaking();
      socketRef.current?.close();
      socketRef.current = null;
      void stopRecorderSafe();
    };
    // Intentionally only when `active` flips.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  return {
    phase,
    statusHint,
    lastUserText,
    lastAssistantText,
    isRecording: recorderState.isRecording || phase === 'listening',
    micReady,
    handsFree,
    toggleHandsFree,
    onOrbPress,
    shutdown,
  };
}
