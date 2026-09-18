/** Native Medumba voicebank — phone recordings dropped in /public/audio/medumba/ */

export type VoiceSpeed = "normal" | "slow";

export type MedumbaTake = {
  id: string;
  phrase: string;
  pronunciation: string;
  meaningFr: string;
  meaningEn: string;
  session: 1 | 2;
  noteFr: string;
  noteEn: string;
};

export const MEDUMBA_AUDIO_DIR = "/audio/medumba";

export const MEDUMBA_TAKES: MedumbaTake[] = [
  {
    id: "o-zi-a",
    phrase: "O zi à?",
    pronunciation: "o, zi, a",
    meaningFr: "Bonjour (à une personne)",
    meaningEn: "Hello (to one person)",
    session: 1,
    noteFr: "Salut-question. Le locuteur confirme tons et à. Pas un « bonjour » français.",
    noteEn: "Greeting-question. Speaker confirms tones and à. Not French “bonjour”.",
  },
  {
    id: "bin-zi-a",
    phrase: "Bǐn zi à?",
    pronunciation: "bin, zi, a",
    meaningFr: "Bonjour (à plusieurs / vouvoiement)",
    meaningEn: "Hello (to several / polite)",
    session: 1,
    noteFr: "Plus respectueux que O zi à ?. Utile chefferie, aînés, marché.",
    noteEn: "More respectful than O zi à?. Chiefdom, elders, market.",
  },
  {
    id: "nju-yalane",
    phrase: "Njʉ yα̌lαnə",
    pronunciation: "nju, ya-la-ne",
    meaningFr: "Il fait jour (réponse culturelle au salut)",
    meaningEn: "It is daytime (cultural reply to the greeting)",
    session: 1,
    noteFr: "On remercie le jour / le Créateur, on ne « répond » pas comme en français.",
    noteEn: "Thanks the day / the Creator; not a French-style reply.",
  },
  {
    id: "a-be-we",
    phrase: "À bə α̂ wə?",
    pronunciation: "a, be, we",
    meaningFr: "Où ? / Où est-ce ?",
    meaningEn: "Where? / Where is it?",
    session: 1,
    noteFr: "Question de séjour. Le locuteur peut dicter la forme courte Â wə ?",
    noteEn: "Stay question. Speaker may dictate the short form Â wə?",
  },
  {
    id: "o-gho",
    phrase: "Ɔ̂ ghɔ",
    pronunciation: "aw, gho",
    meaningFr: "Au revoir",
    meaningEn: "Goodbye",
    session: 1,
    noteFr: "Congé simple. Ɔ̂ comme « o » ouvert, pas « o » français fermé.",
    noteEn: "Simple farewell. Ɔ̂ is an open o, not a closed French o.",
  },
  {
    id: "o-gho-mba",
    phrase: "Ɔ̂ ghɔ mbὰ",
    pronunciation: "aw, gho, mba",
    meaningFr: "Au revoir (plus affectueux)",
    meaningEn: "Goodbye (warmer)",
    session: 1,
    noteFr: "Plus chaleureux. Après un repas, une visite.",
    noteEn: "Warmer. After a meal, a visit.",
  },
  {
    id: "merci",
    phrase: "Merci (forme du locuteur)",
    pronunciation: "à dicter",
    meaningFr: "Merci — le locuteur dicte le mot exact",
    meaningEn: "Thank you — speaker dictates the exact word",
    session: 2,
    noteFr: "On n’invente pas. Il dit le mot, tu notes l’orthographe après coup.",
    noteEn: "Do not invent. He says the word; you write the spelling afterwards.",
  },
  {
    id: "combien",
    phrase: "Combien (forme du locuteur)",
    pronunciation: "à dicter",
    meaningFr: "Combien ça coûte ? — le locuteur dicte",
    meaningEn: "How much? — speaker dictates",
    session: 2,
    noteFr: "Phrase marché. Dicter lentement, tons compris.",
    noteEn: "Market phrase. Dictate slowly, tones included.",
  },
  {
    id: "oui",
    phrase: "Oui (forme du locuteur)",
    pronunciation: "à dicter",
    meaningFr: "Oui — le locuteur dicte",
    meaningEn: "Yes — speaker dictates",
    session: 2,
    noteFr: "Souvent nasal en Grassfields. Écouter, ne pas coller un « oui » français.",
    noteEn: "Often nasal in Grassfields. Listen; do not paste a French “oui”.",
  },
  {
    id: "non",
    phrase: "Non (forme du locuteur)",
    pronunciation: "à dicter",
    meaningFr: "Non — le locuteur dicte",
    meaningEn: "No — speaker dictates",
    session: 2,
    noteFr: "Refus calme.",
    noteEn: "Calm refusal.",
  },
];

const PHRASE_KEY = (phrase: string) =>
  phrase
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/[ʼ'‘’`?!,.]/g, "")
    .replace(/\s+/g, " ")
    .trim();

const STEP_TAKE: Record<string, string> = {
  "md-1": "o-zi-a",
  "md-2": "nju-yalane",
  "md-3": "bin-zi-a",
  "md-4": "a-be-we",
  "md-5": "o-gho",
};

export function medumbaTakeById(id: string) {
  return MEDUMBA_TAKES.find((t) => t.id === id) ?? null;
}

export function medumbaTakeFor(opts: { phrase: string; stepId?: string }) {
  if (opts.stepId && STEP_TAKE[opts.stepId]) {
    return medumbaTakeById(STEP_TAKE[opts.stepId]);
  }
  const key = PHRASE_KEY(opts.phrase);
  return MEDUMBA_TAKES.find((t) => PHRASE_KEY(t.phrase) === key) ?? null;
}

export function medumbaFileCandidates(takeId: string, speed: VoiceSpeed) {
  const stem = `${MEDUMBA_AUDIO_DIR}/${takeId}-${speed}`;
  return [
    `${stem}.mp4`,
    `${stem}.m4a`,
    `${stem}.mp3`,
    `${stem}.wav`,
    `${stem}.aac`,
    `${stem}.ogg`,
    `${stem}.opus`,
    `${stem}.webm`,
  ];
}
