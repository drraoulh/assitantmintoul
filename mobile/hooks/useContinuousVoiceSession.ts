import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';

import { ApiError, transcribeAudio } from '../services/api';
import {
  VoiceSocket,
  uriToBase64,
  type VoiceServerEvent,
} from '../services/voiceSocket';
import { Platform } from 'react-native';

export type VoiceSessionPhase =
  | 'idle'
  | 'listening'
  | 'transcribing'
  | 'thinking'
  | 'speaking';

const IDLE_HINT = 'Appuyez sur le micro pour parler';

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Impossible d'utiliser le micro pour le moment.";
}

function mimeFromUri(uri: string | null): string {
  const lower = (uri ?? '').toLowerCase();
  if (lower.includes('.webm')) return 'audio/webm';
  if (lower.includes('.wav')) return 'audio/wav';
  if (lower.includes('.mp3')) return 'audio/mpeg';
  return 'audio/m4a';
}

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
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(recorder);

  const [phase, setPhase] = useState<VoiceSessionPhase>('idle');
  const [lastUserText, setLastUserText] = useState('');
  const [lastAssistantText, setLastAssistantText] = useState('');
  const [statusHint, setStatusHint] = useState(IDLE_HINT);
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
  const turnResolveRef = useRef<(() => void) | null>(null);
  const turnRejectRef = useRef<((error: Error) => void) | null>(null);
  const assistantAccRef = useRef('');
  const userTextRef = useRef('');

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

      switch (event.type) {
        case 'status': {
          if (event.phase === 'transcribing') {
            setSessionPhase('transcribing', 'Je comprends votre question\u2026');
          } else if (
            event.phase === 'thinking' ||
            event.phase === 'retrieving' ||
            event.phase === 'generating'
          ) {
            setSessionPhase('thinking', 'Je r\u00e9fl\u00e9chis\u2026');
          } else if (event.phase === 'speaking') {
            setSessionPhase(
              'speaking',
              'Je vous r\u00e9ponds\u2026 appuyez pour m\u2019interrompre',
            );
            busyRef.current = false;
          }
          break;
        }
        case 'transcript': {
          const text = (event.text || '').trim();
          userTextRef.current = text;
          setLastUserText(text);
          break;
        }
        case 'token': {
          assistantAccRef.current += event.text || '';
          setLastAssistantText(assistantAccRef.current);
          break;
        }
        case 'assistant_text': {
          assistantAccRef.current = event.text || assistantAccRef.current;
          setLastAssistantText(assistantAccRef.current);
          break;
        }
        case 'audio_chunk': {
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
          if (!playBase64Mp3) {
            break;
          }
          const parts = audioBuffersRef.current.get(event.index) || [];
          audioBuffersRef.current.delete(event.index);
          if (parts.length === 0) {
            break;
          }
          const base64 = bytesToBase64(parts);
          setSessionPhase(
            'speaking',
            'Je vous r\u00e9ponds\u2026 appuyez pour m\u2019interrompre',
          );
          busyRef.current = false;
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
          turnRejectRef.current?.(new Error(event.message));
          turnResolveRef.current = null;
          turnRejectRef.current = null;
          break;
        }
        default:
          break;
      }
    },
    [bytesToBase64, decodeBase64ToBytes, onExchange, playBase64Mp3, setSessionPhase],
  );

  const ensureSocket = useCallback(async (): Promise<VoiceSocket | null> => {
    // Web Render API may not expose WS yet; HTTP+Fish TTS is the reliable path.
    if (Platform.OS === 'web') {
      return null;
    }
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
    setSessionPhase('idle', 'Mode conversation ferm\u00e9');
  }, [setSessionPhase, stopRecorderSafe, stopSpeaking]);

  const armRecorder = useCallback(async (): Promise<boolean> => {
    if (preparedRef.current) {
      return true;
    }

    const permission = await AudioModule.requestRecordingPermissionsAsync();
    if (!permission.granted) {
      setSessionPhase('idle', 'Micro non autoris\u00e9');
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
  }, [recorder, setSessionPhase]);

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
      setSessionPhase('listening', 'Je vous \u00e9coute\u2026 appuyez pour envoyer');
    } catch (error) {
      if (!activeRef.current) {
        return;
      }
      preparedRef.current = false;
      setSessionPhase('idle', errorText(error));
    }
  }, [armRecorder, recorder, setSessionPhase, stopSpeaking]);

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
      await finishTurn('Enregistrement introuvable. Appuyez pour r\u00e9essayer');
      return;
    }

    setSessionPhase('transcribing', 'Je comprends votre question\u2026');
    const result = await transcribeAudio(uri, mimeFromUri(uri));
    const text = result.text.trim();

    if (!activeRef.current) {
      return;
    }

    if (!text || text === '.') {
      await finishTurn('Je n\u2019ai rien entendu. Appuyez pour r\u00e9essayer');
      return;
    }

    setLastUserText(text);
    setSessionPhase('thinking', 'Je r\u00e9fl\u00e9chis\u2026');
    const reply = await sendMessage(text);

    if (!activeRef.current) {
      return;
    }

    if (!reply) {
      await finishTurn('Pas de r\u00e9ponse. Appuyez pour r\u00e9essayer');
      return;
    }

    setLastAssistantText(reply);
    setSessionPhase(
      'speaking',
      'Je vous r\u00e9ponds\u2026 appuyez pour m\u2019interrompre',
    );
    busyRef.current = false;
    await speak(reply);

    if (!activeRef.current || phaseRef.current !== 'speaking') {
      return;
    }

    await finishTurn(IDLE_HINT);
  }, [finishTurn, recorder.uri, sendMessage, setSessionPhase, speak]);

  const processUtteranceWs = useCallback(
    async (socket: VoiceSocket) => {
      const uri = recorder.uri;
      if (!uri) {
        await finishTurn('Enregistrement introuvable. Appuyez pour r\u00e9essayer');
        return;
      }

      audioBuffersRef.current.clear();
      playChainRef.current = Promise.resolve();
      assistantAccRef.current = '';
      userTextRef.current = '';
      setLastAssistantText('');
      setSessionPhase('transcribing', 'Je comprends votre question\u2026');

      const audioBase64 = await uriToBase64(uri);
      const turnPromise = new Promise<void>((resolve, reject) => {
        turnResolveRef.current = resolve;
        turnRejectRef.current = reject;
      });

      socket.sendAudioBase64(audioBase64, mimeFromUri(uri));
      await turnPromise;

      if (!activeRef.current) {
        return;
      }
      await playChainRef.current;
      if (!activeRef.current) {
        return;
      }
      await finishTurn(IDLE_HINT);
    },
    [finishTurn, recorder.uri, setSessionPhase],
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
              : 'Bascule vers le mode compatible\u2026',
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
  ]);

  const onOrbPress = useCallback(async () => {
    if (!activeRef.current) {
      return;
    }

    if (phaseRef.current === 'speaking') {
      stopSpeaking();
      socketRef.current?.interrupt();
      setSessionPhase('idle', IDLE_HINT);
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
  }, [processUtterance, recorderState.isRecording, setSessionPhase, stopSpeaking]);

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

    setSessionPhase('idle', IDLE_HINT);
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
