import AsyncStorage from '@react-native-async-storage/async-storage';

const LAST_CONVERSATION_KEY = 'cameroon-guide:last-conversation-id';

/** Remember the open thread so the app reopens it after a restart. */
export async function loadLastConversationId(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(LAST_CONVERSATION_KEY);
  } catch {
    return null;
  }
}

export async function saveLastConversationId(id: string): Promise<void> {
  try {
    await AsyncStorage.setItem(LAST_CONVERSATION_KEY, id);
  } catch {
    // Storage is a convenience here; ignore failures.
  }
}

export async function clearLastConversationId(): Promise<void> {
  try {
    await AsyncStorage.removeItem(LAST_CONVERSATION_KEY);
  } catch {
    // ignore
  }
}
