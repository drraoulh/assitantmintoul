import { useCallback, useMemo, useRef, useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Asset } from 'expo-asset';
import {
  createAudioPlayer,
  setAudioModeAsync,
  type AudioPlayer,
} from 'expo-audio';
import * as Speech from 'expo-speech';

import { EXPRESSION_LANGUAGES, EXPRESSIONS } from '../data/expressions';
import { colors, radius, spacing } from '../constants/theme';
import { useLocale } from '../i18n';
import { useSpeechPlayback } from '../hooks/useSpeechPlayback';
import type { Expression } from '../types/culture';

interface ParlerLocalScreenProps {
  onBack: () => void;
}

const ALL = '__all__';

export function ParlerLocalScreen({ onBack }: ParlerLocalScreenProps) {
  const { t, locale } = useLocale();
  const [language, setLanguage] = useState(ALL);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const playerRef = useRef<AudioPlayer | null>(null);
  const { speak, stop: stopTts, unlockWebAudio } = useSpeechPlayback();

  const phrases = useMemo(
    () =>
      language === ALL
        ? EXPRESSIONS
        : EXPRESSIONS.filter((item) => item.language === language),
    [language],
  );

  const filters = useMemo(() => [ALL, ...EXPRESSION_LANGUAGES], []);

  const stopNative = useCallback(() => {
    try {
      playerRef.current?.pause();
      playerRef.current?.remove();
    } catch {
      // ignore
    }
    playerRef.current = null;
  }, []);

  const stopAll = useCallback(() => {
    stopNative();
    stopTts();
    Speech.stop();
    setPlayingId(null);
  }, [stopNative, stopTts]);

  const playNative = useCallback(
    async (item: Expression) => {
      if (item.audio == null) {
        return false;
      }
      stopAll();
      await setAudioModeAsync({
        playsInSilentMode: true,
        allowsRecording: false,
      });
      const asset = Asset.fromModule(item.audio);
      await asset.downloadAsync();
      const uri = asset.localUri ?? asset.uri;
      if (!uri) {
        return false;
      }
      const player = createAudioPlayer({ uri });
      playerRef.current = player;
      setPlayingId(item.id);
      player.play();
      const poll = setInterval(() => {
        if (!player.playing) {
          clearInterval(poll);
          if (playerRef.current === player) {
            stopNative();
            setPlayingId(null);
          }
        }
      }, 250);
      return true;
    },
    [stopAll, stopNative],
  );

  const playGuideVoice = useCallback(
    async (item: Expression) => {
      stopAll();
      setPlayingId(item.id);
      await unlockWebAudio();
      // Prefer the local phrase; pronunciation helps when the script is rare.
      const line = `${item.phrase}. ${item.pronunciation}`;
      try {
        await speak(line);
      } catch {
        await new Promise<void>((resolve) => {
          Speech.speak(item.pronunciation || item.phrase, {
            language: 'fr-FR',
            rate: 0.78,
            onDone: () => resolve(),
            onStopped: () => resolve(),
            onError: () => resolve(),
          });
        });
      } finally {
        setPlayingId((current) => (current === item.id ? null : current));
      }
    },
    [speak, stopAll, unlockWebAudio],
  );

  const playPhrase = useCallback(
    async (item: Expression) => {
      if (playingId === item.id) {
        stopAll();
        return;
      }
      try {
        if (item.audio != null) {
          const ok = await playNative(item);
          if (ok) {
            return;
          }
        }
        await playGuideVoice(item);
      } catch {
        stopAll();
      }
    },
    [playGuideVoice, playNative, playingId, stopAll],
  );

  return (
    <View style={styles.root}>
      <SafeAreaView edges={['top']} style={styles.topSafe}>
        <View style={styles.header}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t('local.back')}
            onPress={() => {
              stopAll();
              onBack();
            }}
            style={({ pressed }) => [styles.backBtn, pressed && styles.pressed]}
          >
            <Ionicons name="chevron-back" size={22} color={colors.ivory} />
          </Pressable>
          <View style={styles.headerText}>
            <Text style={styles.kicker}>Culture</Text>
            <Text style={styles.title}>{t('local.title')}</Text>
          </View>
        </View>
      </SafeAreaView>

      <ScrollView
        style={styles.body}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.intro}>{t('local.subtitle')}</Text>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filters}
        >
          {filters.map((lang) => {
            const active = lang === language;
            const label = lang === ALL ? t('local.all') : lang;
            return (
              <Pressable
                key={lang}
                onPress={() => setLanguage(lang)}
                style={[styles.chip, active && styles.chipActive]}
              >
                <Text style={[styles.chipText, active && styles.chipTextActive]}>
                  {label}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>

        <View style={styles.list}>
          {phrases.map((item) => {
            const isPlaying = playingId === item.id;
            const hasNative = item.audio != null;
            const meaning =
              locale === 'en'
                ? item.translationEn || item.translationFr
                : item.translationFr;
            const context =
              locale === 'en' ? item.contextEn || item.contextFr : item.contextFr;
            return (
              <View key={item.id} style={styles.card}>
                <View style={styles.cardTop}>
                  <Text style={styles.language}>{item.language}</Text>
                  <Text style={styles.meaning}>{meaning}</Text>
                </View>
                <Text style={styles.phrase}>{item.phrase}</Text>
                <Text style={styles.pronunciation}>
                  {t('local.pronunciation')} :{' '}
                  {item.pronunciation}
                </Text>
                <Text style={styles.context}>{context}</Text>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => void playPhrase(item)}
                  style={({ pressed }) => [
                    styles.listenBtn,
                    isPlaying && styles.listenBtnActive,
                    pressed && styles.pressed,
                  ]}
                >
                  <Ionicons
                    name={isPlaying ? 'stop-circle' : 'volume-high'}
                    size={18}
                    color={isPlaying ? colors.forestDeep : colors.forest}
                  />
                  <Text style={styles.listenText}>
                    {isPlaying
                      ? t('stop')
                      : hasNative
                        ? t('local.listenNative')
                        : t('local.listenGuide')}
                  </Text>
                </Pressable>
              </View>
            );
          })}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.forest,
  },
  topSafe: {
    backgroundColor: colors.forest,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.sm,
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.12)',
  },
  headerText: {
    flex: 1,
  },
  kicker: {
    color: colors.mint,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.1,
    textTransform: 'uppercase',
  },
  title: {
    color: colors.ivory,
    fontSize: 22,
    fontWeight: '700',
  },
  body: {
    flex: 1,
    backgroundColor: colors.sand,
  },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xl,
    gap: spacing.md,
  },
  intro: {
    color: colors.muted,
    fontSize: 15,
    lineHeight: 22,
  },
  filters: {
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  chip: {
    backgroundColor: colors.ivory,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  chipActive: {
    backgroundColor: colors.forest,
    borderColor: colors.forest,
  },
  chipText: {
    color: colors.forest,
    fontSize: 13,
    fontWeight: '600',
  },
  chipTextActive: {
    color: colors.ivory,
  },
  list: {
    gap: spacing.md,
  },
  card: {
    backgroundColor: colors.ivory,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.line,
    padding: spacing.md,
    gap: spacing.xs,
  },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    gap: spacing.sm,
  },
  language: {
    color: colors.canopy,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.6,
    textTransform: 'uppercase',
  },
  meaning: {
    flex: 1,
    textAlign: 'right',
    color: colors.muted,
    fontSize: 13,
    fontWeight: '600',
  },
  phrase: {
    color: colors.ink,
    fontSize: 24,
    fontWeight: '700',
    marginTop: spacing.xs,
  },
  pronunciation: {
    color: colors.yellowInk,
    fontSize: 13,
    fontWeight: '600',
  },
  context: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
    marginTop: spacing.xs,
  },
  listenBtn: {
    marginTop: spacing.sm,
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.goldSoft,
    borderRadius: radius.pill,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  listenBtnActive: {
    backgroundColor: colors.yellow,
  },
  listenText: {
    color: colors.forestDeep,
    fontSize: 13,
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.85,
  },
});
