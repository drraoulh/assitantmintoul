import { useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { ChatScreen } from './app/ChatScreen';
import { ParlerLocalScreen } from './app/ParlerLocalScreen';

type Screen = 'chat' | 'parler-local';

export default function App() {
  const [screen, setScreen] = useState<Screen>('chat');

  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      {screen === 'parler-local' ? (
        <ParlerLocalScreen onBack={() => setScreen('chat')} />
      ) : (
        <ChatScreen onOpenParlerLocal={() => setScreen('parler-local')} />
      )}
    </SafeAreaProvider>
  );
}
