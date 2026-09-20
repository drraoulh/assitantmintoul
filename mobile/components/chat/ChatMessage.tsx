import { useState } from 'react';
import { Ionicons } from '@expo/vector-icons';
import { Image, Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing } from '../../constants/theme';
import { useLocale } from '../../i18n';
import type { ChatMessage as ChatMessageType, ChatSource } from '../../types/chat';
import { copyOrShareText } from '../../utils/shareText';

interface ChatMessageProps {
  message: ChatMessageType;
  onSpeak?: (text: string) => void;
  onStopSpeaking?: () => void;
  isSpeaking?: boolean;
}

function SourceCard({ source }: { source: ChatSource }) {
  const meta = [source.city, source.region, source.category]
    .filter(Boolean)
    .join(' · ');

  const body = (
    <>
      {source.image_url ? (
        <Image
          source={{ uri: source.image_url }}
          style={styles.sourceImage}
          resizeMode="cover"
          accessibilityLabel={source.title}
        />
      ) : null}
      <View style={styles.sourceTextBlock}>
        <Text style={styles.sourceTitle} numberOfLines={2}>
          {source.title}
        </Text>
        {meta ? (
          <Text style={styles.sourceMeta} numberOfLines={1}>
            {meta}
          </Text>
        ) : null}
      </View>
    </>
  );

  if (source.url) {
    return (
      <Pressable
        accessibilityRole="link"
        onPress={() => {
          void Linking.openURL(source.url!);
        }}
        style={styles.sourceCard}
      >
        {body}
      </Pressable>
    );
  }

  return <View style={styles.sourceCard}>{body}</View>;
}

export function ChatMessage({
  message,
  onSpeak,
  onStopSpeaking,
  isSpeaking = false,
}: ChatMessageProps) {
  const { t } = useLocale();
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';
  const sources = message.sources?.filter((s) => s.title?.trim()) ?? [];
  const isPhotoMessage = Boolean(
    message.imageUri &&
      (message.content === 'Photo envoyée' ||
        message.content === 'Photo sent' ||
        message.content === t('photoSent')),
  );

  const handleCopy = async () => {
    try {
      await copyOrShareText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // ignore — share sheet cancel is common
    }
  };

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
        {message.imageUri ? (
          <Image
            source={{ uri: message.imageUri }}
            style={styles.image}
            resizeMode="cover"
            accessibilityLabel={t('photoSent')}
          />
        ) : null}
        {message.content && !isPhotoMessage ? (
          <Text selectable style={[styles.text, isUser && styles.userText]}>
            {message.content}
          </Text>
        ) : null}
        {isPhotoMessage ? (
          <Text style={[styles.caption, isUser && styles.userText]}>
            {t('photoCaption')}
          </Text>
        ) : null}
        {!isUser && !message.isError && sources.length > 0 ? (
          <View style={styles.sourcesBlock}>
            <Text style={styles.sourcesHint}>{t('sources')}</Text>
            {sources.slice(0, 4).map((source, index) => (
              <SourceCard
                key={`${source.title}-${source.image_url ?? index}`}
                source={source}
              />
            ))}
          </View>
        ) : null}
        {!isUser && !message.isError && message.content ? (
          <View style={styles.actions}>
            {onSpeak ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={isSpeaking ? t('a11y.stop') : t('a11y.listen')}
                onPress={() => {
                  if (isSpeaking) {
                    onStopSpeaking?.();
                    return;
                  }
                  onSpeak(message.content);
                }}
                style={styles.actionBtn}
              >
                <Ionicons
                  name={isSpeaking ? 'stop-circle-outline' : 'volume-high-outline'}
                  size={16}
                  color={colors.canopy}
                />
                <Text style={styles.actionLabel}>
                  {isSpeaking ? t('stop') : t('listen')}
                </Text>
              </Pressable>
            ) : null}
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t('a11y.copy')}
              onPress={() => void handleCopy()}
              style={styles.actionBtn}
            >
              <Ionicons
                name={copied ? 'checkmark-circle-outline' : 'copy-outline'}
                size={16}
                color={colors.canopy}
              />
              <Text style={styles.actionLabel}>
                {copied ? t('copied') : t('copy')}
              </Text>
            </Pressable>
          </View>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    marginBottom: spacing.md,
    maxWidth: '92%',
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
    borderColor: 'rgba(206, 17, 38, 0.35)',
  },
  image: {
    width: 220,
    height: 160,
    borderRadius: radius.sm,
    marginBottom: 8,
    backgroundColor: 'rgba(0,0,0,0.12)',
  },
  caption: {
    fontSize: 12,
    opacity: 0.85,
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
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginTop: 10,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  actionLabel: {
    color: colors.canopy,
    fontSize: 12,
    fontWeight: '600',
  },
  sourcesBlock: {
    marginTop: 12,
    gap: 8,
  },
  sourcesHint: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.6,
    textTransform: 'uppercase',
  },
  sourceCard: {
    backgroundColor: 'rgba(0, 122, 94, 0.06)',
    borderRadius: radius.sm,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.line,
  },
  sourceImage: {
    width: '100%',
    height: 140,
    backgroundColor: 'rgba(0,0,0,0.08)',
  },
  sourceTextBlock: {
    paddingHorizontal: 10,
    paddingVertical: 8,
    gap: 2,
  },
  sourceTitle: {
    color: colors.ink,
    fontSize: 13,
    fontWeight: '700',
  },
  sourceMeta: {
    color: colors.muted,
    fontSize: 11,
  },
});
