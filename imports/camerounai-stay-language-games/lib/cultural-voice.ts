import type { CulturalZone, LanguageTrackId } from "@/lib/types";

export type CulturalVoice = {
  langId: LanguageTrackId;
  areaId: CulturalZone;
  language: string;
  hfId: string;
  hfModel: string;
  preferLangs: string[];
  rate: number;
  slowRate: number;
  pitch: number;
  toneFr: string;
  toneEn: string;
  coachFr: string;
  coachEn: string;
  sample: { phrase: string; pronunciation: string };
};

export const LANGUAGE_VOICES: Record<LanguageTrackId, CulturalVoice> = {
  duala: {
    langId: "duala",
    areaId: "Sawa",
    language: "Duala",
    hfId: "hf:mms-dua",
    hfModel: "facebook/mms-tts-dua",
    preferLangs: ["fr-CM", "en-CM", "fr-SN", "fr-CI", "en-NG", "fr-FR"],
    rate: 0.84,
    slowRate: 0.62,
    pitch: 0.92,
    toneFr:
      "Ton Duala : ouvert, côtier, chaleureux. Deux temps égaux — on ne précipite pas le salut.",
    toneEn:
      "Duala tone: open, coastal, warm. Two even beats — do not rush the greeting.",
    coachFr:
      "Mbolo : mbo-lo. Sourire dans la voix, pas de « r » français.",
    coachEn:
      "Mbolo: mbo-lo. A smile in the voice, no French “r”.",
    sample: { phrase: "Mbolo", pronunciation: "mbo-lo" },
  },
  yemba: {
    langId: "yemba",
    areaId: "Grassfields",
    language: "Yemba",
    hfId: "hf:mms-ybb",
    hfModel: "facebook/mms-tts-ybb",
    preferLangs: ["fr-CM", "en-CM", "en-GB", "fr-FR"],
    rate: 0.7,
    slowRate: 0.5,
    pitch: 1.08,
    toneFr:
      "Ton Yemba : chanté, tons hauts-bas de Dschang. Chaque syllabe a sa hauteur — allez lentement.",
    toneEn:
      "Yemba tone: sung, Dschang rise and fall. Each syllable has its height — go slowly.",
    coachFr:
      "mŋə́ tsà'tsɛ̀ : m-nge / tsa / tse. Le ŋ est un « ng » de nez, pas un n français.",
    coachEn:
      "mŋə́ tsà'tsɛ̀: m-nge / tsa / tse. ŋ is a nasal “ng”, not a French n.",
    sample: { phrase: "mŋə́ tsà'tsɛ̀", pronunciation: "m-nge, tsa, tse" },
  },
  shupamom: {
    langId: "shupamom",
    areaId: "Grassfields",
    language: "Shüpamom",
    hfId: "",
    hfModel: "",
    preferLangs: ["fr-CM", "en-CM", "fr-SN", "en-NG", "fr-FR"],
    rate: 0.64,
    slowRate: 0.46,
    pitch: 0.94,
    toneFr:
      "Ton Shüpamom : palais de Foumban. Posé, royal, pas bamiléké-chanté. L’apostrophe est une coupe de gorge, pas un e muet.",
    toneEn:
      "Shüpamom tone: Foumban palace. Measured, royal — not Bamileke-sung. The apostrophe is a glottal cut, not a silent French e.",
    coachFr:
      "Me sha’ashe : me / sha / (coupe) / she. « Shü » se dit chou, pas « su ». Au palais : plus grave qu’au marché.",
    coachEn:
      "Me sha’ashe: me / sha / (cut) / she. “Shü” is shoo, not “su”. At the palace: lower than at the market.",
    sample: { phrase: "Me sha’ashe", pronunciation: "me, sha, ah, she" },
  },
  medumba: {
    langId: "medumba",
    areaId: "Grassfields",
    language: "Medumba",
    hfId: "",
    hfModel: "",
    preferLangs: ["fr-CM", "en-CM", "fr-FR"],
    rate: 0.7,
    slowRate: 0.5,
    pitch: 1.05,
    toneFr:
      "Ton Medumba : Bamiléké du Ndé (Bangangté). Tons marqués, voyelles ʉ ə ɔ. Le locuteur dicte ; on n’invente pas le mot.",
    toneEn:
      "Medumba tone: Bamileke of the Ndé (Bangangté). Marked tones, vowels ʉ ə ɔ. The speaker dictates; we do not invent the word.",
    coachFr:
      "O zi à ? : o / zi / a. Question de salut, pas un « bonjour » français collé. Tons : allez lentement.",
    coachEn:
      "O zi à?: o / zi / a. A greeting question, not a pasted-on French “bonjour”. Tones: go slowly.",
    sample: { phrase: "O zi à?", pronunciation: "o, zi, a" },
  },
  mbouda: {
    langId: "mbouda",
    areaId: "Grassfields",
    language: "Mbouda",
    hfId: "",
    hfModel: "",
    preferLangs: ["fr-CM", "en-CM", "fr-FR"],
    rate: 0.7,
    slowRate: 0.5,
    pitch: 1.04,
    toneFr:
      "Ton Mbouda : Ngiemboon des Bamboutos. Grassfields, autre ville que Bangangté. Le locuteur dicte ; on n’invente pas le mot.",
    toneEn:
      "Mbouda tone: Ngiemboon of the Bamboutos. Grassfields, a different town from Bangangté. The speaker dictates; we do not invent the word.",
    coachFr:
      "Écoute d’abord. Les fichiers du téléphone portent le français ; la voix est ngiemboon de Mbouda.",
    coachEn:
      "Listen first. The phone files are labelled in French; the voice is Ngiemboon of Mbouda.",
    sample: { phrase: "As-tu mangé ?", pronunciation: "" },
  },
  ewondo: {
    langId: "ewondo",
    areaId: "Fang-Beti",
    language: "Ewondo",
    hfId: "hf:mms-ewo",
    hfModel: "facebook/mms-tts-ewo",
    preferLangs: ["fr-CM", "fr-GA", "fr-CG", "fr-SN", "fr-FR"],
    rate: 0.8,
    slowRate: 0.58,
    pitch: 1.0,
    toneFr:
      "Ton Ewondo : clair, urbain, un cran plus net que sur la côte, voyelles tenues.",
    toneEn:
      "Ewondo tone: clear, urban, a touch crisper than the coast, vowels held.",
    coachFr:
      "Mbolo : mbo-lo. Akiba : a-KI-ba, accent léger au milieu.",
    coachEn:
      "Mbolo: mbo-lo. Akiba: a-KI-ba, light stress in the middle.",
    sample: { phrase: "Mbolo", pronunciation: "mbo-lo" },
  },
  fulfulde: {
    langId: "fulfulde",
    areaId: "Sudano-Sahelian",
    language: "Fulfulde",
    hfId: "hf:cameroon-fulfulde",
    hfModel: "facebook/mms-tts-ful",
    preferLangs: ["fr-CM", "en-NG", "fr-ML", "fr-SN", "fr-FR"],
    rate: 0.7,
    slowRate: 0.5,
    pitch: 0.86,
    toneFr:
      "Ton Fulfulde : posé, grave, presque méditatif. Jam n’est pas un « hi » jeté.",
    toneEn:
      "Fulfulde tone: measured, low, almost meditative. Jam is not a tossed-off “hi”.",
    coachFr:
      "Jam na : djam-na, voyelle longue sur jam. Usoko : ou-so-ko, trois temps égaux.",
    coachEn:
      "Jam na: djam-na, long vowel on jam. Usoko: ou-so-ko, three even beats.",
    sample: { phrase: "Jam na", pronunciation: "djam-na" },
  },
};

