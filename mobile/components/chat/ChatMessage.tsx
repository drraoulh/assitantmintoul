import { Ionicons } from '@expo/vector-icons';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing } from '../../constants/theme';
import type { ChatMessage as ChatMessageType } from '../../types/chat';

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <View style={[styles.row, isUser ? styles.right : styles.left]}>
      {!isUser && (
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>CM</Text>
        </View>
      )}
      <View
        style={[
          styles.bubble,
          isUser && styles.userBubble,
          !isUser && styles.assistantBubble,
          message.isError && styles.errorBubble,
        ]}
      >
        <Text selectable style={[styles.text, isUser && styles.userText]}>
          {message.content}
        </Text>
        {!isUser && !message.isError && (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Écouter la réponse"
            onPress={() =>
              Alert.alert(
                'Lecture vocale',
                "La synthèse vocale sera disponible dans une prochaine phase.",
              )
            }
            style={styles.speak}
          >
            <Ionicons name="volume-high-outline" size={16} color={colors.canopy} />
            <Text style={styles.speakLabel}>Écouter</Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    marginBottom: spacing.md,
    maxWidth: '85%',
  },
  left: {
    alignSelf: 'flex-start',
    alignItems: 'flex-end',
  },
  right: {
    alignSelf: 'flex-end',
  },
  avatar: {
    width: 28,
    height: 28,
    borderRadius: 10,
    backgroundColor: colors.forest,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
    marginBottom: 2,
  },
  avatarText: {
    color: colors.gold,
    fontSize: 10,
    fontWeight: '800',
  },
  bubble: {
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    maxWidth: '100%',
    flexShrink: 1,
  },
  userBubble: {
    backgroundColor: colors.userBubble,
    borderBottomRightRadius: 6,
  },
  assistantBubble: {
    backgroundColor: colors.assistantBubble,
    borderBottomLeftRadius: 6,
    borderWidth: 1,
    borderColor: colors.line,
  },
  errorBubble: {
    backgroundColor: colors.errorBubble,
    borderColor: '#E8B298',
  },
  text: {
    color: colors.ink,
    fontSize: 15,
    lineHeight: 22,
    flexShrink: 1,
  },
  userText: {
    color: colors.ivory,
  },
  speak: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 10,
    alignSelf: 'flex-start',
  },
  speakLabel: {
    color: colors.canopy,
    fontSize: 12,
    fontWeight: '600',
  },
});
