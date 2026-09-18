/** Native Mbouda (Ngiemboon) voicebank — phone recordings in /public/audio/Mbouda/ */

export type VoiceSpeed = "normal" | "slow";

export type MboudaTake = {
  id: string;
  /** Written local form — empty until the speaker dictates spelling. */
  phrase: string;
  pronunciation: string;
  meaningFr: string;
  meaningEn: string;
  session: 1 | 2;
  noteFr: string;
  noteEn: string;
  /** Stay-phrase ids this take answers (never invent a local spelling). */
  meaningIds?: string[];
};

export const MBOUDA_AUDIO_DIR = "/audio/Mbouda";

export const MBOUDA_TAKES: MboudaTake[] = [
  {
    id: "tu-tes-reveille",
    phrase: "",
    pronunciation: "",
    meaningFr: "Tu t’es réveillé ?",
    meaningEn: "Are you awake?",
    session: 1,
    noteFr: "Salut du matin. Le locuteur dicte l’orthographe ngiemboon ; on n’invente pas le mot.",
    noteEn: "Morning greeting. The speaker dictates Ngiemboon spelling; we do not invent the word.",
    meaningIds: ["bonjour", "tu tes reveille"],
  },
  {
    id: "a-tu-mange",
    phrase: "",
    pronunciation: "",
    meaningFr: "As-tu mangé ?",
    meaningEn: "Have you eaten?",
    session: 1,
    noteFr: "Question de politesse, pas seulement de repas.",
    noteEn: "A courtesy question, not only about the meal.",
    meaningIds: ["as tu mange"],
  },
  {
    id: "bon-appetit",
    phrase: "",
    pronunciation: "",
    meaningFr: "Bon appétit",
    meaningEn: "Enjoy your meal",
    session: 1,
    noteFr: "À table, à Mbouda. Écouter le ton, ne pas coller le français.",
    noteEn: "At the table, in Mbouda. Listen to the tone; do not paste in French.",
    meaningIds: ["bon appetit"],
  },
  {
    id: "donne-moi",
    phrase: "",
    pronunciation: "",
    meaningFr: "Donne-moi",
    meaningEn: "Give me",
    session: 1,
    noteFr: "Demande directe. Le locuteur confirme le ton.",
    noteEn: "A direct request. The speaker confirms the tone.",
    meaningIds: ["donne moi"],
  },
  {
    id: "tu-pars-ou",
    phrase: "",
    pronunciation: "",
    meaningFr: "Tu pars où ?",
    meaningEn: "Where are you going?",
    session: 1,
    noteFr: "Question de séjour. Utile dans la rue, au marché.",
    noteEn: "Stay question. Useful in the street, at the market.",
    meaningIds: ["tu pars ou"],
  },
  {
    id: "je-pars-ecole",
    phrase: "",
    pronunciation: "",
    meaningFr: "Je pars à l’école",
    meaningEn: "I’m going to school",
    session: 1,
    noteFr: "Réponse de trajet. Matin, enfants, route de Mbouda.",
    noteEn: "A travel reply. Morning, children, the Mbouda road.",
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
  "mbd-1": "tu-tes-reveille",
  "mbd-2": "a-tu-mange",
  "mbd-3": "bon-appetit",
  "mbd-4": "donne-moi",
  "mbd-5": "tu-pars-ou",
  "mbd-6": "je-pars-ecole",
};

export function mboudaTakeById(id: string) {
  return MBOUDA_TAKES.find((t) => t.id === id) ?? null;
}

export function mboudaTakeFor(opts: { phrase: string; stepId?: string }) {
  if (opts.stepId) {
    const mapped = STEP_TAKE[opts.stepId] ?? opts.stepId;
    const byStep = mboudaTakeById(mapped);
    if (byStep) return byStep;
  }
  const key = PHRASE_KEY(opts.phrase);
  if (!key) return null;
  return (
    MBOUDA_TAKES.find((t) => PHRASE_KEY(t.meaningFr) === key) ??
    MBOUDA_TAKES.find((t) => PHRASE_KEY(t.meaningEn) === key) ??
    MBOUDA_TAKES.find((t) => t.id === key) ??
    null
  );
}

export function mboudaFileCandidates(takeId: string, speed: VoiceSpeed) {
  const dirs = [MBOUDA_AUDIO_DIR, "/audio/mbouda"];
  const exts = [".mp4", ".m4a", ".mp3", ".wav", ".aac", ".ogg", ".opus", ".webm"];
  const urls: string[] = [];
  for (const dir of dirs) {
    const stem = `${dir}/${takeId}-${speed}`;
    for (const ext of exts) urls.push(`${stem}${ext}`);
  }
  return urls;
}
