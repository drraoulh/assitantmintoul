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
import * as Haptics from 'expo-haptics';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { colors, flagStripes, radius, spacing } from '../../constants/theme';
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

function phaseCopy(
  phase: VoiceSessionPhase,
  isRecording: boolean,
): { title: string; subtitle: string; action: string } {
  if (phase === 'listening' || isRecording) {
    return {
      title: 'Je vous ecoute',
      subtitle: 'Parlez naturellement, comme a un guide.',
      action: 'Appuyer pour envoyer',
    };
  }
  if (phase === 'transcribing') {
    return {
      title: 'Je comprends...',
      subtitle: 'Lecture de votre question.',
      action: 'Patientez',
    };
  }
  if (phase === 'thinking') {
    return {
      title: 'Je prepare la reponse',
      subtitle: 'Consultation du guide Smartmboa Tour.',
      action: 'Patientez',
    };
  }
  if (phase === 'speaking') {
    return {
      title: 'Reponse en cours',
      subtitle: 'Ecoutez le guide, ou appuyez pour reparler.',
      action: 'Appuyer pour interrompre',
    };
  }
  return {
    title: 'Pret a vous ecouter',
    subtitle: 'Appuyez sur le micro pour commencer.',
    action: 'Appuyer pour parler',
  };
}

/** Proper French labels (accents) for display — kept as unicode escapes so the file stays ASCII-safe. */
function fr(phase: VoiceSessionPhase, isRecording: boolean) {
  const base = phaseCopy(phase, isRecording);
  const map: Record<string, { title: string; subtitle: string }> = {
    listening: {
      title: 'Je vous \u00e9coute',
      subtitle: 'Parlez naturellement, comme \u00e0 un guide.',
    },
    transcribing: {
      title: 'Je comprends\u2026',
      subtitle: 'Lecture de votre question.',
    },
    thinking: {
      title: 'Je pr\u00e9pare la r\u00e9ponse',
      subtitle: 'Consultation du guide Smartmboa Tour.',
    },
    speaking: {
      title: 'R\u00e9ponse en cours',
      subtitle: '\u00c9coutez le guide, ou appuyez pour reparler.',
    },
    idle: {
      title: 'Pr\u00eat \u00e0 vous \u00e9couter',
      subtitle: 'Appuyez sur le micro pour commencer.',
    },
  };
  const key =
    phase === 'listening' || isRecording
      ? 'listening'
      : phase === 'transcribing'
        ? 'transcribing'
        : phase === 'thinking'
          ? 'thinking'
          : phase === 'speaking'
            ? 'speaking'
            : 'idle';
  return { ...base, ...map[key] };
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
}: VoiceConversationModeProps) {
  const pulse = useRef(new Animated.Value(1)).current;
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

  const copy = fr(phase, isRecording);
  const subtitle =
    phase === 'idle' && !isRecording ? statusHint : copy.subtitle;
  const live = phase === 'listening' || phase === 'speaking' || isRecording;
  const busy = phase === 'transcribing' || phase === 'thinking';

  useEffect(() => {
    if (!visible) {
      fadeIn.setValue(0);
      return;
    }
    Animated.timing(fadeIn, {
      toValue: 1,
      duration: 280,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [visible, fadeIn]);

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

        <SafeAreaView style={styles.safe}>
          <Animated.View style={[styles.content, { opacity: fadeIn }]}>
            <View style={styles.topBar}>
              <View style={styles.brandBlock}>
                <Text style={styles.kicker}>Smartmboa Tour</Text>
                <Text style={styles.brand}>Mode vocal</Text>
              </View>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Fermer"
                hitSlop={16}
                onPress={handleClose}
                style={styles.closeBtn}
              >
                <Ionicons name="close" size={22} color={colors.ink} />
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
                    size={40}
                    color={colors.ivory}
                  />
                </Animated.View>
              </Pressable>

              <VoiceWave active={live} />
              <Text style={styles.actionHint}>{copy.action}</Text>

              <Pressable
                accessibilityRole="switch"
                accessibilityState={{ checked: handsFree }}
                accessibilityLabel="Mode mains libres"
                onPress={() => {
                  void Haptics.selectionAsync();
                  toggleHandsFree();
                }}
                style={[styles.toggle, handsFree && styles.toggleOn]}
              >
                <Text style={[styles.toggleText, handsFree && styles.toggleTextOn]}>
                  {handsFree ? 'Mains libres activ\u00e9' : 'Mains libres'}
                </Text>
              </Pressable>

              {micReady && phase === 'idle' && !isRecording ? (
                <Text style={styles.readyText}>Micro pr\u00eat</Text>
              ) : null}
            </View>

            <View style={styles.transcripts}>
              <Text style={styles.lineLabel}>Vous</Text>
              <Text style={styles.lineText} numberOfLines={2}>
                {lastUserText || 'Votre question appara\u00eetra ici.'}
              </Text>
              <View style={styles.divider} />
              <Text style={styles.lineLabelGuide}>Smartmboa</Text>
              <Text style={styles.lineText} numberOfLines={3}>
                {lastAssistantText || 'La r\u00e9ponse du guide s\u2019affichera ici.'}
              </Text>
            </View>

            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Quitter"
              onPress={handleClose}
              style={styles.exitBtn}
            >
              <Text style={styles.exitText}>Quitter</Text>
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
    paddingBottom: spacing.lg,
  },
  topBar: {
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
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
  },
  phase: {
    color: colors.ink,
    fontSize: 28,
    fontWeight: '700',
    textAlign: 'center',
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
    width: 180,
    height: 180,
    alignItems: 'center',
    justifyContent: 'center',
  },
  orb: {
    width: 120,
    height: 120,
    borderRadius: 60,
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
  },
  exitText: {
    color: colors.ivory,
    fontSize: 15,
    fontWeight: '700',
  },
});
