import { useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { ChatScreen } from './app/ChatScreen';
import { ParlerLocalScreen } from './app/ParlerLocalScreen';
import { LocaleProvider } from './i18n';

type Screen = 'chat' | 'parler-local';

export default function App() {
  const [screen, setScreen] = useState<Screen>('chat');

  return (
    <SafeAreaProvider>
      <LocaleProvider>
        <StatusBar style="light" />
        {screen === 'parler-local' ? (
          <ParlerLocalScreen onBack={() => setScreen('chat')} />
        ) : (
          <ChatScreen onOpenParlerLocal={() => setScreen('parler-local')} />
        )}
      </LocaleProvider>
    </SafeAreaProvider>
  );
}
