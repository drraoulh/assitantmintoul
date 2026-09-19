import { useCallback, useState } from 'react';
import { Alert } from 'react-native';
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';

import { useLocale } from '../i18n';
import { ApiError, transcribeAudio } from '../services/api';
import { mimeFromRecordingUri } from '../utils/audioMime';

export type VoicePhase =
  | 'idle'
  | 'listening'
  | 'transcribing'
  | 'thinking'
  | 'speaking';

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
  const { t } = useLocale();
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(recorder);
  const [phase, setPhase] = useState<VoicePhase>('idle');

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
          Alert.alert(t('mic.title'), t('mic.missing'));
          return;
        }

        setPhase('transcribing');
        const result = await transcribeAudio(uri, mimeFromRecordingUri(uri));
        const text = result.text.trim();
        if (!text || text === '.') {
          setPhase('idle');
          Alert.alert(t('mic.title'), t('mic.empty'));
          return;
        }

        setPhase('thinking');
        await onVoiceTurn(text);
        setPhase('idle');
      } catch (error) {
        setPhase('idle');
        Alert.alert(t('mic.title'), errorText(error));
      }
      return;
    }

    try {
      onStopSpeaking?.();
      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) {
        Alert.alert(t('mic.title'), t('mic.permission'));
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
      Alert.alert(t('mic.title'), errorText(error));
    }
  }, [
    disabled,
    errorText,
    onStopSpeaking,
    onVoiceTurn,
    phase,
    recorder,
    recorderState.isRecording,
    t,
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
