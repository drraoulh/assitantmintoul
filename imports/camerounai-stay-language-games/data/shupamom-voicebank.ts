/** Native Shüpamom voicebank — record these takes, drop files in /public/audio/shupamom/ */

export type VoiceRegister = "street" | "palace";
export type VoiceSpeed = "normal" | "slow";

export type ShupamomTake = {
  /** Filename stem: `{id}-{normal|slow}.wav` */
  id: string;
  phrase: string;
  pronunciation: string;
  meaningFr: string;
  meaningEn: string;
  register: VoiceRegister;
  session: 1 | 2;
  noteFr: string;
  noteEn: string;
};

export const SHUPAMOM_AUDIO_DIR = "/audio/shupamom";

export const SHUPAMOM_TAKES: ShupamomTake[] = [
  {
    id: "me-shaashe-street",
    phrase: "Me sha’ashe",
    pronunciation: "me, sha, ah, she",
    meaningFr: "Bonjour / je vous salue (rue, marché)",
    meaningEn: "Hello / I greet you (street, market)",
    register: "street",
    session: 1,
    noteFr: "Coupe glottale nette entre sha et she. Pas « chassé ». Ton de marché, un peu plus ouvert.",
    noteEn: "Clear glottal cut between sha and she. Not “chassé”. Market tone, a little more open.",
  },
  {
    id: "me-shaashe-palace",
    phrase: "Me sha’ashe",
    pronunciation: "me, sha, ah, she",
    meaningFr: "Bonjour (palais, plus grave)",
    meaningEn: "Hello (palace, lower)",
    register: "palace",
    session: 1,
    noteFr: "Même mot, voix plus basse, plus posée. Le palais n’est pas l’étal.",
    noteEn: "Same word, lower, more measured. The palace is not the stall.",
  },
  {
    id: "nyinyi-fa-kee-ayue",
    phrase: "Nyinyi fa kee Ayue",
    pronunciation: "nyi-nyi, fa, keh, ah-yweh",
    meaningFr: "Merci",
    meaningEn: "Thank you",
    register: "street",
    session: 1,
    noteFr: "Quatre temps. Ayue un peu plus long. Ne pas avaler nyi-nyi.",
    noteEn: "Four beats. Hold Ayue a little. Do not swallow nyi-nyi.",
  },
  {
    id: "ayue",
    phrase: "Ayue",
    pronunciation: "ah-yweh",
    meaningFr: "Réponse au merci / avec plaisir",
    meaningEn: "Reply to thank you",
    register: "street",
    session: 1,
    noteFr: "Court, chaleureux. C’est la réponse, pas le merci complet.",
    noteEn: "Short, warm. This is the reply, not the full thank-you.",
  },
  {
    id: "hmhm",
    phrase: "Hmhm",
    pronunciation: "mm-hmm",
    meaningFr: "Oui (nasal)",
    meaningEn: "Yes (nasal)",
    register: "street",
    session: 1,
    noteFr: "Oui dans le nez, pas un « oui » français. Deux hums légers.",
    noteEn: "Nasal yes, not a French “oui”. Two light hums.",
  },
  {
    id: "mbey",
    phrase: "Mbey",
    pronunciation: "mbay",
    meaningFr: "Non",
    meaningEn: "No",
    register: "street",
    session: 1,
    noteFr: "mb- collé, pas « bey ». Refus calme, pas un coup de gueule.",
    noteEn: "Keep mb- together, not “bey”. Calm refusal, not a snap.",
  },
  {
    id: "a-mbe-sue",
    phrase: "A mbe sue?",
    pronunciation: "ah, mbeh, sweh",
    meaningFr: "Combien ça coûte ?",
    meaningEn: "How much is this?",
    register: "street",
    session: 1,
    noteFr: "Question montante sur sue. Après le salut, jamais avant.",
    noteEn: "Rising question on sue. After the greeting, never before.",
  },
  {
    id: "maa-njuh-a",
    phrase: "Maa njuh-a",
    pronunciation: "ma, nju, ah",
    meaningFr: "Je ne comprends pas",
    meaningEn: "I don’t understand",
    register: "street",
    session: 1,
    noteFr: "Sans honte, tempo posé. Le -a final est une petite ouverture.",
    noteEn: "No shame, measured tempo. Final -a is a small opening.",
  },
  {
    id: "pe-shiket-mejet",
    phrase: "Pe shiket mejet mejet",
    pronunciation: "pe, shi-ket, me-jet, me-jet",
    meaningFr: "Parlez plus lentement",
    meaningEn: "Please speak more slowly",
    register: "street",
    session: 1,
    noteFr: "mejet répété = lentement. Utile juste après Maa njuh-a.",
    noteEn: "Repeated mejet = slowly. Useful right after Maa njuh-a.",
  },
  {
    id: "poket-pe-zee-kut",
    phrase: "Poket pe zee kut",
    pronunciation: "po-ket, pe, ze, kut",
    meaningFr: "Bienvenue (attention à vos pas)",
    meaningEn: "Welcome (watch your steps)",
    register: "street",
    session: 1,
    noteFr: "Accueil. On veille sur les pas — étal comme palais.",
    noteEn: "Welcome. They watch your steps — stall and palace.",
  },
  {
    id: "me-kwat-mbuo",
    phrase: "Me kwat mbuo",
    pronunciation: "me, kwat, m-bwo",
    meaningFr: "S’il vous plaît",
    meaningEn: "Please",
    register: "street",
    session: 1,
    noteFr: "Négociation posée. mbuo : mb + ouo, pas « bouo » français.",
    noteEn: "Calm bargaining. mbuo: mb + woe, not French “bouo”.",
  },
  {
    id: "u-yi-shu-shupamom",
    phrase: "U yi shu shüpamom?",
    pronunciation: "u, yi, shu, shu-pa-mom",
    meaningFr: "Parlez-vous shüpamom ?",
    meaningEn: "Do you speak Shüpamom?",
    register: "palace",
    session: 1,
    noteFr: "shu = langue. Shü = « chou », jamais « su ». Question de palais / musée.",
    noteEn: "shu = language. Shü = “shoo”, never “su”. Palace / museum question.",
  },
  {
    id: "hmhm-meyet",
    phrase: "Hmhm, meyet",
    pronunciation: "mm-hmm, me-yet",
    meaningFr: "Oui, un peu",
    meaningEn: "Yes, a little",
    register: "palace",
    session: 1,
    noteFr: "Réponse honnête du visiteur. Hmhm nasal, puis meyet.",
    noteEn: "Honest visitor reply. Nasal Hmhm, then meyet.",
  },
  {
    id: "pwo-shia-famju",
    phrase: "Pwo shi’a famju",
    pronunciation: "pwo, shi, ah, fam-ju",
    meaningFr: "Au revoir / à demain",
    meaningEn: "Goodbye / see you tomorrow",
    register: "palace",
    session: 1,
    noteFr: "Coupe dans shi’a. Ce n’est pas le congé yemba.",
    noteEn: "Cut inside shi’a. This is not the Yemba farewell.",
  },
  {
    id: "pa-saa-ne",
    phrase: "Pa sa’a ne?",
    pronunciation: "pa, sa, ah, ne",
    meaningFr: "Comment allez-vous ?",
    meaningEn: "How are you?",
    register: "street",
    session: 2,
    noteFr: "Coupe dans sa’a. Utile hors mission, pour le corpus de tons.",
    noteEn: "Cut inside sa’a. Extra corpus, not on the main mission path.",
  },
  {
    id: "gha-ma",
    phrase: "Gha-ma!",
    pronunciation: "gha, ma",
    meaningFr: "Au secours",
    meaningEn: "Help",
    register: "street",
    session: 2,
    noteFr: "Plus vif. Deux coups. Pas un cri français « aidez-moi ».",
    noteEn: "Sharper. Two beats. Not a French “aidez-moi” shout.",
  },
  {
    id: "tuem",
    phrase: "Tuem",
    pronunciation: "twem",
    meaningFr: "Pardon / désolé",
    meaningEn: "Sorry",
    register: "street",
    session: 2,
    noteFr: "Court. Ton d’excuse, pas de salut.",
    noteEn: "Short. Apology tone, not a greeting.",
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
  "sp-1": "me-shaashe-street",
  "sp-2": "nyinyi-fa-kee-ayue",
  "sp-3": "hmhm",
  "sp-4": "a-mbe-sue",
  "sp-5": "maa-njuh-a",
  "sm-1": "poket-pe-zee-kut",
  "sm-2": "a-mbe-sue",
  "sm-3": "me-kwat-mbuo",
  "sm-4": "nyinyi-fa-kee-ayue",
  "si-1": "me-shaashe-palace",
  "si-2": "u-yi-shu-shupamom",
  "si-3": "pwo-shia-famju",
};

export function shupamomTakeById(id: string) {
  return SHUPAMOM_TAKES.find((t) => t.id === id) ?? null;
}

export function shupamomTakeFor(opts: {
  phrase: string;
  stepId?: string;
}): ShupamomTake | null {
  if (opts.stepId && STEP_TAKE[opts.stepId]) {
    return shupamomTakeById(STEP_TAKE[opts.stepId]);
  }
  const key = PHRASE_KEY(opts.phrase);
  const street = SHUPAMOM_TAKES.find(
    (t) => PHRASE_KEY(t.phrase) === key && t.register === "street",
  );
  return street ?? SHUPAMOM_TAKES.find((t) => PHRASE_KEY(t.phrase) === key) ?? null;
}

export function shupamomFileCandidates(takeId: string, speed: VoiceSpeed) {
  const stem = `${SHUPAMOM_AUDIO_DIR}/${takeId}-${speed}`;
  return [`${stem}.wav`, `${stem}.mp3`, `${stem}.m4a`, `${stem}.webm`];
}
