import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert } from 'react-native';
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';

import { ApiError, transcribeAudio } from '../services/api';

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
}

export function useContinuousVoiceSession({
  active,
  sendMessage,
  speak,
  stopSpeaking,
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

  const shutdown = useCallback(async () => {
    activeRef.current = false;
    busyRef.current = false;
    stopSpeaking();
    await stopRecorderSafe();
    setMicReady(false);
    setSessionPhase('idle', 'Mode conversation fermé');
  }, [setSessionPhase, setMicReady, stopRecorderSafe, stopSpeaking]);

  /** Ask for the mic and preload the recorder so a tap starts instantly. */
  const armRecorder = useCallback(async (): Promise<boolean> => {
    if (preparedRef.current) {
      return true;
    }

    const permission = await AudioModule.requestRecordingPermissionsAsync();
    if (!permission.granted) {
      setSessionPhase('idle', 'Micro non autorisé');
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
      const armed = await armRecorder();
      if (!armed || !activeRef.current) {
        return;
      }

      recorder.record();
      setSessionPhase('listening', 'Je vous écoute… appuyez pour envoyer');
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

  /** After a turn: chain straight into listening only in hands-free mode. */
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

      const uri = recorder.uri;
      if (!uri) {
        await finishTurn('Enregistrement introuvable. Appuyez pour réessayer');
        return;
      }

      setSessionPhase('transcribing', 'Je comprends votre question…');
      const result = await transcribeAudio(uri, mimeFromUri(uri));
      const text = result.text.trim();

      if (!activeRef.current) {
        return;
      }

      if (!text || text === '.') {
        await finishTurn('Je n’ai rien entendu. Appuyez pour réessayer');
        return;
      }

      setLastUserText(text);
      setSessionPhase('thinking', 'Je réfléchis…');
      const reply = await sendMessage(text);

      if (!activeRef.current) {
        return;
      }

      if (!reply) {
        await finishTurn('Pas de réponse. Appuyez pour réessayer');
        return;
      }

      setLastAssistantText(reply);
      setSessionPhase('speaking', 'Je vous réponds… appuyez pour m’interrompre');
      busyRef.current = false;
      await speak(reply);

      if (!activeRef.current || phaseRef.current !== 'speaking') {
        return;
      }

      await finishTurn(IDLE_HINT);
    } catch (error) {
      if (!activeRef.current) {
        return;
      }
      setSessionPhase('idle', errorText(error));
      busyRef.current = false;
      Alert.alert('Mode vocal', errorText(error));
      void armRecorder();
    } finally {
      busyRef.current = false;
    }
  }, [
    armRecorder,
    finishTurn,
    recorder,
    recorderState.isRecording,
    sendMessage,
    setSessionPhase,
    speak,
  ]);

  const onOrbPress = useCallback(async () => {
    if (!activeRef.current) {
      return;
    }

    if (phaseRef.current === 'speaking') {
      stopSpeaking();
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

    // Never record on entry: stay idle and only warm up the mic.
    setSessionPhase('idle', IDLE_HINT);
    void armRecorder();

    return () => {
      activeRef.current = false;
      busyRef.current = false;
      stopSpeaking();
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
