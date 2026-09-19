import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';

import { colors, flagStripes, radius, spacing } from '../../constants/theme';
import { useLocale } from '../../i18n';
import { deleteConversation, listConversations } from '../../services/api';
import type { ConversationSummary } from '../../types/chat';

interface ConversationHistorySheetProps {
  visible: boolean;
  activeConversationId?: string;
  onClose: () => void;
  onOpenConversation: (id: string) => void;
  onNewConversation: () => void;
}

function formatUpdatedAt(
  value: string | null | undefined,
  todayLabel: string,
  dateLocale: string,
): string {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  if (sameDay) {
    return `${todayLabel} ${date.toLocaleTimeString(dateLocale, {
      hour: '2-digit',
      minute: '2-digit',
    })}`;
  }
  return date.toLocaleDateString(dateLocale, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function ConversationHistorySheet({
  visible,
  activeConversationId,
  onClose,
  onOpenConversation,
  onNewConversation,
}: ConversationHistorySheetProps) {
  const { t, dateLocale } = useLocale();
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [persistent, setPersistent] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listConversations();
      setItems(response.items);
      setPersistent(response.persistent);
    } catch {
      setError(t('history.error'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (visible) {
      void load();
    }
  }, [visible, load]);

  const confirmDelete = (item: ConversationSummary) => {
    Alert.alert(t('history.deleteTitle'), `${t('history.deleteBody')}\n« ${item.title} »`, [
      { text: t('history.cancel'), style: 'cancel' },
      {
        text: t('history.delete'),
        style: 'destructive',
        onPress: () => {
          void (async () => {
            try {
              await deleteConversation(item.id);
              setItems((current) =>
                current.filter((entry) => entry.id !== item.id),
              );
              if (item.id === activeConversationId) {
                onNewConversation();
              }
            } catch {
              Alert.alert(t('history.title'), t('history.error'));
            }
          })();
        },
      },
    ]);
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <View style={styles.root}>
        <SafeAreaView edges={['top']} style={styles.headerSafe}>
          <View style={styles.header}>
            <View style={styles.headerCopy}>
              <Text style={styles.kicker}>{t('history.title')}</Text>
              <Text style={styles.title}>{t('history.title')}</Text>
            </View>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t('history.close')}
              hitSlop={12}
              onPress={onClose}
              style={styles.closeBtn}
            >
              <Ionicons name="close" size={22} color={colors.ivory} />
            </Pressable>
          </View>
          <View style={styles.stripes}>
            {flagStripes.map((stripe) => (
              <View
                key={stripe}
                style={[styles.stripe, { backgroundColor: stripe }]}
              />
            ))}
          </View>
        </SafeAreaView>

        <ScrollView contentContainerStyle={styles.list}>
          <Pressable
            accessibilityRole="button"
            onPress={() => {
              onNewConversation();
              onClose();
            }}
            style={({ pressed }) => [styles.newRow, pressed && styles.pressed]}
          >
            <View style={styles.newIcon}>
              <Ionicons name="add" size={20} color={colors.greenDeep} />
            </View>
            <Text style={styles.newLabel}>{t('a11y.newChat')}</Text>
          </Pressable>

          {!persistent && (
            <Text style={styles.notice}>{t('history.ephemeral')}</Text>
          )}

          {loading && (
            <View style={styles.center}>
              <ActivityIndicator color={colors.green} />
            </View>
          )}

          {error && <Text style={styles.error}>{error}</Text>}

          {!loading && !error && items.length === 0 && (
            <Text style={styles.empty}>{t('history.empty')}</Text>
          )}

          {items.map((item) => {
            const isActive = item.id === activeConversationId;
            return (
              <View
                key={item.id}
                style={[styles.row, isActive && styles.rowActive]}
              >
                <Pressable
                  accessibilityRole="button"
                  style={styles.rowMain}
                  onPress={() => {
                    onOpenConversation(item.id);
                    onClose();
                  }}
                >
                  <Text numberOfLines={2} style={styles.rowTitle}>
                    {item.title}
                  </Text>
                  <Text style={styles.rowMeta}>
                    {item.message_count} message
                    {item.message_count > 1 ? 's' : ''}
                    {formatUpdatedAt(item.updated_at, t('history.today'), dateLocale)
                      ? ` · ${formatUpdatedAt(item.updated_at, t('history.today'), dateLocale)}`
                      : ''}
                  </Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={`Supprimer ${item.title}`}
                  hitSlop={10}
                  onPress={() => confirmDelete(item)}
                  style={styles.deleteBtn}
                >
                  <Ionicons name="trash-outline" size={18} color={colors.red} />
                </Pressable>
              </View>
            );
          })}
        </ScrollView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.sand,
  },
  headerSafe: {
    backgroundColor: colors.green,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    paddingTop: spacing.sm,
  },
  headerCopy: {
    flex: 1,
  },
  kicker: {
    color: 'rgba(255, 232, 148, 0.85)',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.1,
    textTransform: 'uppercase',
  },
  title: {
    color: colors.ivory,
    fontSize: 20,
    fontWeight: '700',
    marginTop: 2,
  },
  closeBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255, 253, 247, 0.16)',
  },
  stripes: {
    flexDirection: 'row',
    height: 4,
  },
  stripe: {
    flex: 1,
  },
  list: {
    padding: spacing.md,
    gap: spacing.sm,
  },
  newRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: colors.ivory,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    paddingHorizontal: 14,
    paddingVertical: 14,
  },
  newIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.yellow,
  },
  newLabel: {
    color: colors.ink,
    fontSize: 15,
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.85,
  },
  notice: {
    color: colors.yellowInk,
    backgroundColor: 'rgba(252, 209, 22, 0.16)',
    borderRadius: radius.sm,
    padding: spacing.sm,
    fontSize: 12,
    lineHeight: 18,
  },
  center: {
    paddingVertical: spacing.lg,
  },
  error: {
    color: colors.red,
    fontSize: 13,
    paddingVertical: spacing.sm,
  },
  empty: {
    color: colors.muted,
    fontSize: 14,
    paddingVertical: spacing.lg,
    textAlign: 'center',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.ivory,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    paddingLeft: 14,
    paddingRight: 6,
  },
  rowActive: {
    borderColor: colors.green,
    backgroundColor: 'rgba(0, 122, 94, 0.06)',
  },
  rowMain: {
    flex: 1,
    paddingVertical: 14,
    paddingRight: spacing.sm,
  },
  rowTitle: {
    color: colors.ink,
    fontSize: 15,
    fontWeight: '600',
  },
  rowMeta: {
    color: colors.muted,
    fontSize: 12,
    marginTop: 4,
  },
  deleteBtn: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
