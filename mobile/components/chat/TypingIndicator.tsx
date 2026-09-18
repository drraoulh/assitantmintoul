import { StyleSheet, Text, View } from 'react-native';

import { colors } from '../../constants/theme';

export function TypingIndicator() {
  return (
    <View style={styles.wrap}>
      <View style={styles.dots}>
        <View style={styles.dot} />
        <View style={[styles.dot, styles.mid]} />
        <View style={styles.dot} />
      </View>
      <Text style={styles.label}>Smartmboa Tour réfléchit...</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignSelf: 'flex-start',
    backgroundColor: colors.ivory,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 12,
    maxWidth: '92%',
    gap: 8,
  },
  dots: {
    flexDirection: 'row',
    gap: 6,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: colors.canopy,
    opacity: 0.4,
  },
  mid: {
    opacity: 0.8,
  },
  label: {
    color: colors.muted,
    fontSize: 13,
    fontStyle: 'italic',
  },
});
