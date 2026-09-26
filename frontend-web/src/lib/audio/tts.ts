/** Split long answers so HTTP TTS stays under Render's request window. */
const MAX_SEGMENT_CHARS = 160;
const FIRST_SEGMENT_CHARS = 72;

export function cleanForSpeech(text: string): string {
  return text
    .replace(/\*\*/g, '')
    .replace(/`+/g, '')
    .replace(/_/g, '')
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

function waitForVoices(): Promise<SpeechSynthesisVoice[]> {
  return new Promise((resolve) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) {
      resolve([]);
      return;
    }
    const existing = window.speechSynthesis.getVoices();
    if (existing.length) {
      resolve(existing);
      return;
    }
    const done = () => {
      window.speechSynthesis.removeEventListener('voiceschanged', done);
      resolve(window.speechSynthesis.getVoices());
    };
    window.speechSynthesis.addEventListener('voiceschanged', done);
    window.setTimeout(done, 400);
  });
}

/**
 * Speak with a warm Cameroon / West-African oral cadence.
 * Picks African locale voices when the browser has them; otherwise tunes rate/pitch.
 */
export async function speakOnDevice(text: string, locale: string): Promise<void> {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;

  const cleaned = cleanForSpeech(text);
  if (!cleaned) return;

  const voices = await waitForVoices();
  const isEn = locale.toLowerCase().startsWith('en');

  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(cleaned);
    // Prefer African locale tags so the engine leans that way even without a named voice.
    utterance.lang = isEn ? 'en-NG' : 'fr-CM';
    // Warm, unhurried oral guide — closer to Cameroon street cadence than default US/FR news TTS.
    utterance.rate = 0.88;
    utterance.pitch = 1.06;
    const voice = pickAfricanVoice(voices, isEn);
    if (voice) {
      utterance.voice = voice;
      if (voice.lang) utterance.lang = voice.lang;
    }
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  });
}

function pickAfricanVoice(
  voices: SpeechSynthesisVoice[],
  english: boolean,
): SpeechSynthesisVoice | null {
  if (!voices.length) return null;

  const preferredLangs = english
    ? ['en-ng', 'en-gh', 'en-ke', 'en-za', 'en-tz', 'en-cm', 'en-ug', 'en-zw']
    : ['fr-cm', 'fr-sn', 'fr-ci', 'fr-cd', 'fr-bf', 'fr-ml', 'fr-tg', 'fr-bj'];

  for (const code of preferredLangs) {
    const hit = voices.find((v) => v.lang?.toLowerCase().replace('_', '-').startsWith(code));
    if (hit) return hit;
  }

  const nameHint = english
    ? /nigeria|ghana|kenya|africa|south africa|cameroon|lagos|accra|nairobi|ibadan/i
    : /cameroun|cameroon|senegal|ivoire|africa|africain|dakar|abidjan|kinshasa|yaound/i;
  const named = voices.find((v) => nameHint.test(`${v.name} ${v.lang}`));
  if (named) return named;

  // British English often sits closer to Cameroonian English rhythm than US default.
  if (english) {
    const gb = voices.find((v) => v.lang?.toLowerCase().startsWith('en-gb'));
    if (gb) return gb;
  }

  return (
    voices.find((v) =>
      v.lang?.toLowerCase().startsWith(english ? 'en' : 'fr'),
    ) ?? null
  );
}

export function stopDeviceSpeech(): void {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
}
