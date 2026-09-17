import { useEffect, useMemo, useRef } from 'react';
import {
  Animated,
  Easing,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import * as Haptics from 'expo-haptics';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { colors, spacing } from '../../constants/theme';
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
}

function phaseCopy(phase: VoiceSessionPhase, isRecording: boolean): {
  title: string;
  subtitle: string;
  action: string;
} {
  if (phase === 'listening' || isRecording) {
    return {
      title: 'Je vous Ã©coute',
      subtitle: 'Parlez naturellement, comme Ã  un guide.',
      action: 'Appuyer pour envoyer',
    };
  }
  if (phase === 'transcribing') {
    return {
      title: 'Je comprendsâ€¦',
      subtitle: 'Transcription de votre question.',
      action: 'Patientez',
    };
  }
  if (phase === 'thinking') {
    return {
      title: 'Je prÃ©pare la rÃ©ponse',
      subtitle: 'Recherche dans les sites touristiques du Cameroun.',
      action: 'Patientez',
    };
  }
  if (phase === 'speaking') {
    return {
      title: 'RÃ©ponse en cours',
      subtitle: 'Ã‰coutez le guide, ou interrompez pour reparler.',
      action: 'Appuyer pour interrompre',
    };
  }
  return {
    title: 'PrÃªt Ã  vous Ã©couter',
    subtitle: 'Rien ne sâ€™enregistre avant votre appui.',
    action: 'Appuyer pour parler',
  };
}

