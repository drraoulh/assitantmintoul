import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { colors, radius, spacing } from '../../constants/theme';

interface WelcomeCardProps {
  onOpenParlerLocal?: () => void;
}

export function WelcomeCard({ onOpenParlerLocal }: WelcomeCardProps) {
  return (
    <View style={styles.card}>
      <Text style={styles.kicker}>Smartmboa Tour</Text>
      <Text style={styles.title}>Découvrez le Cameroun autrement</Text>
      <Text style={styles.body}>
        Itinéraires, transport, restos, culture, sécurité, ou « 2 jours à
        Douala » — posez votre question. Envoyez une photo pour reconnaître
        un lieu ou un plat. Mode conversation pour parler au guide.
      </Text>

      {onOpenParlerLocal ? (
        <Pressable
          accessibilityRole="button"
          onPress={onOpenParlerLocal}
          style={({ pressed }) => [styles.cta, pressed && styles.ctaPressed]}
        >
          <Ionicons name="chatbubbles-outline" size={18} color={colors.forestDeep} />
          <View style={styles.ctaText}>
            <Text style={styles.ctaTitle}>Parler local</Text>
            <Text style={styles.ctaSub}>
              Salutations et phrases utiles pour le voyage
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.forest} />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.ivory,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.line,
    gap: spacing.xs,
  },
  kicker: {
    color: colors.canopy,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },
  title: {
    color: colors.ink,
    fontSize: 26,
    fontWeight: '700',
  },
  body: {
    color: colors.muted,
    fontSize: 15,
    lineHeight: 22,
    marginTop: spacing.xs,
  },
  cta: {
    marginTop: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.goldSoft,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderWidth: 1,
    borderColor: colors.yellow,
  },
  ctaPressed: {
    opacity: 0.9,
  },
  ctaText: {
    flex: 1,
    gap: 2,
  },
  ctaTitle: {
    color: colors.forestDeep,
    fontSize: 15,
    fontWeight: '700',
  },
  ctaSub: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 16,
  },
});
