import { Pressable, StyleSheet, Text, View } from 'react-native';

import { APP_NAME, APP_TAGLINE } from '../../constants/config';
import { colors, spacing } from '../../constants/theme';
import type { BackendStatus } from '../../types/chat';

interface ChatHeaderProps {
  status: BackendStatus;
  onStatusPress: () => void;
}

const STATUS_LABEL: Record<BackendStatus, string> = {
  checking: 'Connexion…',
  online: 'Connecté',
  offline: 'Hors ligne',
};

export function ChatHeader({ status, onStatusPress }: ChatHeaderProps) {
  return (
    <View style={styles.wrap}>
      <View style={styles.brandRow}>
        <View style={styles.mark}>
          <Text style={styles.flag}>🇨🇲</Text>
        </View>
        <View style={styles.titles}>
          <Text style={styles.name}>{APP_NAME}</Text>
          <Text style={styles.tagline}>{APP_TAGLINE}</Text>
        </View>
      </View>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Vérifier la connexion au serveur"
        onPress={onStatusPress}
        style={styles.statusChip}
      >
        <View style={[styles.dot, styles[status]]} />
        <Text style={styles.statusText}>{STATUS_LABEL[status]}</Text>
      </Pressable>
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
    gap: spacing.sm,
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
    backgroundColor: colors.gold,
  },
  online: {
    backgroundColor: '#7DCEA0',
  },
  offline: {
    backgroundColor: '#E57373',
  },
  statusText: {
    color: colors.ivory,
    fontSize: 12,
    fontWeight: '600',
  },
});
