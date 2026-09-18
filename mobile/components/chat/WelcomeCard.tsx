import { StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing } from '../../constants/theme';

export function WelcomeCard() {
  return (
    <View style={styles.card}>
      <Text style={styles.kicker}>Smartmboa Tour</Text>
      <Text style={styles.title}>Découvrez le Cameroun autrement</Text>
      <Text style={styles.body}>
        Posez une question sur les villes, les parcs, la culture ou un
        itinéraire. Ouvrez « Mode conversation » pour parler au guide :
        vous parlez, il répond à voix haute, puis vous reparlez.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.ivory,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.line,
    gap: spacing.xs,
  },
  kicker: {
    color: colors.canopy,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },
  title: {
    color: colors.ink,
    fontSize: 26,
    fontWeight: '700',
  },
  body: {
    color: colors.muted,
    fontSize: 15,
    lineHeight: 22,
    marginTop: spacing.xs,
  },
});
