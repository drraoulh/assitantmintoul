import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { APP_NAME } from '../../constants/config';
import { colors, flagStripes, spacing } from '../../constants/theme';
import { useLocale } from '../../i18n';
import type { BackendStatus } from '../../types/chat';

interface ChatHeaderProps {
  status: BackendStatus;
  onStatusPress: () => void;
  onOpenHistory: () => void;
  onNewConversation: () => void;
}

export function ChatHeader({
  status,
  onStatusPress,
  onOpenHistory,
  onNewConversation,
}: ChatHeaderProps) {
  const { t, locale, toggleLocale } = useLocale();

  const statusLabel =
    status === 'checking'
      ? t('status.checking')
      : status === 'waking'
        ? t('status.waking')
        : status === 'online'
          ? t('status.online')
          : t('status.offline');

  return (
    <View style={styles.wrap}>
      <View style={styles.brandRow}>
        <View style={styles.mark}>
          <Text style={styles.flag}>🇨🇲</Text>
        </View>
        <View style={styles.titles}>
          <Text style={styles.name}>{APP_NAME}</Text>
          <Text style={styles.tagline}>{t('tagline')}</Text>
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t('a11y.language')}
          hitSlop={10}
          onPress={toggleLocale}
          style={styles.langBtn}
        >
          <Text style={styles.langText}>{locale === 'fr' ? 'FR' : 'EN'}</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t('a11y.history')}
          hitSlop={10}
          onPress={onOpenHistory}
          style={styles.iconBtn}
        >
          <Ionicons name="time-outline" size={20} color={colors.ivory} />
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t('a11y.newChat')}
          hitSlop={10}
          onPress={onNewConversation}
          style={[styles.iconBtn, styles.iconBtnAccent]}
        >
          <Ionicons name="add" size={22} color={colors.greenDeep} />
        </Pressable>
      </View>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t('a11y.checkServer')}
        onPress={onStatusPress}
        style={styles.statusChip}
      >
        <View style={[styles.dot, styles[status]]} />
        <Text style={styles.statusText}>{statusLabel}</Text>
      </Pressable>

      <View style={styles.stripes}>
        {flagStripes.map((stripe) => (
          <View
            key={stripe}
            style={[styles.stripe, { backgroundColor: stripe }]}
          />
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.forest,
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    paddingTop: spacing.sm,
    gap: spacing.sm,
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  mark: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: colors.forestDeep,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.gold,
  },
  flag: {
    fontSize: 22,
  },
  titles: {
    flex: 1,
  },
  name: {
    color: colors.ivory,
    fontSize: 17,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  tagline: {
    color: colors.goldSoft,
    fontSize: 12,
    marginTop: 2,
  },
  langBtn: {
    minWidth: 38,
    height: 38,
    borderRadius: 19,
    paddingHorizontal: 10,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255, 253, 247, 0.2)',
    borderWidth: 1,
    borderColor: colors.gold,
  },
  langText: {
    color: colors.gold,
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 0.6,
  },
  iconBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255, 253, 247, 0.16)',
  },
  iconBtnAccent: {
    backgroundColor: colors.yellow,
  },
  statusChip: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(255, 251, 244, 0.1)',
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  checking: {
    backgroundColor: colors.yellow,
  },
  waking: {
    backgroundColor: colors.yellow,
  },
  online: {
    backgroundColor: colors.mint,
  },
  offline: {
    backgroundColor: colors.red,
  },
  statusText: {
    color: colors.ivory,
    fontSize: 12,
    fontWeight: '600',
  },
  stripes: {
    flexDirection: 'row',
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
  },
  stripe: {
    flex: 1,
  },
});
