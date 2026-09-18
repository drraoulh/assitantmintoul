import { useEffect, useRef, useState } from 'react';
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
import { ConversationHistorySheet } from '../components/chat/ConversationHistorySheet';
import { SuggestedPrompts } from '../components/chat/SuggestedPrompts';
import { TypingIndicator } from '../components/chat/TypingIndicator';
import { WelcomeCard } from '../components/chat/WelcomeCard';
import { VoiceConversationMode } from '../components/voice/VoiceConversationMode';
import { colors, spacing } from '../constants/theme';
import { useChat } from '../hooks/useChat';
import { useSpeechPlayback } from '../hooks/useSpeechPlayback';

interface ChatScreenProps {
  onOpenParlerLocal?: () => void;
}

export function ChatScreen({ onOpenParlerLocal }: ChatScreenProps) {
  const {
    messages,
    conversationId,
    isSending,
    backendStatus,
    sendMessage,
    sendImage,
    appendExchange,
    openConversation,
    startNewConversation,
    checkHealth,
  } = useChat();
  const { isSpeaking, speak, stop, playBase64Mp3, unlockWebAudio } =
    useSpeechPlayback();
  const [voiceModeOpen, setVoiceModeOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const scrollRef = useRef<ScrollView>(null);
  const isEmpty = messages.length === 0;

  useEffect(() => {
    scrollRef.current?.scrollToEnd({ animated: true });
  }, [messages, isSending, isSpeaking]);

  return (
    <View style={styles.root}>
      <SafeAreaView edges={['top']} style={styles.topSafe}>
        <ChatHeader
          status={backendStatus}
          onStatusPress={() => void checkHealth()}
          onOpenHistory={() => setHistoryOpen(true)}
          onNewConversation={() => {
            stop();
            void startNewConversation();
          }}
        />
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
          onContentSizeChange={() =>
            scrollRef.current?.scrollToEnd({ animated: true })
          }
        >
          {isEmpty && (
            <View style={styles.empty}>
              <WelcomeCard onOpenParlerLocal={onOpenParlerLocal} />
              <SuggestedPrompts
                disabled={isSending}
                onSelect={(prompt) => void sendMessage(prompt)}
              />
            </View>
          )}

          {messages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message}
              onSpeak={(text) => void speak(text)}
              onStopSpeaking={stop}
              isSpeaking={isSpeaking}
            />
          ))}
          {isSending && <TypingIndicator />}
        </ScrollView>

        <SafeAreaView edges={['bottom']} style={styles.composerSafe}>
          <ChatInputBar
            disabled={isSending}
            onSend={(text) => void sendMessage(text)}
            onSendImage={(uri) => void sendImage(uri)}
            onOpenVoiceMode={() => {
              void unlockWebAudio();
              setVoiceModeOpen(true);
            }}
          />
        </SafeAreaView>
      </KeyboardAvoidingView>

      <ConversationHistorySheet
        visible={historyOpen}
        activeConversationId={conversationId}
        onClose={() => setHistoryOpen(false)}
        onOpenConversation={(id) => {
          stop();
          void openConversation(id);
        }}
        onNewConversation={() => {
          stop();
          void startNewConversation();
        }}
      />

      <VoiceConversationMode
        visible={voiceModeOpen}
        onClose={() => setVoiceModeOpen(false)}
        sendMessage={(text) => sendMessage(text, 'voice')}
        speak={speak}
        stopSpeaking={stop}
        playBase64Mp3={playBase64Mp3}
        unlockWebAudio={unlockWebAudio}
        onExchange={appendExchange}
      />
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
