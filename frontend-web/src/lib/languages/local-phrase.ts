/**
 * Local Cameroon language coach for the web assistant.
 * Uses native phone recordings under /audio/{Mbouda|medumba}/ — never invents spelling.
 */

export type LocalLangId = 'mbouda' | 'medumba';

export type LocalPhraseHit = {
  answer: string;
  /** Guide line in FR/EN (spoken with preferred African-accent voice when available). */
  guideLine: string;
  langId: LocalLangId;
  language: string;
  meaningFr: string;
  meaningEn: string;
  phrase?: string;
  audioUrl: string | null;
  tipFr: string;
  tipEn: string;
};

type Take = {
  id: string;
  phrase: string;
  meaningFr: string;
  meaningEn: string;
  tipFr: string;
  tipEn: string;
  meaningIds: string[];
  audioUrl: string;
};

const fold = (s: string) =>
  s
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .replace(/['ʼ‘’`?!.,;:()]/g, '')
    .replace(/\s+/g, ' ')
    .trim();

const MEANINGS: { id: string; keys: string[] }[] = [
  {
    id: 'bonjour',
    keys: [
      'bonjour',
      'bon matin',
      'bonne matinee',
      'hello',
      'hi',
      'salut',
      'good morning',
      'good evening',
      'bonsoir',
    ],
  },
  { id: 'merci', keys: ['merci', 'thank you', 'thanks'] },
  { id: 'au revoir', keys: ['au revoir', 'aurevoir', 'goodbye', 'bye'] },
  { id: 'combien', keys: ['combien', 'how much', 'prix'] },
  { id: 'ou', keys: ['ou se trouve', 'ou est', 'where is', 'where'] },
  { id: 'bon appetit', keys: ['bon appetit', 'enjoy your meal'] },
  { id: 'as tu mange', keys: ['as tu mange', 'have you eaten'] },
  { id: 'tu tes reveille', keys: ['tu tes reveille', 'reveille', 'are you awake'] },
  { id: 'tu pars ou', keys: ['tu pars ou', 'where are you going'] },
  { id: 'donne moi', keys: ['donne moi', 'give me'] },
];

const LANG_ALIASES: { langId: LocalLangId; language: string; keys: string[] }[] = [
  {
    langId: 'mbouda',
    language: 'Mbouda',
    keys: ['mbouda', 'ngiemboon', 'ngyemboon', 'ngienboum', 'bamboutos', 'bafoussam'],
  },
  {
    langId: 'medumba',
    language: 'Medumba',
    keys: ['medumba', 'bangangte', 'bangangté', 'nde'],
  },
];

const CITY_TO_LANG: { keys: string[]; langId: LocalLangId }[] = [
  { langId: 'mbouda', keys: ['mbouda', 'bafoussam'] },
  { langId: 'medumba', keys: ['bangangte', 'bangangté'] },
];

const MBOUDA_TAKES: Take[] = [
  {
    id: 'tu-tes-reveille',
    phrase: '',
    meaningFr: 'Tu t’es réveillé ? / Bonjour (matin)',
    meaningEn: 'Are you awake? / Good morning',
    tipFr: 'Salut du matin en ngiemboon. Écoutez le ton — on n’invente pas l’orthographe.',
    tipEn: 'Morning greeting in Ngiemboon. Listen to the tone — we do not invent the spelling.',
    meaningIds: ['bonjour', 'tu tes reveille'],
    audioUrl: '/audio/Mbouda/tu-tes-reveille-normal.mp4',
  },
  {
    id: 'a-tu-mange',
    phrase: '',
    meaningFr: 'As-tu mangé ?',
    meaningEn: 'Have you eaten?',
    tipFr: 'Question de politesse, pas seulement de repas.',
    tipEn: 'A courtesy question, not only about the meal.',
    meaningIds: ['as tu mange'],
    audioUrl: '/audio/Mbouda/a-tu-mange-normal.mp4',
  },
  {
    id: 'bon-appetit',
    phrase: '',
    meaningFr: 'Bon appétit',
    meaningEn: 'Enjoy your meal',
    tipFr: 'À table, à Mbouda.',
    tipEn: 'At the table, in Mbouda.',
    meaningIds: ['bon appetit'],
    audioUrl: '/audio/Mbouda/bon-appetit-normal.mp4',
  },
  {
    id: 'donne-moi',
    phrase: '',
    meaningFr: 'Donne-moi',
    meaningEn: 'Give me',
    tipFr: 'Demande directe.',
    tipEn: 'A direct request.',
    meaningIds: ['donne moi'],
    audioUrl: '/audio/Mbouda/donne-moi-normal.mp4',
  },
  {
    id: 'tu-pars-ou',
    phrase: '',
    meaningFr: 'Tu pars où ?',
    meaningEn: 'Where are you going?',
    tipFr: 'Utile dans la rue, au marché.',
    tipEn: 'Useful in the street, at the market.',
    meaningIds: ['tu pars ou', 'ou'],
    audioUrl: '/audio/Mbouda/tu-pars-ou-normal.mp4',
  },
  {
    id: 'je-pars-ecole',
    phrase: '',
    meaningFr: 'Je pars à l’école',
    meaningEn: 'I’m going to school',
    tipFr: 'Réponse de trajet.',
    tipEn: 'A travel reply.',
    meaningIds: [],
    audioUrl: '/audio/Mbouda/je-pars-ecole-normal.mp4',
  },
];

const MEDUMBA_TAKES: Take[] = [
  {
    id: 'o-zi-a',
    phrase: 'O zi à?',
    meaningFr: 'Bonjour (à une personne)',
    meaningEn: 'Hello / good morning (to one person)',
    tipFr: 'Salut-question. Pas un « bonjour » français collé.',
    tipEn: 'Greeting-question. Not a pasted French “bonjour”.',
    meaningIds: ['bonjour'],
    audioUrl: '/audio/medumba/o-zi-a-normal.mp4',
  },
  {
    id: 'bin-zi-a',
    phrase: 'Bǐn zi à?',
    meaningFr: 'Bonjour (à plusieurs / vouvoiement)',
    meaningEn: 'Hello (to several / polite)',
    tipFr: 'Plus respectueux : aînés, chefferie, marché.',
    tipEn: 'More respectful: elders, chiefdom, market.',
    meaningIds: ['bonjour'],
    audioUrl: '/audio/medumba/bin-zi-a-normal.mp4',
  },
  {
    id: 'nju-yalane',
    phrase: 'Njʉ yα̌lαnə',
    meaningFr: 'Il fait jour (réponse au salut)',
    meaningEn: 'It is daytime (reply to the greeting)',
    tipFr: 'Réponse culturelle au salut.',
    tipEn: 'Cultural reply to the greeting.',
    meaningIds: [],
    audioUrl: '/audio/medumba/nju-yalane-normal.mp4',
  },
  {
    id: 'a-be-we',
    phrase: 'À bə α̂ wə?',
    meaningFr: 'Où ? / Où est-ce ?',
    meaningEn: 'Where? / Where is it?',
    tipFr: 'Question de séjour.',
    tipEn: 'Stay question.',
    meaningIds: ['ou'],
    audioUrl: '/audio/medumba/a-be-we-normal.mp4',
  },
  {
    id: 'o-gho',
    phrase: 'Ɔ̂ ghɔ',
    meaningFr: 'Au revoir',
    meaningEn: 'Goodbye',
    tipFr: 'Congé simple.',
    tipEn: 'Simple farewell.',
    meaningIds: ['au revoir'],
    audioUrl: '/audio/medumba/o-gho-normal.mp4',
  },
  {
    id: 'o-gho-mba',
    phrase: 'Ɔ̂ ghɔ mbὰ',
    meaningFr: 'Au revoir (plus affectueux)',
    meaningEn: 'Goodbye (warmer)',
    tipFr: 'Plus chaleureux.',
    tipEn: 'Warmer farewell.',
    meaningIds: ['au revoir'],
    audioUrl: '/audio/medumba/o-gho-mba-normal.mp4',
  },
];

const PACKS: Record<LocalLangId, Take[]> = {
  mbouda: MBOUDA_TAKES,
  medumba: MEDUMBA_TAKES,
};

const SAY_RE =
  /comment\s+(dit[-\s]?on|on\s+dit|dire)|how\s+(do\s+you\s+say|to\s+say|would\s+you\s+say)|que\s+veut\s+dire|what\s+does\s+.+\s+mean|tradui[st]|say\s+.+\s+in\b|apprendre|learn|prononc/i;

function meaningOf(text: string): string | null {
  const f = fold(text);
  let best: { id: string; len: number } | null = null;
  for (const row of MEANINGS) {
    for (const key of row.keys) {
      const k = fold(key);
      if (f.includes(k) && (!best || k.length > best.len)) {
        best = { id: row.id, len: k.length };
      }
    }
  }
  return best?.id ?? null;
}

function langInText(text: string): { langId: LocalLangId; language: string } | null {
  const f = fold(text);
  for (const row of LANG_ALIASES) {
    if (row.keys.some((k) => f.includes(fold(k)))) {
      return { langId: row.langId, language: row.language };
    }
  }
  for (const row of CITY_TO_LANG) {
    if (row.keys.some((k) => f.includes(fold(k)))) {
      const alias = LANG_ALIASES.find((a) => a.langId === row.langId)!;
      return { langId: row.langId, language: alias.language };
    }
  }
  return null;
}

function askedLabel(meaningId: string, locale: 'fr' | 'en') {
  const labels: Record<string, { fr: string; en: string }> = {
    bonjour: { fr: 'bonjour', en: 'good morning' },
    merci: { fr: 'merci', en: 'thank you' },
    'au revoir': { fr: 'au revoir', en: 'goodbye' },
    combien: { fr: 'combien', en: 'how much' },
    ou: { fr: 'où', en: 'where' },
    'bon appetit': { fr: 'bon appétit', en: 'enjoy your meal' },
    'as tu mange': { fr: 'as-tu mangé', en: 'have you eaten' },
    'tu tes reveille': { fr: 'tu t’es réveillé', en: 'are you awake' },
    'tu pars ou': { fr: 'tu pars où', en: 'where are you going' },
    'donne moi': { fr: 'donne-moi', en: 'give me' },
  };
  const hit = labels[meaningId];
  if (hit) return locale === 'fr' ? hit.fr : hit.en;
  return MEANINGS.find((m) => m.id === meaningId)?.keys[0] ?? meaningId;
}

function matchesMeaning(take: Take, meaningId: string) {
  if (take.meaningIds.includes(meaningId)) return true;
  const blob = fold(`${take.meaningFr} ${take.meaningEn} ${take.phrase}`);
  const row = MEANINGS.find((m) => m.id === meaningId);
  if (!row) return blob.includes(meaningId);
  return row.keys.some((k) => blob.includes(fold(k)));
}

export function isLocalPhraseQuery(query: string): boolean {
  const q = query.trim();
  if (!q) return false;
  const hasLang = Boolean(langInText(q));
  const hasMeaning = Boolean(meaningOf(q));
  if (SAY_RE.test(q) && (hasLang || hasMeaning)) return true;
  if (hasLang && hasMeaning) return true;
  return false;
}

export function answerLocalPhrase(
  query: string,
  locale: 'fr' | 'en',
): LocalPhraseHit | null {
  if (!isLocalPhraseQuery(query)) return null;

  const isFr = locale === 'fr';
  const lang = langInText(query);
  const meaning = meaningOf(query);
  const say = SAY_RE.test(query);

  if (!lang && say && meaning) {
    const word = askedLabel(meaning, locale);
    return {
      answer: isFr
        ? `Ah, ça dépend du coin ! Dis-moi la langue — par exemple : « Comment dit-on ${word} en Mbouda ? » ou « … en Medumba ? »`
        : `Ah, it depends on the place! Tell me the language — for example: “How do you say ${word} in Mbouda?” or “… in Medumba?”`,
      guideLine: isFr
        ? `Dis-moi juste la langue — Mbouda ou Medumba — et je te fais écouter.`
        : `Just tell me the language — Mbouda or Medumba — and I’ll play it for you.`,
      langId: 'mbouda',
      language: '',
      meaningFr: word,
      meaningEn: word,
      audioUrl: null,
      tipFr: '',
      tipEn: '',
    };
  }

  if (!lang) return null;

  const pack = PACKS[lang.langId];
  const filtered = meaning ? pack.filter((t) => matchesMeaning(t, meaning)) : pack;
  const asked = meaning ? askedLabel(meaning, locale) : null;

  if (meaning && !filtered.length) {
    const recorded = pack
      .slice(0, 4)
      .map((t) => (isFr ? t.meaningFr : t.meaningEn))
      .join(', ');
    return {
      answer: isFr
        ? `Pour « ${asked} » en ${lang.language}, je n’ai pas encore la voix du locuteur. Mais j’ai déjà : ${recorded}.`
        : `For “${asked}” in ${lang.language}, I don’t have the speaker’s voice yet. I already have: ${recorded}.`,
      guideLine: isFr
        ? `Désolé mon ami — ce mot-là en ${lang.language}, je ne l’ai pas encore en enregistrement.`
        : `Sorry my friend — that word in ${lang.language}, I don’t have the recording yet.`,
      langId: lang.langId,
      language: lang.language,
      meaningFr: asked ?? '',
      meaningEn: asked ?? '',
      audioUrl: null,
      tipFr: '',
      tipEn: '',
    };
  }

  const take = (filtered.length ? filtered : pack)[0];
  if (!take) return null;

  const word = asked ?? (isFr ? take.meaningFr : take.meaningEn);
  const guideLine = africanGuideLine(word, lang.language, isFr);

  const phraseBit = take.phrase ? `\n\n**${take.phrase}**` : '';
  const tip = isFr ? take.tipFr : take.tipEn;

  return {
    answer: `${guideLine}${phraseBit}\n\n_${tip}_`,
    guideLine,
    langId: lang.langId,
    language: lang.language,
    meaningFr: take.meaningFr,
    meaningEn: take.meaningEn,
    phrase: take.phrase || undefined,
    audioUrl: take.audioUrl,
    tipFr: take.tipFr,
    tipEn: take.tipEn,
  };
}

/** Oral Cameroon / West-African guide tone (spoken + shown). */
function africanGuideLine(word: string, language: string, isFr: boolean): string {
  if (isFr) {
    return `Ah ! Chez nous en ${language}, pour dire ${word}, c’est comme ça. Écoute bien.`;
  }
  return `Ah my friend — in ${language}, we say ${word} like this. Listen well.`;
}
