import { useCallback, useEffect, useRef, useState } from 'react';
import {
  createAudioPlayer,
  setAudioModeAsync,
  type AudioPlayer,
} from 'expo-audio';
import { File, Paths } from 'expo-file-system';
import * as Speech from 'expo-speech';
import { Platform } from 'react-native';

import { useLocale } from '../i18n';
import { synthesizeSpeech } from '../services/api';

// Fish TTS latency grows with text length. HTTP fallback speaks short segments
// so the first audible audio starts while later segments synthesize.
const MAX_SEGMENT_CHARS = 120;
const FIRST_SEGMENT_CHARS = 48;

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
  let isFirst = true;

  for (const sentence of sentences) {
    const piece = sentence.trim();
    if (!piece) {
      continue;
    }
    const limit = isFirst ? FIRST_SEGMENT_CHARS : MAX_SEGMENT_CHARS;
    if (!current) {
      current = piece;
    } else if (current.length + piece.length + 1 <= limit) {
      current = `${current} ${piece}`;
    } else {
      segments.push(current);
      isFirst = false;
      current = piece;
    }
    // Force-flush a long first sentence early for time-to-first-speech.
    if (isFirst && current.length >= FIRST_SEGMENT_CHARS) {
      const cut = current.lastIndexOf(' ', FIRST_SEGMENT_CHARS);
      if (cut >= 20) {
        segments.push(current.slice(0, cut).trim());
        current = current.slice(cut).trim();
        isFirst = false;
      }
    }
  }
  if (current) {
    segments.push(current);
  }
  return segments.length > 0 ? segments : [text];
}

function speakOnDevice(cleaned: string, language: string): Promise<void> {
  return new Promise<void>((resolve) => {
    Speech.speak(cleaned, {
      language,
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
  const { speechLanguage } = useLocale();
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
    const logPlay = (event: string, extra?: Record<string, number | string | undefined>) => {
      console.info(
        '[TTFA TRACE]',
        JSON.stringify({
          event,
          index,
          bytes: audio.byteLength,
          ts: Date.now(),
          ...extra,
        }),
      );
    };

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
      logPlay('audio_decode_start');
      const blob = new Blob([audio], { type: 'audio/mpeg' });
      const url = URL.createObjectURL(blob);
      pendingBlobUrlRef.current = url;
      logPlay('audio_decode_end');

      await new Promise<void>((resolve, reject) => {
        let playedLogged = false;
        const markPlayed = (via: string) => {
          if (playedLogged || index !== 0) {
            return;
          }
          playedLogged = true;
          logPlay('first_audio_actually_played', { via });
          logPlay('audio_player_start', { via });
        };
        const cleanup = () => {
          element.onended = null;
          element.onerror = null;
          element.onplaying = null;
          element.loop = false;
          if (pendingBlobUrlRef.current === url) {
            URL.revokeObjectURL(url);
            pendingBlobUrlRef.current = null;
          }
        };
        element.onplaying = () => {
          markPlayed('onplaying');
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
        if (index === 0) {
          logPlay('first_audio_play_command');
        }
        const playAttempt = element.play();
        if (playAttempt && typeof playAttempt.then === 'function') {
          playAttempt
            .then(() => {
              markPlayed('play_promise');
            })
            .catch(async (error) => {
              try {
                element.loop = true;
                element.src = SILENT_WAV;
                element.volume = 0.001;
                await element.play();
                element.loop = false;
                element.volume = 1;
                element.src = url;
                await element.play();
                markPlayed('unlock_retry');
              } catch {
                cleanup();
                reject(error);
              }
            });
        }
      });
      return;
    }

    logPlay('audio_decode_start');
    const file = new File(Paths.cache, `tts-${Date.now()}-${index}.mp3`);
    file.create({ overwrite: true });
    file.write(new Uint8Array(audio));
    logPlay('audio_decode_end');

    const player = createAudioPlayer({ uri: file.uri });
    playerRef.current = player;

    try {
      await new Promise<void>((resolve, reject) => {
        let playedLogged = false;
        const subscription = player.addListener(
          'playbackStatusUpdate',
          (status) => {
            if (status.error) {
              subscription.remove();
              reject(new Error(status.error));
              return;
            }
            if (status.playing && index === 0 && !playedLogged) {
              playedLogged = true;
              logPlay('first_audio_actually_played');
              logPlay('audio_player_start');
            }
            if (status.didJustFinish) {
              subscription.remove();
              resolve();
            }
          },
        );
        if (index === 0) {
          logPlay('first_audio_play_command');
        }
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
            await speakOnDevice(remaining, speechLanguage);
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
          await speakOnDevice(cleaned, speechLanguage);
        }
      } finally {
        if (!cancelledRef.current) {
          setIsSpeaking(false);
        }
      }
    },
    [playBytes, speechLanguage, stop],
  );

  useEffect(
    () => () => {
      stop();
    },
    [stop],
  );

  const playBase64Mp3 = useCallback(
    async (base64: string, index: number) => {
      console.info(
        '[TTFA TRACE]',
        JSON.stringify({
          event: 'audio_decode_start',
          index,
          base64_chars: base64.length,
          ts: Date.now(),
          source: 'playBase64Mp3',
        }),
      );
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
      console.info(
        '[TTFA TRACE]',
        JSON.stringify({
          event: 'audio_decode_end',
          index,
          bytes: bytes.byteLength,
          ts: Date.now(),
          source: 'playBase64Mp3',
        }),
      );
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
