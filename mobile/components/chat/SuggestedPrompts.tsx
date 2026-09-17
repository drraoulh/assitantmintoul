import { Pressable, StyleSheet, Text, View } from 'react-native';

import { SUGGESTED_PROMPTS } from '../../constants/prompts';
import { colors, radius, spacing } from '../../constants/theme';

interface SuggestedPromptsProps {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
}

export function SuggestedPrompts({ onSelect, disabled = false }: SuggestedPromptsProps) {
  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>Suggestions</Text>
      <View style={styles.list}>
        {SUGGESTED_PROMPTS.map((prompt) => (
          <Pressable
            key={prompt}
            accessibilityRole="button"
            disabled={disabled}
            onPress={() => onSelect(prompt)}
            style={({ pressed }) => [
              styles.chip,
              pressed && styles.pressed,
              disabled && styles.disabled,
            ]}
          >
            <Text style={styles.chipText}>{prompt}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: spacing.sm,
  },
  label: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  list: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  chip: {
    backgroundColor: colors.ivory,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: 14,
    paddingVertical: 10,
    maxWidth: '100%',
  },
  chipText: {
    color: colors.forest,
    fontSize: 13,
    fontWeight: '600',
  },
  pressed: {
    backgroundColor: colors.goldSoft,
  },
  disabled: {
    opacity: 0.5,
  },
});
