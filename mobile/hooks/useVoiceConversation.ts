import { useCallback, useState } from 'react';
import { Alert } from 'react-native';
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';

import { ApiError, transcribeAudio } from '../services/api';

export type VoicePhase =
  | 'idle'
  | 'listening'
  | 'transcribing'
  | 'thinking'
  | 'speaking';

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
  if (lower.includes('.webm')) {
    return 'audio/webm';
  }
  if (lower.includes('.wav')) {
    return 'audio/wav';
  }
  if (lower.includes('.mp3')) {
    return 'audio/mpeg';
  }
  if (lower.includes('.caf')) {
    return 'audio/wav';
  }
  return 'audio/m4a';
}

interface UseVoiceConversationOptions {
  disabled?: boolean;
  onStopSpeaking?: () => void;
  onVoiceTurn: (transcript: string) => Promise<void>;
}

export function useVoiceConversation({
  disabled = false,
  onStopSpeaking,
  onVoiceTurn,
}: UseVoiceConversationOptions) {
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(recorder);
  const [phase, setPhase] = useState<VoicePhase>('idle');

  const toggleVoiceTurn = useCallback(async () => {
    if (disabled || phase === 'transcribing' || phase === 'thinking') {
      return;
    }

    if (recorderState.isRecording || phase === 'listening') {
      try {
        await recorder.stop();
        const uri = recorder.uri;
        if (!uri) {
          setPhase('idle');
          Alert.alert('Micro', "L'enregistrement audio est introuvable.");
          return;
        }

        setPhase('transcribing');
        const result = await transcribeAudio(uri, mimeFromUri(uri));
        const text = result.text.trim();
        if (!text || text === '.') {
          setPhase('idle');
          Alert.alert('Micro', 'Aucune parole détectée. Réessayez.');
          return;
        }

        setPhase('thinking');
        await onVoiceTurn(text);
        setPhase('idle');
      } catch (error) {
        setPhase('idle');
        Alert.alert('Micro', errorText(error));
      }
      return;
    }

    try {
      onStopSpeaking?.();
      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) {
        Alert.alert(
          'Micro',
          "Autorisez l'accès au microphone pour poser une question à voix haute.",
        );
        return;
      }

      await setAudioModeAsync({
        playsInSilentMode: true,
        allowsRecording: true,
      });
      await recorder.prepareToRecordAsync();
      recorder.record();
      setPhase('listening');
    } catch (error) {
      setPhase('idle');
      Alert.alert('Micro', errorText(error));
    }
  }, [
    disabled,
    onStopSpeaking,
    onVoiceTurn,
    phase,
    recorder,
    recorderState.isRecording,
  ]);

  return {
    phase,
    setPhase,
    isRecording: recorderState.isRecording || phase === 'listening',
    isBusy:
      phase === 'transcribing' ||
      phase === 'thinking' ||
      phase === 'speaking' ||
      disabled,
    toggleVoiceTurn,
  };
}
