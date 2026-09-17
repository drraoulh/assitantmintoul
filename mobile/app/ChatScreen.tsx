import { useEffect, useRef } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ChatHeader } from '../components/chat/ChatHeader';
import { ChatInputBar } from '../components/chat/ChatInputBar';
import { ChatMessage } from '../components/chat/ChatMessage';
import { SuggestedPrompts } from '../components/chat/SuggestedPrompts';
import { TypingIndicator } from '../components/chat/TypingIndicator';
import { WelcomeCard } from '../components/chat/WelcomeCard';
import { colors, spacing } from '../constants/theme';
import { useChat } from '../hooks/useChat';

export function ChatScreen() {
  const { messages, isSending, backendStatus, sendMessage, checkHealth } = useChat();
  const scrollRef = useRef<ScrollView>(null);
  const isEmpty = messages.length === 0;

  useEffect(() => {
    scrollRef.current?.scrollToEnd({ animated: true });
  }, [messages, isSending]);

  return (
    <View style={styles.root}>
      <SafeAreaView edges={['top']} style={styles.topSafe}>
        <ChatHeader status={backendStatus} onStatusPress={() => void checkHealth()} />
      </SafeAreaView>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 8 : 0}
      >
        <ScrollView
          ref={scrollRef}
          style={styles.flex}
          contentContainerStyle={styles.thread}
          keyboardShouldPersistTaps="handled"
          onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
        >
          {isEmpty && (
            <View style={styles.empty}>
              <WelcomeCard />
              <SuggestedPrompts disabled={isSending} onSelect={(prompt) => void sendMessage(prompt)} />
            </View>
          )}

          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}
          {isSending && <TypingIndicator />}
        </ScrollView>

        <SafeAreaView edges={['bottom']} style={styles.composerSafe}>
          <ChatInputBar disabled={isSending} onSend={(text) => void sendMessage(text)} />
        </SafeAreaView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.forest,
  },
  topSafe: {
    backgroundColor: colors.forest,
  },
  flex: {
    flex: 1,
    backgroundColor: colors.sand,
  },
  thread: {
    padding: spacing.md,
    paddingBottom: spacing.lg,
    flexGrow: 1,
  },
  empty: {
    gap: spacing.lg,
    marginBottom: spacing.lg,
  },
  composerSafe: {
    backgroundColor: colors.sand,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
});
