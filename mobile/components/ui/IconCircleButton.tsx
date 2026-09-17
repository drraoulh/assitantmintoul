import { Ionicons } from '@expo/vector-icons';
import { Pressable, StyleSheet, View } from 'react-native';

import { colors } from '../../constants/theme';

interface IconCircleButtonProps {
  name: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
  accessibilityLabel: string;
  variant?: 'ghost' | 'solid' | 'gold';
  disabled?: boolean;
}

export function IconCircleButton({
  name,
  onPress,
  accessibilityLabel,
  variant = 'ghost',
  disabled = false,
}: IconCircleButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.base,
        variant === 'ghost' && styles.ghost,
        variant === 'solid' && styles.solid,
        variant === 'gold' && styles.gold,
        disabled && styles.disabled,
        pressed && !disabled && styles.pressed,
      ]}
    >
      <View>
        <Ionicons
          name={name}
          size={20}
          color={variant === 'ghost' ? colors.forest : colors.ivory}
        />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ghost: {
    backgroundColor: colors.overlay,
  },
  solid: {
    backgroundColor: colors.forest,
  },
  gold: {
    backgroundColor: colors.clay,
  },
  disabled: {
    opacity: 0.4,
  },
  pressed: {
    opacity: 0.75,
  },
});
