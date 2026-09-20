import { Platform, Share } from 'react-native';

/** Copy text when possible; fall back to the native share sheet. */
export async function copyOrShareText(text: string): Promise<'copied' | 'shared'> {
  const cleaned = text.trim();
  if (!cleaned) {
    throw new Error('Empty text');
  }

  if (
    Platform.OS === 'web' &&
    typeof navigator !== 'undefined' &&
    navigator.clipboard?.writeText
  ) {
    await navigator.clipboard.writeText(cleaned);
    return 'copied';
  }

  await Share.share({ message: cleaned });
  return 'shared';
}
