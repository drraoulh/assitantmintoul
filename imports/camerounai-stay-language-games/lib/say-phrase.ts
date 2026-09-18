import type { LanguageTrackId, Locale } from "@/lib/types";
import { expressions } from "@/data/expressions";
import { YEMBA_VERIFIED_FR } from "@/data/yemba-verified";
import { MEDUMBA_TAKES } from "@/data/medumba-voicebank";
import { MBOUDA_TAKES } from "@/data/mbouda-voicebank";
import { SHUPAMOM_TAKES } from "@/data/shupamom-voicebank";
import { LANGUAGE_VOICES, trackFromLanguage } from "@/lib/cultural-voice";
import { findStayCity, STAY_CITIES, type StayCity } from "@/data/stay-cities";

export type StayExchange = {
  langId: LanguageTrackId;
  language: string;
  phrase: string;
  pronunciation: string;
  meaningFr: string;
  meaningEn: string;
  tipFr: string;
  tipEn: string;
  listenOnly?: boolean;
  stepId?: string;
  meaningIds?: string[];
};

export type SpeakCue = {
  langId: LanguageTrackId;
  phrase: string;
  pronunciation: string;
  stepId?: string;
};

const fold = (s: string) =>
  s
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/['ʼ‘’`?!.,;:()]/g, "")
    .replace(/\s+/g, " ")
    .trim();

const MEANINGS: { keys: string[]; id: string }[] = [
  { id: "bonjour", keys: ["bonjour", "hello", "salut", "hi", "bonsoir"] },
  { id: "merci", keys: ["merci", "thank you", "thanks"] },
  { id: "au revoir", keys: ["au revoir", "aurevoir", "goodbye", "bye"] },
  { id: "combien", keys: ["combien", "how much", "prix"] },
  { id: "ou", keys: ["ou se trouve", "ou est", "where is", "where"] },
  { id: "oui", keys: ["oui", "yes"] },
  { id: "non", keys: ["non", "no"] },
  { id: "bienvenue", keys: ["bienvenue", "welcome"] },
  { id: "comment allez vous", keys: ["comment allez vous", "comment ca va", "how are you"] },
  { id: "bon appetit", keys: ["bon appetit", "enjoy your meal"] },
  { id: "as tu mange", keys: ["as tu mange", "have you eaten"] },
  { id: "tu tes reveille", keys: ["tu tes reveille", "reveille", "are you awake"] },
  { id: "tu pars ou", keys: ["tu pars ou", "where are you going"] },
  { id: "donne moi", keys: ["donne moi", "give me"] },
];

const LANG_ALIASES: { keys: string[]; langId: LanguageTrackId }[] = [
  { langId: "duala", keys: ["duala", "douala", "sawa"] },
  { langId: "ewondo", keys: ["ewondo", "beti", "fang"] },
  { langId: "yemba", keys: ["yemba", "dschang"] },
  {
    langId: "shupamom",
    keys: ["shupamom", "shupamem", "bamoun", "bamum", "bamun"],
  },
  { langId: "medumba", keys: ["medumba", "bangangte"] },
  { langId: "mbouda", keys: ["mbouda", "ngiemboon", "ngyemboon", "ngienboum"] },
  { langId: "fulfulde", keys: ["fulfulde", "peul", "fula", "pular"] },
];

function meaningOf(text: string) {
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

function langInText(text: string): LanguageTrackId | null {
  const f = fold(text);
  for (const row of LANG_ALIASES) {
    if (row.keys.some((k) => f.includes(fold(k)))) return row.langId;
  }
  return null;
}

function fromExpression(e: (typeof expressions)[number]): StayExchange {
  return {
    langId: trackFromLanguage(e.language),
    language: e.language,
    phrase: e.phrase,
    pronunciation: e.pronunciation,
    meaningFr: e.translationFr,
    meaningEn: e.translationEn,
    tipFr: e.contextFr,
    tipEn: e.contextEn,
  };
}

function yembaExchange(fr: string, en: string, tipFr: string, tipEn: string): StayExchange | null {
  const phrase = YEMBA_VERIFIED_FR[fold(fr)] ?? YEMBA_VERIFIED_FR[fr.toLowerCase()];
  if (!phrase) return null;
  return {
    langId: "yemba",
    language: "Yemba",
    phrase,
    pronunciation: phrase,
    meaningFr: fr,
    meaningEn: en,
    tipFr,
    tipEn,
  };
}

export function exchangesForLang(langId: LanguageTrackId): StayExchange[] {
  if (langId === "yemba") {
    return [
      yembaExchange(
        "Bonjour",
        "Hello",
        "Salut Yemba de Dschang. Tons : allez lentement.",
        "Yemba greeting in Dschang. Tones: go slowly.",
      ),
      yembaExchange(
        "Merci",
        "Thank you",
        "Remerciement vérifié par locuteur.",
        "Thank-you verified with a speaker.",
      ),
      yembaExchange(
        "Au revoir",
        "Goodbye",
        "Congé. Aussi : à bientôt.",
        "Farewell. Also: see you soon.",
      ),
      yembaExchange(
        "Combien ça coûte ?",
        "How much does it cost?",
        "Au marché de Dschang.",
        "At the Dschang market.",
      ),
    ].filter((x): x is StayExchange => Boolean(x));
  }

  if (langId === "medumba") {
    return MEDUMBA_TAKES.filter((t) => t.session === 1 && t.phrase).map((t) => ({
      langId: "medumba" as const,
      language: "Medumba",
      phrase: t.phrase,
      pronunciation: t.pronunciation,
      meaningFr: t.meaningFr,
      meaningEn: t.meaningEn,
      tipFr: t.noteFr,
      tipEn: t.noteEn,
      stepId: t.id,
    }));
  }

  if (langId === "mbouda") {
    return MBOUDA_TAKES.map((t) => ({
      langId: "mbouda" as const,
      language: "Mbouda",
      phrase: t.phrase || "Écoute",
      pronunciation: t.pronunciation,
      meaningFr: t.meaningFr,
      meaningEn: t.meaningEn,
      tipFr: t.noteFr,
      tipEn: t.noteEn,
      listenOnly: true,
      stepId: t.id,
      meaningIds: t.meaningIds,
    }));
  }

  if (langId === "shupamom") {
    return SHUPAMOM_TAKES.filter((t) => t.session === 1 && t.register === "street").map(
      (t) => ({
        langId: "shupamom" as const,
        language: "Shüpamom",
        phrase: t.phrase,
        pronunciation: t.pronunciation,
        meaningFr: t.meaningFr,
        meaningEn: t.meaningEn,
        tipFr: t.noteFr,
        tipEn: t.noteEn,
        stepId: t.id,
      }),
    );
  }

  return expressions
    .filter((e) => trackFromLanguage(e.language) === langId)
    .map(fromExpression);
}

function matchesMeaning(ex: StayExchange, meaningId: string) {
  if (ex.meaningIds?.includes(meaningId)) return true;
  const blob = fold(`${ex.meaningFr} ${ex.meaningEn} ${ex.phrase}`);
  const row = MEANINGS.find((m) => m.id === meaningId);
  if (!row) return blob.includes(meaningId);
  return row.keys.some((k) => blob.includes(fold(k)));
}

function askedLabel(meaningId: string, locale: Locale) {
  const labels: Record<string, { fr: string; en: string }> = {
    bonjour: { fr: "bonjour", en: "hello" },
    merci: { fr: "merci", en: "thank you" },
    "au revoir": { fr: "au revoir", en: "goodbye" },
    combien: { fr: "combien", en: "how much" },
    ou: { fr: "où", en: "where" },
    "bon appetit": { fr: "bon appétit", en: "enjoy your meal" },
    "as tu mange": { fr: "as-tu mangé", en: "have you eaten" },
    "tu tes reveille": { fr: "tu t’es réveillé", en: "are you awake" },
    "tu pars ou": { fr: "tu pars où", en: "where are you going" },
    "donne moi": { fr: "donne-moi", en: "give me" },
  };
  const hit = labels[meaningId];
  if (hit) return locale === "fr" ? hit.fr : hit.en;
  return MEANINGS.find((m) => m.id === meaningId)?.keys[0] ?? meaningId;
}

const SAY_RE =
  /comment\s+(dit[-\s]?on|on\s+dit|dire)|how\s+(do\s+you\s+say|to\s+say|would\s+you\s+say)|que\s+veut\s+dire|what\s+does\s+.+\s+mean|tradui[st]|say\s+.+\s+in\b/i;

const CITY_CHECKIN_RE =
  /^(je\s+suis|on\s+est|nous\s+sommes|i'?m(?:\s+in)?|we\s+are(?:\s+in)?|a|à|in)\b/i;

export function isStayPhraseQuery(query: string) {
  const q = query.trim();
  if (SAY_RE.test(q)) return true;
  if (findStayCity(q) && (CITY_CHECKIN_RE.test(q) || fold(q).split(" ").length <= 3)) {
    return true;
  }
  if (langInText(q) && meaningOf(q)) return true;
  return false;
}

function sayItLine(ex: StayExchange, asked: string | null, locale: Locale) {
  const isFr = locale === "fr";
  const word = asked ?? (isFr ? ex.meaningFr : ex.meaningEn);
  const lang = ex.language;
  if (ex.listenOnly) {
    return isFr
      ? `On dit ${word} en ${lang} comme ça.`
      : `You say ${word} in ${lang} like this.`;
  }
  return isFr
    ? `On dit ${word} en ${lang} : ${ex.phrase}.`
    : `You say ${word} in ${lang}: ${ex.phrase}.`;
}

function speakFrom(ex: StayExchange): SpeakCue {
  return {
    langId: ex.langId,
    phrase: ex.listenOnly ? ex.meaningFr : ex.phrase,
    pronunciation: ex.pronunciation,
    stepId: ex.stepId,
  };
}

export function answerStayPhrase(
  query: string,
  locale: Locale,
): { answer: string; speak?: SpeakCue; city?: StayCity } | null {
  if (!isStayPhraseQuery(query)) return null;

  const isFr = locale === "fr";
  const city = findStayCity(query);
  const langId = langInText(query) ?? city?.langId ?? null;
  const meaning = meaningOf(query);
  const say = SAY_RE.test(query);

  if (!langId && !city && say && meaning) {
    const word = askedLabel(meaning, locale);
    return {
      answer: isFr
        ? `Ça dépend de la ville. Dites-moi où vous êtes, par exemple : comment dit-on ${word} à Douala, à Mbouda, à Foumban…`
        : `It depends on the city. Tell me where you are, for example: how do you say ${word} in Douala, Mbouda, Foumban…`,
    };
  }

  if (!langId) return null;

  const pack = exchangesForLang(langId);
  const voice = LANGUAGE_VOICES[langId];

  const filtered = meaning ? pack.filter((e) => matchesMeaning(e, meaning)) : pack;
  const asked = meaning ? askedLabel(meaning, locale) : null;

  if (meaning && !filtered.length) {
    const recorded = pack
      .slice(0, 4)
      .map((e) => (isFr ? e.meaningFr : e.meaningEn))
      .join(", ");
    return {
      answer: isFr
        ? `Je n’ai pas encore « ${asked} » en ${voice.language} dans les enregistrements. Demandez plutôt : ${recorded || "un mot déjà déposé"}.`
        : `I don’t have “${asked}” in ${voice.language} recordings yet. Try: ${recorded || "a word already deposited"}.`,
      city: city ?? undefined,
    };
  }

  const list = (filtered.length ? filtered : pack).slice(0, 1);
  if (!list.length) {
    return {
      answer: isFr
        ? `Je n’ai pas encore ce mot en ${voice.language}. Le locuteur dicte ; on n’invente pas.`
        : `I don’t have that word in ${voice.language} yet. The speaker dictates; we do not invent.`,
      city: city ?? undefined,
    };
  }

  const first = list[0];
  const word = asked ?? (isFr ? first.meaningFr : first.meaningEn);

  return {
    answer: sayItLine(first, word, locale),
    speak: speakFrom(first),
    city: city ?? undefined,
  };
}

export type CoachTurn = {
  city: StayCity | null;
  text: string;
  exchange?: StayExchange;
  play?: boolean;
  suggestions: string[];
};

const PLAY_RE =
  /\b(commencer|lancer|start|play|jeu|entraine|entraîne|cest parti|c'est parti|on y va|go)\b/i;
const RESET_RE =
  /\b(changer|autre ville|change city|pas (ça|ca|celle)|wrong city)\b/i;

function citySuggestions(locale: Locale) {
  return STAY_CITIES.slice(0, 8).map((c) =>
    locale === "fr" ? c.nameFr : c.nameEn,
  );
}

function afterCitySuggestions(locale: Locale, city: StayCity | null) {
  if (city?.langId === "mbouda") {
    return locale === "fr"
      ? ["Bonjour", "As-tu mangé ?", "Bon appétit", "Commencer le jeu", "Autre ville"]
      : ["Hello", "Have you eaten?", "Enjoy your meal", "Start the game", "Another city"];
  }
  return locale === "fr"
    ? ["Merci", "Au revoir", "Combien", "Commencer le jeu", "Autre ville"]
    : ["Thank you", "Goodbye", "How much", "Start the game", "Another city"];
}

function describeExchange(ex: StayExchange, locale: Locale, asked?: string | null) {
  return sayItLine(ex, asked ?? null, locale);
}

export function coachOpening(locale: Locale): CoachTurn {
  return {
    city: null,
    text:
      locale === "fr"
        ? "Bonjour ! Moi, c’est votre guide. Avant le jeu, j’ai une question : dans quelle ville êtes-vous en ce moment ? Écrivez-moi, ou appuyez sur le micro."
        : "Hello! I’m your guide. Before the game, one question: which city are you in right now? Type it, or tap the mic.",
    suggestions: citySuggestions(locale),
  };
}

export function coachTurn(
  text: string,
  city: StayCity | null,
  locale: Locale,
): CoachTurn {
  const isFr = locale === "fr";
  const raw = text.trim();
  if (!raw) {
    return {
      city,
      text: isFr
        ? "Je vous écoute. Une ville, ou un mot à traduire."
        : "I’m listening. A city, or a word to translate.",
      suggestions: city ? afterCitySuggestions(locale, city) : citySuggestions(locale),
    };
  }

  if (RESET_RE.test(raw)) {
    return {
      city: null,
      text: isFr
        ? "Très bien. Quelle est la ville, maintenant ?"
        : "Alright. Which city now?",
      suggestions: citySuggestions(locale),
    };
  }

  if (PLAY_RE.test(raw)) {
    if (!city) {
      return {
        city: null,
        text: isFr
          ? "On lance le jeu dès que je connais la ville. Où êtes-vous ?"
          : "We’ll start the game as soon as I know the city. Where are you?",
        suggestions: citySuggestions(locale),
      };
    }
    return {
      city,
      play: true,
      text: isFr
        ? `C’est parti. Jeux en ${city.language}, pour ${city.nameFr}. Je vous y emmène.`
        : `Let’s go. Games in ${city.language}, for ${city.nameEn}. I’ll take you there.`,
      suggestions: [],
    };
  }

  const found = findStayCity(raw);
  const meaning = meaningOf(raw);
  const next = found ?? city;

  if (!next) {
    return {
      city: null,
      text: isFr
        ? meaning
          ? "Ça change selon la ville. Dites-moi où vous êtes : Douala, Yaoundé, Foumban, Bangangté…"
          : "Je n’ai pas reconnu la ville. Essayez Douala, Yaoundé, Dschang, Foumban, Mbouda, Maroua…"
        : meaning
          ? "That changes by city. Tell me where you are: Douala, Yaoundé, Foumban, Bangangté…"
          : "I didn’t catch the city. Try Douala, Yaoundé, Dschang, Foumban, Mbouda, Maroua…",
      suggestions: citySuggestions(locale),
    };
  }

  const pack = exchangesForLang(next.langId);
  const want = meaning ?? (found ? "bonjour" : null);
  const ex = want
    ? pack.find((e) => matchesMeaning(e, want))
    : pack[0];

  if (!ex) {
    const booklet = pack
      .slice(0, 5)
      .map((e) => (isFr ? e.meaningFr : e.meaningEn))
      .join(", ");
    return {
      city: next,
      text: isFr
        ? want
          ? `Vous êtes à ${next.nameFr}. Je n’ai pas « ${askedLabel(want, locale)} » dans les enregistrements ${next.language}. Voici ce que le locuteur a déposé : ${booklet || "rien encore"}.`
          : `Vous êtes à ${next.nameFr}. Je n’ai pas encore d’enregistrement ${next.language} pour ce mot.`
        : want
          ? `You’re in ${next.nameEn}. I don’t have “${askedLabel(want, locale)}” in the ${next.language} recordings. The speaker deposited: ${booklet || "nothing yet"}.`
          : `You’re in ${next.nameEn}. I don’t have a ${next.language} recording for that word yet.`,
      suggestions: afterCitySuggestions(locale, next),
    };
  }

  if (found && (!city || city.id !== found.id)) {
    const word = want ? askedLabel(want, locale) : null;
    return {
      city: next,
      exchange: ex,
      text: isFr
        ? `Ah, ${next.nameFr} ! ${sayItLine(ex, word, locale)}`
        : `Ah, ${next.nameEn}! ${sayItLine(ex, word, locale)}`,
      suggestions: afterCitySuggestions(locale, next),
    };
  }

  return {
    city: next,
    exchange: ex,
    text: describeExchange(ex, locale, want ? askedLabel(want, locale) : null),
    suggestions: afterCitySuggestions(locale, next),
  };
}

