import { useState } from 'react';
import {
  Alert,
  Keyboard,
  StyleSheet,
  TextInput,
  View,
} from 'react-native';

import { colors, radius, spacing } from '../../constants/theme';
import { IconCircleButton } from '../ui/IconCircleButton';

interface ChatInputBarProps {
  disabled?: boolean;
  onSend: (message: string) => void;
}

export function ChatInputBar({ disabled = false, onSend }: ChatInputBarProps) {
  const [value, setValue] = useState('');

  const submit = () => {
    const next = value.trim();
    if (!next || disabled) {
      return;
    }
    onSend(next);
    setValue('');
  };

  return (
    <View style={styles.wrap}>
      <IconCircleButton
        name="camera-outline"
        accessibilityLabel="Joindre une photo"
        onPress={() =>
          Alert.alert(
            'Photo',
            "L'analyse d'image sera disponible dans une prochaine phase.",
          )
        }
      />
      <TextInput
        value={value}
        onChangeText={setValue}
        placeholder="Écrire un message…"
        placeholderTextColor={colors.muted}
        multiline
        editable={!disabled}
        style={styles.input}
        onSubmitEditing={() => {
          Keyboard.dismiss();
          submit();
        }}
      />
      <IconCircleButton
        name="mic-outline"
        accessibilityLabel="Parler"
        onPress={() =>
          Alert.alert(
            'Micro',
            'La reconnaissance vocale sera disponible dans une prochaine phase.',
          )
        }
      />
      <IconCircleButton
        name="send"
        variant="solid"
        accessibilityLabel="Envoyer"
        disabled={disabled || value.trim().length === 0}
        onPress={submit}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    backgroundColor: colors.ivory,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: 8,
  },
  input: {
    flex: 1,
    maxHeight: 110,
    minHeight: 42,
    paddingHorizontal: spacing.sm,
    paddingVertical: 10,
    color: colors.ink,
    fontSize: 16,
  },
});
