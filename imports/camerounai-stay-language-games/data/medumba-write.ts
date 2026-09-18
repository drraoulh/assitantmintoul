import type { LanguageTrackId } from "@/lib/types";

export type WritePrompt = {
  id: string;
  langId: LanguageTrackId;
  phrase: string;
  pronunciation: string;
  /** Canonical French shown after a check */
  french: string;
  /** Word chips that build the French, in order */
  answerTiles: string[];
  distractors: string[];
  /** Accepted typed answers (accents optional) */
  accepted: string[];
  hintFr?: string;
  hintEn?: string;
};

export const MEDUMBA_WRITE_PROMPTS: WritePrompt[] = [
  {
    id: "o-zi-a",
    langId: "medumba",
    phrase: "O zi à?",
    pronunciation: "o, zi, a",
    french: "Bonjour (à une personne)",
    answerTiles: ["Bonjour"],
    distractors: ["Au", "revoir", "Où", "Merci", "Oui"],
    accepted: ["bonjour", "salut", "bonjour a une personne"],
  },
  {
    id: "bin-zi-a",
    langId: "medumba",
    phrase: "Bǐn zi à?",
    pronunciation: "bin, zi, a",
    french: "Bonjour (à plusieurs / vouvoiement)",
    answerTiles: ["Bonjour", "à", "vous"],
    distractors: ["Au", "revoir", "Où", "besoin"],
    accepted: [
      "bonjour",
      "salut",
      "bonjour a plusieurs",
      "bonjour a vous",
      "bonjour (vouvoiement)",
    ],
    hintFr: "Salut à plusieurs personnes, plus respectueux.",
    hintEn: "Greeting to several people, more respectful.",
  },
  {
    id: "nju-yalane",
    langId: "medumba",
    phrase: "Njʉ yα̌lαnə",
    pronunciation: "nju, ya-la-ne",
    french: "Il fait jour",
    answerTiles: ["Il", "fait", "jour"],
    distractors: ["Bonjour", "besoin", "grands", "trois"],
    accepted: [
      "il fait jour",
      "cest le jour",
      "c est le jour",
      "le jour",
      "il est jour",
    ],
    hintFr: "Réponse culturelle au salut — pas « bonjour ».",
    hintEn: "Cultural reply to the greeting — not “hello”.",
  },
  {
    id: "a-be-we",
    langId: "medumba",
    phrase: "À bə α̂ wə?",
    pronunciation: "a, be, we",
    french: "Où ?",
    answerTiles: ["Où"],
    distractors: ["Oui", "Non", "Bonjour", "Merci", "Au"],
    accepted: ["ou", "ou est-ce", "ou est ce", "ou est-ce que"],
  },
  {
    id: "o-gho",
    langId: "medumba",
    phrase: "Ɔ̂ ghɔ",
    pronunciation: "aw, gho",
    french: "Au revoir",
    answerTiles: ["Au", "revoir"],
    distractors: ["Bonjour", "Où", "Merci", "Oui", "un"],
    accepted: ["au revoir", "aurevoir", "adieu"],
  },
  {
    id: "o-gho-mba",
    langId: "medumba",
    phrase: "Ɔ̂ ghɔ mbὰ",
    pronunciation: "aw, gho, mba",
    french: "Au revoir (plus affectueux)",
    answerTiles: ["Au", "revoir"],
    distractors: ["Bonjour", "Où", "grands", "mots", "un"],
    accepted: [
      "au revoir",
      "aurevoir",
      "au revoir plus chaleureux",
      "au revoir affectueux",
      "au revoir plus affectueux",
    ],
    hintFr: "Même adieu, plus chaleureux.",
    hintEn: "The same farewell, warmer.",
  },
];

export function foldAnswer(s: string) {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/[ʼ'‘’`?!.,;:()]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function frenchMatches(input: string, accepted: string[]) {
  const k = foldAnswer(input);
  if (k.length < 2) return false;
  return accepted.some((a) => {
    const ak = foldAnswer(a);
    if (!ak) return false;
    if (k === ak) return true;
    if (ak.includes(" ") && ` ${k} `.includes(` ${ak} `)) return true;
    if (!ak.includes(" ") && ak.length >= 4) {
      return k.split(" ").includes(ak);
    }
    return false;
  });
}
