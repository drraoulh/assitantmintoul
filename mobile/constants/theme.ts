/**
 * Palette derived from the Cameroon flag: green #007A5E, red #CE1126,
 * yellow #FCD116. Green carries the surfaces, yellow the highlights, and red
 * stays an accent (errors, quit actions, flag stripe) so it never overwhelms.
 */
export const colors = {
  // Flag greens
  green: '#007A5E',
  greenDeep: '#00412F',
  greenMid: '#0E9E76',
  greenInk: '#00614A',
  /** Light tint of the flag green: readable on dark green surfaces. */
  mint: '#6FE3B4',

  // Flag red
  red: '#CE1126',
  redDeep: '#9C0C1C',
  redSoft: '#FBE1E4',

  // Flag yellow
  yellow: '#FCD116',
  yellowSoft: '#FFE894',
  yellowInk: '#7A5D00',

  // Legacy names kept so existing styles stay valid.
  forest: '#007A5E',
  forestDeep: '#00412F',
  canopy: '#00614A',
  gold: '#FCD116',
  goldSoft: '#FFE894',
  clay: '#CE1126',

  // Warm neutrals
  sand: '#F5EFE1',
  ivory: '#FFFDF7',
  ink: '#161A18',
  muted: '#5E6B64',
  line: '#E3DCCA',

  // Surfaces & states
  userBubble: '#00563F',
  assistantBubble: '#FFFDF7',
  errorBubble: '#FBE1E4',
  overlay: 'rgba(0, 65, 47, 0.08)',
  success: '#2FA36B',
  warning: '#FCD116',
  danger: '#CE1126',
} as const;

/** Flag stripes, left to right. */
export const flagStripes = [colors.green, colors.red, colors.yellow] as const;

export const spacing = {
  xs: 6,
  sm: 10,
  md: 16,
  lg: 24,
  xl: 32,
} as const;

export const radius = {
  sm: 12,
  md: 18,
  lg: 24,
  pill: 999,
} as const;
