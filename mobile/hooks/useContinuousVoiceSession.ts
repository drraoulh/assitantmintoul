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
  OrderedVoiceScheduler,
  concatParts,
  supportsMediaSourceMp3,
  type VoiceStreamMetrics,
} from '../services/voiceEarlyPlayback';
import { ProgressiveMp3Player } from '../services/voiceStreamPlayer';
import {
  VoiceSocket,
  uriToBase64,
  type VoiceServerEvent,
} from '../services/voiceSocket';
import { mimeFromRecordingUri } from '../utils/audioMime';
import { Platform } from 'react-native';

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
  const schedulerRef = useRef(new OrderedVoiceScheduler(true));
  const streamPlayerRef = useRef<ProgressiveMp3Player | null>(null);
  const streamIdleResolveRef = useRef<(() => void) | null>(null);
  const streamIdlePromiseRef = useRef<Promise<void>>(Promise.resolve());
  /** Server finished generating this turn (turn_done). Needed so inter-sentence
   * gaps do not look "idle" and re-arm the mic mid-reply. */
  const turnGenerationDoneRef = useRef(false);
  const progressiveCapableRef = useRef(
    Platform.OS === 'web' && supportsMediaSourceMp3(),
  );
  const streamMetricsRef = useRef<VoiceStreamMetrics>({});
  const turnResolveRef = useRef<(() => void) | null>(null);
  const turnRejectRef = useRef<((error: Error) => void) | null>(null);
  const userTextRef = useRef('');
  const assistantAccRef = useRef('');
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
    firstSpeech?: number;
    firstPlayCommand?: number;
    firstActuallyPlayed?: number;
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

  const logTtfa = useCallback(
    (event: string, extra?: Record<string, number | string | undefined>) => {
      const perf = clientPerfRef.current;
      const base = perf?.sendStart ?? perf?.recordEnd ?? Date.now();
      console.info(
        '[TTFA TRACE]',
        JSON.stringify({
          event,
          turn_id: perf?.turnId,
          elapsed_from_send_ms: Date.now() - base,
          ...extra,
        }),
      );
    },
    [],
  );

  const resetVoiceStream = useCallback(() => {
    streamPlayerRef.current?.stop();
    streamPlayerRef.current = null;
    schedulerRef.current.reset();
    audioBuffersRef.current.clear();
    playChainRef.current = Promise.resolve();
    streamMetricsRef.current = {};
    turnGenerationDoneRef.current = false;
    streamIdleResolveRef.current?.();
    streamIdleResolveRef.current = null;
    streamIdlePromiseRef.current = Promise.resolve();
  }, []);

  const armStreamIdle = useCallback(() => {
    turnGenerationDoneRef.current = false;
    let resolveIdle: (() => void) | null = null;
    streamIdlePromiseRef.current = new Promise<void>((resolve) => {
      resolveIdle = resolve;
    });
    streamIdleResolveRef.current = () => {
      resolveIdle?.();
      streamIdleResolveRef.current = null;
    };
  }, []);

  const maybeResolveStreamIdle = useCallback(() => {
    if (!turnGenerationDoneRef.current) {
      return;
    }
    if (schedulerRef.current.currentPlaying != null) {
      return;
    }
    if (schedulerRef.current.sequences.size > 0) {
      return;
    }
    streamIdleResolveRef.current?.();
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

  const applyPlayActionRef = useRef<
    (action: ReturnType<OrderedVoiceScheduler['onChunk']>) => Promise<void>
  >(async () => undefined);

  const applyPlayAction = useCallback(
    async (action: ReturnType<OrderedVoiceScheduler['onChunk']>) => {
      if (action.type === 'none') {
        return;
      }
      const perf = clientPerfRef.current;
      const progressive = progressiveCapableRef.current;

      if (action.type === 'start') {
        setSessionPhase('speaking', t('voice.speakingInterrupt'));
        busyRef.current = false;

        if (perf && perf.firstPlayCommand == null && action.index === 0) {
          const now = Date.now();
          perf.firstPlayCommand = now;
          streamMetricsRef.current.frontend_play_start = now;
          if (streamMetricsRef.current.frontend_audio_received_seq0 != null) {
            streamMetricsRef.current.receive_to_play_start_ms =
              now - streamMetricsRef.current.frontend_audio_received_seq0;
          }
          const base = perf.sendStart ?? perf.recordEnd ?? now;
          streamMetricsRef.current.time_to_first_play_ms = now - base;
          logTtfa('frontend_play_start', {
            sequence_id: action.index,
            receive_to_play_start_ms:
              streamMetricsRef.current.receive_to_play_start_ms,
            time_to_first_play_ms: streamMetricsRef.current.time_to_first_play_ms,
            progressive: progressive ? 1 : 0,
          });
          logClientPerf('frontend_play_start', {
            receive_to_play_start_ms:
              streamMetricsRef.current.receive_to_play_start_ms ?? -1,
            time_to_first_play_ms:
              streamMetricsRef.current.time_to_first_play_ms ?? -1,
          });
        }

        if (progressive && Platform.OS === 'web') {
          const player = new ProgressiveMp3Player({
            onPlayStart: (index) => {
              logTtfa('audio_player_start', { sequence_id: index });
            },
            onFirstAudible: (index) => {
              const now = Date.now();
              if (perf && perf.firstActuallyPlayed == null && index === 0) {
                perf.firstActuallyPlayed = now;
                perf.firstSpeech = now;
                streamMetricsRef.current.frontend_first_audio_played = now;
                logTtfa('frontend_first_audio_played', {
                  sequence_id: index,
                  since_receive_ms:
                    streamMetricsRef.current.frontend_audio_received_seq0 != null
                      ? now - streamMetricsRef.current.frontend_audio_received_seq0
                      : undefined,
                });
                logClientPerf('frontend_first_audio_played');
              }
            },
            onEnded: (index) => {
              const next = schedulerRef.current.onPlaybackFinished(
                index,
                progressiveCapableRef.current,
              );
              void applyPlayActionRef.current(next).then(() => {
                maybeResolveStreamIdle();
              });
            },
            onError: () => {
              // Hard failure — do not wait for turn_done / remaining sequences.
              streamIdleResolveRef.current?.();
            },
          });
          streamPlayerRef.current = player;
          try {
            await player.start(action.index, action.bytes, true);
          } catch {
            streamPlayerRef.current = null;
            if (playBase64Mp3) {
              const base64 = bytesToBase64([action.bytes]);
              playChainRef.current = playChainRef.current
                .then(async () => {
                  if (!activeRef.current) {
                    return;
                  }
                  await playBase64Mp3(base64, action.index);
                  const next = schedulerRef.current.onPlaybackFinished(
                    action.index,
                    false,
                  );
                  await applyPlayActionRef.current(next);
                  maybeResolveStreamIdle();
                })
                .catch(() => undefined);
            }
          }
          return;
        }

        if (!playBase64Mp3) {
          return;
        }
        const parts = audioBuffersRef.current.get(action.index) || [action.bytes];
        const merged = parts.length === 1 ? action.bytes : concatParts(parts);
        audioBuffersRef.current.delete(action.index);
        const base64 = bytesToBase64([merged]);
        playChainRef.current = playChainRef.current
          .then(async () => {
            if (!activeRef.current || phaseRef.current === 'idle') {
              return;
            }
            await playBase64Mp3(base64, action.index);
            if (perf && perf.firstActuallyPlayed == null && action.index === 0) {
              perf.firstActuallyPlayed = Date.now();
              perf.firstSpeech = perf.firstActuallyPlayed;
              streamMetricsRef.current.frontend_first_audio_played =
                perf.firstActuallyPlayed;
            }
            const next = schedulerRef.current.onPlaybackFinished(action.index, false);
            await applyPlayActionRef.current(next);
            maybeResolveStreamIdle();
          })
          .catch(() => undefined);
        return;
      }

      if (action.type === 'append') {
        streamPlayerRef.current?.append(action.bytes);
        return;
      }

      if (action.type === 'end') {
        streamPlayerRef.current?.end();
      }
    },
    [
      bytesToBase64,
      logClientPerf,
      logTtfa,
      maybeResolveStreamIdle,
      playBase64Mp3,
      setSessionPhase,
      t,
    ],
  );

  useEffect(() => {
    applyPlayActionRef.current = applyPlayAction;
  }, [applyPlayAction]);

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
            // Do not regress speaking → thinking while early-play audio is out;
            // token-level "generating" used to flip the UI and invite mic re-arm.
            if (phaseRef.current !== 'speaking') {
              setSessionPhase('thinking', t('voice.thinkingShort'));
            }
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
          const receiveTs =
            (event as VoiceServerEvent & { frontend_receive_timestamp?: number })
              .frontend_receive_timestamp ?? Date.now();
          const seq = event.sequence_id ?? event.index;
          if (perf && perf.firstAudioChunk == null) {
            perf.firstAudioChunk = receiveTs;
            streamMetricsRef.current.frontend_audio_received_seq0 = receiveTs;
            logClientPerf('first_audio_chunk');
            logTtfa('frontend_audio_received_seq0', {
              sequence_id: seq,
              part: event.part ?? 0,
              backend_send_timestamp: event.backend_send_timestamp,
              backend_to_frontend_ms:
                typeof event.backend_send_timestamp === 'number'
                  ? Math.round(receiveTs - event.backend_send_timestamp * 1000)
                  : undefined,
            });
            setSessionPhase('speaking', t('voice.speakingInterrupt'));
            busyRef.current = false;
          }
          if (!playBase64Mp3) {
            break;
          }
          try {
            logTtfa('audio_decode_start', { sequence_id: seq, part: event.part ?? 0 });
            const part = decodeBase64ToBytes(event.data);
            logTtfa('audio_decode_end', {
              sequence_id: seq,
              bytes: part.byteLength,
            });
            const prev = audioBuffersRef.current.get(event.index) || [];
            prev.push(part);
            audioBuffersRef.current.set(event.index, prev);
            logTtfa('audio_queue_push', {
              sequence_id: seq,
              buffered_parts: prev.length,
            });
            const progressive = progressiveCapableRef.current;
            const action = schedulerRef.current.onChunk(
              event.index,
              part,
              progressive,
            );
            void applyPlayAction(action);
          } catch {
            // ignore bad chunk
          }
          break;
        }
        case 'audio_done': {
          const now = Date.now();
          if (perf) {
            perf.audioDone = now;
          }
          if (streamMetricsRef.current.audio_done_received == null) {
            streamMetricsRef.current.audio_done_received = now;
            if (streamMetricsRef.current.frontend_play_start != null) {
              streamMetricsRef.current.play_start_to_audio_done_ms =
                now - streamMetricsRef.current.frontend_play_start;
            }
          }
          logClientPerf('audio_done');
          logTtfa('audio_done_received', {
            sequence_id: event.sequence_id ?? event.index,
            wait_after_first_chunk_ms:
              perf?.firstAudioChunk != null ? now - perf.firstAudioChunk : undefined,
            play_start_to_audio_done_ms:
              streamMetricsRef.current.play_start_to_audio_done_ms,
            // Generation finished — does NOT start playback.
            note: 'generation_complete_only',
          });
          if (!playBase64Mp3) {
            break;
          }
          const progressive = progressiveCapableRef.current;
          const action = schedulerRef.current.onDone(event.index, progressive);
          void applyPlayAction(action);
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
          turnGenerationDoneRef.current = true;
          // Unblock when generation is done and nothing is left to play
          // (including the no-audio case). Inter-sentence gaps must NOT idle.
          maybeResolveStreamIdle();
          // Wait for stream idle only — playChain is often already resolved on
          // the progressive MSE path, so racing it finished the turn mid-speech.
          void streamIdlePromiseRef.current.finally(() => {
            turnResolveRef.current?.();
            turnResolveRef.current = null;
            turnRejectRef.current = null;
          });
          break;
        }
        case 'interrupted': {
          const turnPending = turnResolveRef.current != null;
          const hadPlayback = schedulerRef.current.hasStartedPlayback;
          resetVoiceStream();
          if (turnPending && !hadPlayback) {
            // Spurious cancel before first audio — keep waiting for this turn.
            armStreamIdle();
            break;
          }
          turnResolveRef.current?.();
          turnResolveRef.current = null;
          turnRejectRef.current = null;
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
    [
      applyPlayAction,
      armStreamIdle,
      bytesToBase64,
      decodeBase64ToBytes,
      logClientPerf,
      logTtfa,
      maybeResolveStreamIdle,
      onExchange,
      playBase64Mp3,
      resetVoiceStream,
      setSessionPhase,
      t,
    ],
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
    resetVoiceStream();
    socketRef.current?.interrupt();
    socketRef.current?.close();
    socketRef.current = null;
    await stopRecorderSafe();
    setMicReady(false);
    setSessionPhase('idle', t('voice.closed'));
  }, [resetVoiceStream, setSessionPhase, stopRecorderSafe, stopSpeaking, t]);

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
      resetVoiceStream();
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
  }, [armRecorder, errorText, recorder, resetVoiceStream, setSessionPhase, stopSpeaking, t]);

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

      resetVoiceStream();
      armStreamIdle();
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
      // Progressive MSE does not advance playChain — only streamIdle tracks
      // audible completion. Racing a resolved playChain cut TTS mid-sentence
      // by re-arming the mic (stopSpeaking / allowsRecording duck).
      await Promise.race([
        streamIdlePromiseRef.current,
        new Promise<void>((resolve) => setTimeout(resolve, 120_000)),
      ]);
      if (streamMetricsRef.current.time_to_first_play_ms != null) {
        logClientPerf('time_to_first_play', {
          time_to_first_play_ms: streamMetricsRef.current.time_to_first_play_ms,
          receive_to_play_start_ms:
            streamMetricsRef.current.receive_to_play_start_ms ?? -1,
          play_start_to_audio_done_ms:
            streamMetricsRef.current.play_start_to_audio_done_ms ?? -1,
        });
      }
      if (!activeRef.current) {
        return;
      }
      await finishTurn(t('voice.idleHint'));
    },
    [
      armStreamIdle,
      finishTurn,
      locale,
      logClientPerf,
      recorder.uri,
      resetVoiceStream,
      setSessionPhase,
      t,
    ],
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
