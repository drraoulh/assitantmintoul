import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { colors, radius, spacing } from '../../constants/theme';
import { useLocale, type TranslationKey } from '../../i18n';

interface WelcomeCardProps {
  onOpenParlerLocal?: () => void;
  onSelectTheme?: (prompt: string) => void;
  disabled?: boolean;
}

const THEMES: {
  key: TranslationKey;
  promptKey: TranslationKey;
  icon: keyof typeof Ionicons.glyphMap;
}[] = [
  { key: 'theme.nature', promptKey: 'prompt.nature', icon: 'leaf-outline' },
  { key: 'theme.beaches', promptKey: 'prompt.beaches', icon: 'water-outline' },
  { key: 'theme.food', promptKey: 'prompt.food', icon: 'restaurant-outline' },
  { key: 'theme.culture', promptKey: 'prompt.culture', icon: 'color-palette-outline' },
  { key: 'theme.mountains', promptKey: 'prompt.mountains', icon: 'trail-sign-outline' },
];

export function WelcomeCard({
  onOpenParlerLocal,
  onSelectTheme,
  disabled = false,
}: WelcomeCardProps) {
  const { t } = useLocale();

  return (
    <View style={styles.card}>
      <Text style={styles.kicker}>Smartmboa Tour</Text>
      <Text style={styles.title}>{t('tagline')}</Text>
      <Text style={styles.body}>{t('welcome.body')}</Text>

      {onSelectTheme ? (
        <View style={styles.themes}>
          <Text style={styles.themesLabel}>{t('welcome.themes')}</Text>
          <View style={styles.themeRow}>
            {THEMES.map((theme) => (
              <Pressable
                key={theme.key}
                accessibilityRole="button"
                disabled={disabled}
                onPress={() => onSelectTheme(t(theme.promptKey))}
                style={({ pressed }) => [
                  styles.themeChip,
                  pressed && styles.themePressed,
                  disabled && styles.disabled,
                ]}
              >
                <Ionicons name={theme.icon} size={14} color={colors.forestDeep} />
                <Text style={styles.themeText}>{t(theme.key)}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      ) : null}

      {onOpenParlerLocal ? (
        <Pressable
          accessibilityRole="button"
          onPress={onOpenParlerLocal}
          style={({ pressed }) => [styles.cta, pressed && styles.ctaPressed]}
        >
          <Ionicons name="chatbubbles-outline" size={18} color={colors.forestDeep} />
          <View style={styles.ctaText}>
            <Text style={styles.ctaTitle}>{t('welcome.localTitle')}</Text>
            <Text style={styles.ctaSub}>{t('welcome.localSub')}</Text>
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
  themes: {
    marginTop: spacing.md,
    gap: spacing.sm,
  },
  themesLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  themeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  themeChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(0, 122, 94, 0.08)',
    borderRadius: radius.pill,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: 'rgba(0, 122, 94, 0.18)',
  },
  themeText: {
    color: colors.forestDeep,
    fontSize: 13,
    fontWeight: '600',
  },
  themePressed: {
    backgroundColor: colors.goldSoft,
  },
  disabled: {
    opacity: 0.5,
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
