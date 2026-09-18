import { useCallback, useEffect, useRef, useState } from 'react';
import {
  createAudioPlayer,
  setAudioModeAsync,
  type AudioPlayer,
} from 'expo-audio';
import { File, Paths } from 'expo-file-system';
import * as Speech from 'expo-speech';
import { Platform } from 'react-native';

import { synthesizeSpeech } from '../services/api';

// Fish Audio synthesis time grows with the text, so speak in chunks: the first
// sentence starts playing while the rest is still being synthesized.
const MAX_SEGMENT_CHARS = 180;

// Tiny silent WAV — played inside a user gesture to unlock Safari/Chrome autoplay.
const SILENT_WAV =
  'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=';

function cleanForSpeech(text: string): string {
  return text
    .replace(/\*\*/g, '')
    .replace(/`+/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function splitForSpeech(text: string): string[] {
  const sentences = text.match(/[^.!?…]+[.!?…]*/g) ?? [text];
  const segments: string[] = [];
  let current = '';

  for (const sentence of sentences) {
    const piece = sentence.trim();
    if (!piece) {
      continue;
    }
    if (!current) {
      current = piece;
    } else if (current.length + piece.length + 1 <= MAX_SEGMENT_CHARS) {
      current = `${current} ${piece}`;
    } else {
      segments.push(current);
      current = piece;
    }
  }
  if (current) {
    segments.push(current);
  }
  return segments.length > 0 ? segments : [text];
}

function speakOnDevice(cleaned: string): Promise<void> {
  return new Promise<void>((resolve) => {
    Speech.speak(cleaned, {
      language: 'fr-FR',
      rate: 0.96,
      pitch: 1.0,
      onDone: () => resolve(),
      onStopped: () => resolve(),
      onError: () => resolve(),
    });
  });
}

async function synthesizeOrNull(text: string): Promise<ArrayBuffer | null> {
  try {
    return await synthesizeSpeech(text);
  } catch {
    return null;
  }
}

export function useSpeechPlayback() {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const playerRef = useRef<AudioPlayer | null>(null);
  const cancelledRef = useRef(false);
  const webAudioRef = useRef<HTMLAudioElement | null>(null);
  const webUnlockedRef = useRef(false);
  const pendingBlobUrlRef = useRef<string | null>(null);

  const stop = useCallback(() => {
    cancelledRef.current = true;
    Speech.stop();
    if (webAudioRef.current) {
      try {
        webAudioRef.current.pause();
        webAudioRef.current.removeAttribute('src');
        webAudioRef.current.load();
      } catch {
        // ignore
      }
    }
    if (pendingBlobUrlRef.current) {
      URL.revokeObjectURL(pendingBlobUrlRef.current);
      pendingBlobUrlRef.current = null;
    }
    const player = playerRef.current;
    playerRef.current = null;
    if (player) {
      try {
        player.pause();
        player.remove();
      } catch {
        // ignore
      }
    }
    setIsSpeaking(false);
  }, []);

  /** Must be called during a click/tap so later TTS autoplay is allowed. */
  const unlockWebAudio = useCallback(async () => {
    if (Platform.OS !== 'web') {
      return;
    }
    try {
      const AudioCtor = (globalThis as { Audio?: typeof Audio }).Audio;
      if (!AudioCtor) {
        return;
      }
      if (!webAudioRef.current) {
        webAudioRef.current = new AudioCtor();
        webAudioRef.current.preload = 'auto';
      }
      const element = webAudioRef.current;
      // Keep a near-silent loop alive so Safari still allows later src swaps.
      element.loop = true;
      element.src = SILENT_WAV;
      element.volume = 0.001;
      await element.play();
      webUnlockedRef.current = true;
    } catch {
      // Autoplay policies vary; speak() will still try.
    }
  }, []);

  const playBytes = useCallback(async (audio: ArrayBuffer, index: number) => {
    if (Platform.OS === 'web') {
      const AudioCtor = (globalThis as { Audio?: typeof Audio }).Audio;
      if (!AudioCtor) {
        throw new Error('Audio non disponible');
      }
      if (!webAudioRef.current) {
        webAudioRef.current = new AudioCtor();
        webAudioRef.current.preload = 'auto';
      }
      const element = webAudioRef.current;
      if (pendingBlobUrlRef.current) {
        URL.revokeObjectURL(pendingBlobUrlRef.current);
        pendingBlobUrlRef.current = null;
      }
      const blob = new Blob([audio], { type: 'audio/mpeg' });
      const url = URL.createObjectURL(blob);
      pendingBlobUrlRef.current = url;

      await new Promise<void>((resolve, reject) => {
        const cleanup = () => {
          element.onended = null;
          element.onerror = null;
          element.loop = false;
          if (pendingBlobUrlRef.current === url) {
            URL.revokeObjectURL(url);
            pendingBlobUrlRef.current = null;
          }
        };
        element.onended = () => {
          cleanup();
          // Re-arm silent loop so the next sentence can autoplay too.
          try {
            element.loop = true;
            element.src = SILENT_WAV;
            element.volume = 0.001;
            void element.play();
          } catch {
            // ignore
          }
          resolve();
        };
        element.onerror = () => {
          cleanup();
          reject(new Error('Lecture audio impossible'));
        };
        element.loop = false;
        element.volume = 1;
        element.src = url;
        const playAttempt = element.play();
        if (playAttempt && typeof playAttempt.then === 'function') {
          playAttempt.catch(async (error) => {
            try {
              element.loop = true;
              element.src = SILENT_WAV;
              element.volume = 0.001;
              await element.play();
              element.loop = false;
              element.volume = 1;
              element.src = url;
              await element.play();
            } catch {
              cleanup();
              reject(error);
            }
          });
        }
      });
      return;
    }

    const file = new File(Paths.cache, `tts-${Date.now()}-${index}.mp3`);
    file.create({ overwrite: true });
    file.write(new Uint8Array(audio));

    const player = createAudioPlayer({ uri: file.uri });
    playerRef.current = player;

    try {
      await new Promise<void>((resolve, reject) => {
        const subscription = player.addListener(
          'playbackStatusUpdate',
          (status) => {
            if (status.error) {
              subscription.remove();
              reject(new Error(status.error));
              return;
            }
            if (status.didJustFinish) {
              subscription.remove();
              resolve();
            }
          },
        );
        player.play();
      });
    } finally {
      playerRef.current = null;
      try {
        player.remove();
      } catch {
        // ignore
      }
      try {
        if (file.exists) {
          file.delete();
        }
      } catch {
        // ignore
      }
    }
  }, []);

  const speak = useCallback(
    async (text: string) => {
      const cleaned = cleanForSpeech(text);
      if (!cleaned) {
        return;
      }

      stop();
      cancelledRef.current = false;
      setIsSpeaking(true);

      const segments = splitForSpeech(cleaned);
      let played = 0;

      try {
        await setAudioModeAsync({
          playsInSilentMode: true,
          allowsRecording: false,
        });

        // Warm the first Fish request ASAP so playback starts sooner.
        let pending = synthesizeOrNull(segments[0]);
        for (let index = 0; index < segments.length; index += 1) {
          const audio = await pending;
          if (cancelledRef.current) {
            return;
          }

          pending =
            index + 1 < segments.length
              ? synthesizeOrNull(segments[index + 1])
              : Promise.resolve(null);

          if (!audio) {
            if (Platform.OS === 'web') {
              const retry = await synthesizeOrNull(segments[index]);
              if (retry) {
                await playBytes(retry, index);
                played += 1;
                continue;
              }
            }
            const remaining = segments.slice(index).join(' ');
            await speakOnDevice(remaining);
            return;
          }

          await playBytes(audio, index);
          played += 1;
          if (cancelledRef.current) {
            return;
          }
        }
      } catch {
        if (!cancelledRef.current && played === 0) {
          if (Platform.OS === 'web') {
            const retry = await synthesizeOrNull(cleaned);
            if (retry) {
              try {
                await playBytes(retry, 0);
                return;
              } catch {
                // fall through
              }
            }
          }
          await speakOnDevice(cleaned);
        }
      } finally {
        if (!cancelledRef.current) {
          setIsSpeaking(false);
        }
      }
    },
    [playBytes, stop],
  );

  useEffect(
    () => () => {
      stop();
    },
    [stop],
  );

  const playBase64Mp3 = useCallback(
    async (base64: string, index: number) => {
      const decode =
        typeof atob === 'function'
          ? (value: string) => atob(value)
          : (value: string) => {
              const chars =
                'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
              const cleaned = value.replace(/=+$/, '');
              let output = '';
              for (let i = 0; i < cleaned.length; i += 4) {
                const enc1 = chars.indexOf(cleaned.charAt(i));
                const enc2 = chars.indexOf(cleaned.charAt(i + 1));
                const enc3 = chars.indexOf(cleaned.charAt(i + 2));
                const enc4 = chars.indexOf(cleaned.charAt(i + 3));
                const bits = (enc1 << 18) | (enc2 << 12) | (enc3 << 6) | enc4;
                output += String.fromCharCode((bits >> 16) & 255);
                if (enc3 !== -1 && cleaned.charAt(i + 2) !== '') {
                  output += String.fromCharCode((bits >> 8) & 255);
                }
                if (enc4 !== -1 && cleaned.charAt(i + 3) !== '') {
                  output += String.fromCharCode(bits & 255);
                }
              }
              return output;
            };
      const binary = decode(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
      }
      await playBytes(
        bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
        index,
      );
    },
    [playBytes],
  );

  return {
    isSpeaking,
    speak,
    stop,
    playBase64Mp3,
    unlockWebAudio,
  };
}
