/** Split long answers so HTTP TTS stays under Render's request window. */
const MAX_SEGMENT_CHARS = 160;
const FIRST_SEGMENT_CHARS = 72;

export function cleanForSpeech(text: string): string {
  return text
    .replace(/\*\*/g, '')
    .replace(/`+/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function splitForSpeech(text: string): string[] {
  const cleaned = cleanForSpeech(text);
  if (!cleaned) return [];
  const sentences = cleaned.match(/[^.!?…]+[.!?…]*/g) ?? [cleaned];
  const segments: string[] = [];
  let current = '';
  let isFirst = true;

  for (const sentence of sentences) {
    const piece = sentence.trim();
    if (!piece) continue;
    const limit = isFirst ? FIRST_SEGMENT_CHARS : MAX_SEGMENT_CHARS;
    if (!current) {
      current = piece;
    } else if (current.length + piece.length + 1 <= limit) {
      current = `${current} ${piece}`;
    } else {
      segments.push(current);
      isFirst = false;
      current = piece;
    }
    if (isFirst && current.length >= FIRST_SEGMENT_CHARS) {
      const cut = current.lastIndexOf(' ', FIRST_SEGMENT_CHARS);
      if (cut >= 20) {
        segments.push(current.slice(0, cut).trim());
        current = current.slice(cut).trim();
        isFirst = false;
      }
    }
  }
  if (current) segments.push(current);
  return segments;
}

export function speakOnDevice(text: string, locale: string): Promise<void> {
  return new Promise((resolve) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) {
      resolve();
      return;
    }
    const utterance = new SpeechSynthesisUtterance(cleanForSpeech(text));
    utterance.lang = locale.toLowerCase().startsWith('en') ? 'en-US' : 'fr-FR';
    utterance.rate = 0.98;
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  });
}

export function stopDeviceSpeech(): void {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
}