const LANG_NAME: Record<string, LanguageTrackId> = {
  duala: "duala",
  yemba: "yemba",
  shupamom: "shupamom",
  "shüpamom": "shupamom",
  shupamem: "shupamom",
  bamum: "shupamom",
  bamoun: "shupamom",
  bamun: "shupamom",
  medumba: "medumba",
  "mədʉmba": "medumba",
  bangangte: "medumba",
  bangangté: "medumba",
  mbouda: "mbouda",
  ngiemboon: "mbouda",
  ngyemboon: "mbouda",
  ngienboum: "mbouda",
  bamboutos: "mbouda",
  ewondo: "ewondo",
  fulfulde: "fulfulde",
};

export function trackFromLanguage(language: string): LanguageTrackId {
  const key = language
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .trim();
  return LANG_NAME[key] ?? "duala";
}

export function languageVoice(langId: LanguageTrackId): CulturalVoice {
  return LANGUAGE_VOICES[langId];
}

/** @deprecated prefer languageVoice — area maps to the first stay language only */
export function culturalVoice(areaId: CulturalZone): CulturalVoice {
  const found = Object.values(LANGUAGE_VOICES).find((v) => v.areaId === areaId);
  return found ?? LANGUAGE_VOICES.duala;
}

/** Turn a phonetic guide into something a TTS engine can pace, with real glottal cuts. */
export function phoneticForSpeech(pronunciation: string, phrase: string) {
  const raw = (pronunciation || phrase).trim();
  if (!raw) return phrase;
  return raw
    .replace(/[ʼ'‘’`]/g, ", ah, ")
    .replace(/[üʉÜ]/g, "u")
    .replace(/shü|shü/gi, "shu")
    .replace(/[ŋŊ]/g, "ng")
    .replace(/[əǝ]/g, "e")
    .replace(/[ɛ]/g, "eh")
    .replace(/[ɔ]/g, "aw")
    .replace(/[áàâ]/gi, "a")
    .replace(/[éèê]/gi, "e")
    .replace(/[íì]/gi, "i")
    .replace(/[óòô]/gi, "o")
    .replace(/[úù]/gi, "u")
    .replace(/[-–—/]/g, ", ")
    .replace(/\s*,\s*,+/g, ", ")
    .replace(/\s+/g, " ")
    .trim();
}

export function looksLocalScript(text: string) {
  return /[ŋəɛɔʉʔʼáàéèíóúü]/i.test(text) || /[ʔ]/.test(text);
}

export function syllablesFromPronunciation(pronunciation: string, phrase: string) {
  const raw = (pronunciation || phrase).trim();
  if (!raw) return phrase;
  return raw
    .replace(/[ʼ'‘’`]/g, " · ")
    .replace(/[-–—/]/g, " · ")
    .replace(/\s+/g, " ")
    .trim();
}

export type CoachCard = {
  syllables: string;
  tone: string;
  tip: string;
  when?: string;
  source: "ai" | "local";
};

export function localCoachCard(
  langId: LanguageTrackId,
  locale: "fr" | "en",
  pronunciation: string,
  phrase: string,
  whenText?: string,
): CoachCard {
  const voice = languageVoice(langId);
  return {
    syllables: syllablesFromPronunciation(pronunciation, phrase),
    tone: locale === "fr" ? voice.toneFr : voice.toneEn,
    tip: locale === "fr" ? voice.coachFr : voice.coachEn,
    when: whenText,
    source: "local",
  };
}
