import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { ChatScreen } from './app/ChatScreen';

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <ChatScreen />
    </SafeAreaProvider>
  );
}
