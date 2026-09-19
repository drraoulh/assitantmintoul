import { useEffect, useMemo, useRef } from 'react';
import {
  Animated,
  Easing,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import * as Haptics from 'expo-haptics';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { colors, flagStripes, radius, spacing } from '../../constants/theme';
import { useLocale } from '../../i18n';
import {
  type VoiceSessionPhase,
  useContinuousVoiceSession,
} from '../../hooks/useContinuousVoiceSession';

interface VoiceConversationModeProps {
  visible: boolean;
  onClose: () => void;
  sendMessage: (text: string) => Promise<string | null>;
  speak: (text: string) => Promise<void>;
  stopSpeaking: () => void;
  playBase64Mp3?: (base64: string, index: number) => Promise<void>;
  unlockWebAudio?: () => Promise<void>;
  onExchange?: (userText: string, assistantText: string) => void;
}

function phaseLabels(
  phase: VoiceSessionPhase,
  isRecording: boolean,
  t: (key: import('../../i18n').TranslationKey) => string,
): { title: string; subtitle: string; action: string } {
  if (phase === 'listening' || isRecording) {
    return {
      title: t('voice.listeningTitle'),
      subtitle: t('voice.listeningSub'),
      action: t('voice.listeningAction'),
    };
  }
  if (phase === 'transcribing') {
    return {
      title: t('voice.transcribingTitle'),
      subtitle: t('voice.transcribingSub'),
      action: t('voice.wait'),
    };
  }
  if (phase === 'thinking') {
    return {
      title: t('voice.thinkingTitle'),
      subtitle: t('voice.thinkingSub'),
      action: t('voice.wait'),
    };
  }
  if (phase === 'speaking') {
    return {
      title: t('voice.speakingTitle'),
      subtitle: t('voice.speakingSub'),
      action: t('voice.interrupt'),
    };
  }
  return {
    title: t('voice.readyTitle'),
    subtitle: t('voice.readySub'),
    action: t('voice.readyAction'),
  };
}

function VoiceWave({ active }: { active: boolean }) {
  const bars = useMemo(
    () => Array.from({ length: 5 }, () => new Animated.Value(0.35)),
    [],
  );

  useEffect(() => {
    if (!active) {
      bars.forEach((bar) => bar.setValue(0.35));
      return;
    }
    const animations = bars.map((bar, index) =>
      Animated.loop(
        Animated.sequence([
          Animated.timing(bar, {
            toValue: 0.4 + ((index % 3) + 1) * 0.2,
            duration: 320 + index * 40,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
          Animated.timing(bar, {
            toValue: 0.3,
            duration: 320 + index * 40,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
        ]),
      ),
    );
    animations.forEach((animation, index) => {
      setTimeout(() => animation.start(), index * 50);
    });
    return () => animations.forEach((animation) => animation.stop());
  }, [active, bars]);

  return (
    <View style={styles.waveRow}>
      {bars.map((bar, index) => (
        <Animated.View
          key={`bar-${index}`}
          style={[styles.waveBar, { transform: [{ scaleY: bar }] }]}
        />
      ))}
    </View>
  );
}

export function VoiceConversationMode({
  visible,
  onClose,
  sendMessage,
  speak,
  stopSpeaking,
  playBase64Mp3,
  unlockWebAudio,
  onExchange,
}: VoiceConversationModeProps) {
  const { t, locale, toggleLocale } = useLocale();
  const pulse = useRef(new Animated.Value(1)).current;
  const fadeIn = useRef(new Animated.Value(0)).current;

  const {
    phase,
    lastUserText,
    lastAssistantText,
    isRecording,
    micReady,
    handsFree,
    toggleHandsFree,
    onOrbPress,
    shutdown,
  } = useContinuousVoiceSession({
    active: visible,
    sendMessage,
    speak,
    stopSpeaking,
    playBase64Mp3,
    onExchange,
  });

  const copy = phaseLabels(phase, isRecording, t);
  const live = phase === 'listening' || phase === 'speaking' || isRecording;
  const busy = phase === 'transcribing' || phase === 'thinking';

  useEffect(() => {
    if (!visible) {
      fadeIn.setValue(0);
      return;
    }
    // Opening the modal is a user gesture — unlock web audio autoplay now.
    void unlockWebAudio?.();
    Animated.timing(fadeIn, {
      toValue: 1,
      duration: 280,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [visible, fadeIn, unlockWebAudio]);

  useEffect(() => {
    if (!visible || !live) {
      pulse.setValue(1);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1.06,
          duration: 700,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 1,
          duration: 700,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [visible, live, pulse]);

  const handleClose = () => {
    void Haptics.selectionAsync();
    void shutdown().finally(() => onClose());
  };

  const handleOrbPress = () => {
    if (busy) return;
    // Keep autoplay unlocked across the long STT→LLM→TTS async chain.
    void unlockWebAudio?.();
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    void onOrbPress();
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="fullScreen"
      onRequestClose={handleClose}
    >
      <View style={styles.root}>
        <View style={styles.flagStripe}>
          {flagStripes.map((stripe) => (
            <View key={stripe} style={[styles.flagBand, { backgroundColor: stripe }]} />
          ))}
        </View>

        <SafeAreaView style={styles.safe} edges={['top', 'left', 'right', 'bottom']}>
          <Animated.View style={[styles.content, { opacity: fadeIn }]}>
            <View style={styles.topBar}>
              <View style={styles.brandBlock}>
                <Text style={styles.kicker}>Smartmboa Tour</Text>
                <Text style={styles.brand}>{t('voice.modeBrand')}</Text>
              </View>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={t('a11y.language')}
                hitSlop={12}
                onPress={() => {
                  void Haptics.selectionAsync();
                  toggleLocale();
                }}
                style={styles.langBtn}
              >
                <Text style={styles.langText}>{locale === 'fr' ? 'FR' : 'EN'}</Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={t('voice.close')}
                hitSlop={16}
                onPress={handleClose}
                style={styles.closeBtn}
              >
                <Ionicons name="close" size={22} color={colors.ink} />
              </Pressable>
            </View>

            <ScrollView
              style={styles.scroll}
              contentContainerStyle={styles.scrollContent}
              bounces={false}
              showsVerticalScrollIndicator={false}
              keyboardShouldPersistTaps="handled"
            >
              <View style={styles.center}>
                <Text style={styles.phase}>{copy.title}</Text>
                <Text style={styles.hint}>{copy.subtitle}</Text>

                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={copy.action}
                  disabled={busy}
                  onPress={handleOrbPress}
                  style={styles.orbHit}
                >
                  <Animated.View
                    style={[
                      styles.orb,
                      live && styles.orbLive,
                      busy && styles.orbBusy,
                      { transform: [{ scale: pulse }] },
                    ]}
                  >
                    <Ionicons
                      name={
                        phase === 'speaking'
                          ? 'volume-high'
                          : busy
                            ? 'hourglass-outline'
                            : 'mic'
                      }
                      size={36}
                      color={colors.ivory}
                    />
                  </Animated.View>
                </Pressable>

                <VoiceWave active={live} />
                <Text style={styles.actionHint}>{copy.action}</Text>

                <Pressable
                  accessibilityRole="switch"
                  accessibilityState={{ checked: handsFree }}
                  accessibilityLabel={t('voice.handsFree')}
                  onPress={() => {
                    void Haptics.selectionAsync();
                    toggleHandsFree();
                  }}
                  style={[styles.toggle, handsFree && styles.toggleOn]}
                >
                  <Text style={[styles.toggleText, handsFree && styles.toggleTextOn]}>
                    {handsFree ? t('voice.handsFreeOn') : t('voice.handsFree')}
                  </Text>
                </Pressable>

                {micReady && phase === 'idle' && !isRecording ? (
                  <Text style={styles.readyText}>{t('voice.micReady')}</Text>
                ) : null}
              </View>

              <View style={styles.transcripts}>
                <Text style={styles.lineLabel}>{t('voice.you')}</Text>
                <Text style={styles.lineText} numberOfLines={2}>
                  {lastUserText || t('voice.yourQuestion')}
                </Text>
                <View style={styles.divider} />
                <Text style={styles.lineLabelGuide}>Smartmboa</Text>
                <Text style={styles.lineText} numberOfLines={3}>
                  {lastAssistantText || t('voice.guideReply')}
                </Text>
              </View>
            </ScrollView>

            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t('voice.quit')}
              onPress={handleClose}
              style={styles.exitBtn}
            >
              <Text style={styles.exitText}>{t('voice.quit')}</Text>
            </Pressable>
          </Animated.View>
        </SafeAreaView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.sand,
  },
  flagStripe: {
    flexDirection: 'row',
    height: 6,
  },
  flagBand: {
    flex: 1,
  },
  safe: {
    flex: 1,
  },
  content: {
    flex: 1,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    backgroundColor: colors.sand,
    zIndex: 2,
  },
  brandBlock: {
    flex: 1,
    paddingRight: spacing.md,
  },
  kicker: {
    color: colors.canopy,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },
  brand: {
    color: colors.ink,
    fontSize: 22,
    fontWeight: '700',
    marginTop: 2,
  },
  langBtn: {
    minWidth: 44,
    height: 36,
    paddingHorizontal: 10,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.forest,
    marginRight: spacing.xs,
  },
  langText: {
    color: colors.ivory,
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 0.6,
  },
  closeBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.ivory,
    borderWidth: 1,
    borderColor: colors.line,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingBottom: spacing.md,
  },
  center: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.md,
    gap: spacing.sm,
    minHeight: 320,
  },
  phase: {
    color: colors.ink,
    fontSize: 24,
    fontWeight: '700',
    textAlign: 'center',
    paddingHorizontal: spacing.sm,
  },
  hint: {
    color: colors.muted,
    fontSize: 15,
    lineHeight: 22,
    textAlign: 'center',
    paddingHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  orbHit: {
    width: 160,
    height: 160,
    alignItems: 'center',
    justifyContent: 'center',
  },
  orb: {
    width: 108,
    height: 108,
    borderRadius: 54,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.green,
  },
  orbLive: {
    backgroundColor: colors.greenMid,
  },
  orbBusy: {
    backgroundColor: colors.greenInk,
    opacity: 0.85,
  },
  waveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    height: 28,
  },
  waveBar: {
    width: 5,
    height: 22,
    borderRadius: 99,
    backgroundColor: colors.green,
  },
  actionHint: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: '600',
    marginTop: spacing.xs,
  },
  toggle: {
    marginTop: spacing.md,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: radius.pill,
    backgroundColor: colors.ivory,
    borderWidth: 1,
    borderColor: colors.line,
  },
  toggleOn: {
    backgroundColor: colors.yellowSoft,
    borderColor: colors.yellow,
  },
  toggleText: {
    color: colors.ink,
    fontSize: 13,
    fontWeight: '600',
  },
  toggleTextOn: {
    color: colors.yellowInk,
  },
  readyText: {
    color: colors.canopy,
    fontSize: 12,
    fontWeight: '600',
  },
  transcripts: {
    backgroundColor: colors.ivory,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.line,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  lineLabel: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  lineLabelGuide: {
    color: colors.canopy,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  lineText: {
    color: colors.ink,
    fontSize: 15,
    lineHeight: 22,
  },
  divider: {
    height: 1,
    backgroundColor: colors.line,
    marginVertical: spacing.sm,
  },
  exitBtn: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: radius.md,
    backgroundColor: colors.ink,
    marginTop: spacing.xs,
  },
  exitText: {
    color: colors.ivory,
    fontSize: 15,
    fontWeight: '700',
  },
});
