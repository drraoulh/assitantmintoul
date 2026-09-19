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

export function useVoiceInput(onTranscribed: (text: string) => void) {
  const { t } = useLocale();
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(recorder);
  const [isTranscribing, setIsTranscribing] = useState(false);

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

  const toggleRecording = useCallback(async () => {
    if (isTranscribing) {
      return;
    }

    if (recorderState.isRecording) {
      try {
        await recorder.stop();
        const uri = recorder.uri;
        if (!uri) {
          Alert.alert(t('mic.title'), t('mic.missing'));
          return;
        }

        setIsTranscribing(true);
        const result = await transcribeAudio(uri, mimeFromRecordingUri(uri));
        const text = result.text.trim();
        if (!text) {
          Alert.alert(t('mic.title'), t('mic.empty'));
          return;
        }
        onTranscribed(text);
      } catch (error) {
        Alert.alert(t('mic.title'), errorText(error));
      } finally {
        setIsTranscribing(false);
      }
      return;
    }

    try {
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
    } catch (error) {
      Alert.alert(t('mic.title'), errorText(error));
    }
  }, [
    errorText,
    isTranscribing,
    onTranscribed,
    recorder,
    recorderState.isRecording,
    t,
  ]);

  return {
    isRecording: recorderState.isRecording,
    isTranscribing,
    toggleRecording,
  };
}