function VoiceWave({ active, tint }: { active: boolean; tint: string }) {
  const bars = useMemo(
    () => Array.from({ length: 7 }, () => new Animated.Value(0.35)),
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
            toValue: 0.35 + ((index % 3) + 1) * 0.22,
            duration: 280 + index * 45,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
          Animated.timing(bar, {
            toValue: 0.3,
            duration: 280 + index * 45,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
        ]),
      ),
    );

    animations.forEach((animation, index) => {
      setTimeout(() => animation.start(), index * 40);
    });

    return () => animations.forEach((animation) => animation.stop());
  }, [active, bars]);

  return (
    <View style={styles.waveRow}>
      {bars.map((bar, index) => (
        <Animated.View
          key={`bar-${index}`}
          style={[
            styles.waveBar,
            {
              backgroundColor: tint,
              transform: [{ scaleY: bar }],
            },
          ]}
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
}: VoiceConversationModeProps) {
  const pulse = useRef(new Animated.Value(1)).current;
  const ring = useRef(new Animated.Value(1)).current;
  const fadeIn = useRef(new Animated.Value(0)).current;

  const {
    phase,
    statusHint,
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
  });

  const copy = phaseCopy(phase, isRecording);
  const subtitle = phase === 'idle' && !isRecording ? statusHint : copy.subtitle;
  const live = phase === 'listening' || phase === 'speaking' || isRecording;
  const busy = phase === 'transcribing' || phase === 'thinking';

  const orbColor =
    phase === 'speaking'
      ? colors.yellow
      : phase === 'listening' || isRecording
        ? colors.greenMid
        : busy
          ? colors.greenInk
          : colors.green;

  useEffect(() => {
    if (!visible) {
      fadeIn.setValue(0);
      return;
    }
    Animated.timing(fadeIn, {
      toValue: 1,
      duration: 420,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [visible, fadeIn]);

  useEffect(() => {
    if (!visible || !live) {
      pulse.setValue(1);
      ring.setValue(1);
      return;
    }

    const pulseLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: phase === 'speaking' ? 1.08 : 1.14,
          duration: phase === 'speaking' ? 650 : 850,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 1,
          duration: phase === 'speaking' ? 650 : 850,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ]),
    );

    const ringLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(ring, {
          toValue: 1.35,
          duration: 1400,
          easing: Easing.out(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(ring, {
          toValue: 1,
          duration: 0,
          useNativeDriver: true,
        }),
      ]),
    );

    pulseLoop.start();
    ringLoop.start();
    return () => {
      pulseLoop.stop();
      ringLoop.stop();
    };
  }, [visible, live, phase, pulse, ring]);

  const handleClose = () => {
    void Haptics.selectionAsync();
    void shutdown().finally(() => {
      onClose();
    });
  };

  const handleOrbPress = () => {
    if (busy) {
      return;
    }
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    void onOrbPress();
  };

  const handleHandsFreePress = () => {
    void Haptics.selectionAsync();
    toggleHandsFree();
  };

  return (
    <Modal
      visible={visible}
      animationType="fade"
      presentationStyle="fullScreen"
      onRequestClose={handleClose}
    >
      <LinearGradient
        colors={['#02140E', '#00412F', '#00563F', '#031C15']}
        locations={[0, 0.35, 0.7, 1]}
        style={styles.root}
      >
        <View pointerEvents="none" style={styles.glowTop} />
        <View pointerEvents="none" style={styles.glowBottom} />

        <SafeAreaView style={styles.safe}>
          <Animated.View style={[styles.content, { opacity: fadeIn }]}>
            <View style={styles.topBar}>
              <View style={styles.brandBlock}>
                <Text style={styles.kicker}>Cameroon AI Tour Guide</Text>
                <Text style={styles.brand}>Conversation vocale</Text>
              </View>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Fermer le mode conversation"
                hitSlop={16}
                onPress={handleClose}
                style={styles.closeBtn}
              >
                <Ionicons name="close" size={22} color={colors.ivory} />
              </Pressable>
            </View>

            <View style={styles.center}>
              <Text style={styles.phase}>{copy.title}</Text>
              <Text style={styles.hint}>{subtitle}</Text>

              <Pressable
                accessibilityRole="button"
                accessibilityLabel={copy.action}
                disabled={busy}
                onPress={handleOrbPress}
                style={styles.orbHit}
              >
                <Animated.View
                  pointerEvents="none"
                  style={[
                    styles.ring,
                    {
                      borderColor: orbColor,
                      opacity: ring.interpolate({
                        inputRange: [1, 1.35],
                        outputRange: [0.45, 0],
                      }),
                      transform: [{ scale: ring }],
                    },
                  ]}
                />
                <Animated.View
                  pointerEvents="none"
                  style={[
                    styles.orbGlow,
                    {
                      backgroundColor: orbColor,
                      transform: [{ scale: pulse }],
                    },
                  ]}
                />
                <View style={[styles.orb, { backgroundColor: orbColor }]}>
                  <Ionicons
                    name={
                      phase === 'speaking'
                        ? 'volume-high'
                        : phase === 'listening' || isRecording
                          ? 'mic'
                          : busy
                            ? 'hourglass'
                            : 'mic'
                    }
                    size={44}
                    color={colors.ivory}
                  />
                </View>
              </Pressable>

              <VoiceWave
                active={live}
                tint={phase === 'speaking' ? colors.yellowSoft : colors.mint}
              />

              <Pressable
                accessibilityRole="button"
                disabled={busy}
                onPress={handleOrbPress}
                style={[styles.actionPill, busy && styles.actionPillDisabled]}
              >
                <Text style={styles.actionText}>{copy.action}</Text>
              </Pressable>

              <View style={styles.optionsRow}>
                <Pressable
                  accessibilityRole="switch"
                  accessibilityState={{ checked: handsFree }}
                  accessibilityLabel="Mode mains libres"
                  onPress={handleHandsFreePress}
                  style={[styles.optionPill, handsFree && styles.optionPillOn]}
                >
                  <Ionicons
                    name={handsFree ? 'infinite' : 'hand-left-outline'}
                    size={15}
                    color={handsFree ? colors.forestDeep : colors.ivory}
                  />
                  <Text
                    style={[styles.optionText, handsFree && styles.optionTextOn]}
                  >
                    {handsFree ? 'Mains libres' : 'Appui manuel'}
                  </Text>
                </Pressable>

                {micReady && phase === 'idle' && !isRecording && (
                  <View style={styles.readyBadge}>
                    <View style={styles.readyDot} />
                    <Text style={styles.readyText}>Micro prÃªt</Text>
                  </View>
                )}
              </View>
            </View>

            <View style={styles.transcripts}>
              <View style={styles.card}>
                <Text style={styles.cardLabel}>Vous</Text>
                <Text style={styles.cardText} numberOfLines={3}>
                  {lastUserText || 'Votre question apparaÃ®tra ici.'}
                </Text>
              </View>
              <View style={[styles.card, styles.cardAssistant]}>
                <Text style={[styles.cardLabel, styles.cardLabelGold]}>Guide</Text>
                <Text style={styles.cardText} numberOfLines={4}>
                  {lastAssistantText || 'La rÃ©ponse du guide sâ€™affichera ici.'}
                </Text>
              </View>
            </View>

            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Quitter le mode conversation"
              onPress={handleClose}
              style={styles.exitBtn}
            >
              <Ionicons name="exit-outline" size={18} color={colors.ivory} />
              <Text style={styles.exitText}>Quitter la conversation</Text>
            </Pressable>
          </Animated.View>
        </SafeAreaView>
      </LinearGradient>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  glowTop: {
    position: 'absolute',
    top: -80,
    alignSelf: 'center',
    width: 280,
    height: 280,
    borderRadius: 140,
    backgroundColor: 'rgba(0, 122, 94, 0.32)',
  },
  glowBottom: {
    position: 'absolute',
    bottom: -40,
    right: -40,
    width: 220,
    height: 220,
    borderRadius: 110,
    backgroundColor: 'rgba(252, 209, 22, 0.14)',
  },
  safe: {
    flex: 1,
  },
  content: {
    flex: 1,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
  },
  topBar: {
    zIndex: 20,
    elevation: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: spacing.sm,
  },
  brandBlock: {
    flex: 1,
    paddingRight: spacing.md,
  },
  kicker: {
    color: 'rgba(255, 232, 148, 0.78)',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.1,
    textTransform: 'uppercase',
  },
  brand: {
    color: colors.ivory,
    fontSize: 20,
    fontWeight: '700',
    marginTop: 2,
  },
  closeBtn: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,251,244,0.14)',
    borderWidth: 1,
    borderColor: 'rgba(255,251,244,0.22)',
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
  },
  phase: {
    color: colors.ivory,
    fontSize: 32,
    fontWeight: '700',
    letterSpacing: -0.4,
    textAlign: 'center',
  },
  hint: {
    color: 'rgba(255,251,244,0.68)',
    fontSize: 15,
    lineHeight: 22,
    textAlign: 'center',
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  orbHit: {
    width: 240,
    height: 240,
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: spacing.sm,
  },
  ring: {
    position: 'absolute',
    width: 168,
    height: 168,
    borderRadius: 84,
    borderWidth: 2,
  },
  orbGlow: {
    position: 'absolute',
    width: 190,
    height: 190,
    borderRadius: 95,
    opacity: 0.28,
  },
  orb: {
    width: 138,
    height: 138,
    borderRadius: 69,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255,251,244,0.18)',
  },
  waveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    height: 36,
    marginTop: spacing.sm,
  },
  waveBar: {
    width: 5,
    height: 28,
    borderRadius: 99,
  },
  actionPill: {
    marginTop: spacing.md,
    paddingHorizontal: 22,
    paddingVertical: 12,
    borderRadius: 999,
    backgroundColor: 'rgba(255,251,244,0.1)',
    borderWidth: 1,
    borderColor: 'rgba(255,251,244,0.16)',
  },
  actionPillDisabled: {
    opacity: 0.55,
  },
  actionText: {
    color: colors.ivory,
    fontSize: 14,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
  optionsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  optionPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 999,
    backgroundColor: 'rgba(255,251,244,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(255,251,244,0.16)',
  },
  optionPillOn: {
    backgroundColor: colors.goldSoft,
    borderColor: colors.gold,
  },
  optionText: {
    color: colors.ivory,
    fontSize: 13,
    fontWeight: '600',
  },
  optionTextOn: {
    color: colors.forestDeep,
  },
  readyBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 9,
  },
  readyDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: colors.mint,
  },
  readyText: {
    color: 'rgba(255,251,244,0.7)',
    fontSize: 12,
    fontWeight: '600',
  },
  transcripts: {
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  card: {
    backgroundColor: 'rgba(255,251,244,0.07)',
    borderRadius: 18,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: 'rgba(255,251,244,0.1)',
  },
  cardAssistant: {
    backgroundColor: 'rgba(252,209,22,0.12)',
    borderColor: 'rgba(252,209,22,0.26)',
  },
  cardLabel: {
    color: 'rgba(255,251,244,0.55)',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.9,
    textTransform: 'uppercase',
    marginBottom: 6,
  },
  cardLabelGold: {
    color: colors.goldSoft,
  },
  cardText: {
    color: colors.ivory,
    fontSize: 15,
    lineHeight: 22,
  },
  exitBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: spacing.sm,
    paddingVertical: 14,
    borderRadius: 16,
    backgroundColor: 'rgba(206, 17, 38, 0.32)',
    borderWidth: 1,
    borderColor: 'rgba(255,251,244,0.16)',
  },
  exitText: {
    color: colors.ivory,
    fontSize: 15,
    fontWeight: '700',
  },
});
