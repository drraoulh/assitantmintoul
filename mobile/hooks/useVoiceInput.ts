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
  // Expo HIGH_QUALITY is usually AAC in an m4a container.
  // Hugging Face rejects audio/mp4 but accepts audio/m4a.
  return 'audio/m4a';
}

export function useVoiceInput(onTranscribed: (text: string) => void) {
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(recorder);
  const [isTranscribing, setIsTranscribing] = useState(false);

  const toggleRecording = useCallback(async () => {
    if (isTranscribing) {
      return;
    }

    if (recorderState.isRecording) {
      try {
        await recorder.stop();
        const uri = recorder.uri;
        if (!uri) {
          Alert.alert('Micro', "L'enregistrement audio est introuvable.");
          return;
        }

        setIsTranscribing(true);
        const result = await transcribeAudio(uri, mimeFromUri(uri));
        const text = result.text.trim();
        if (!text) {
          Alert.alert('Micro', 'Aucune parole détectée. Réessayez.');
          return;
        }
        onTranscribed(text);
      } catch (error) {
        Alert.alert('Micro', errorText(error));
      } finally {
        setIsTranscribing(false);
      }
      return;
    }

    try {
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
    } catch (error) {
      Alert.alert('Micro', errorText(error));
    }
  }, [isTranscribing, onTranscribed, recorder, recorderState.isRecording]);

  return {
    isRecording: recorderState.isRecording,
    isTranscribing,
    toggleRecording,
  };
}
