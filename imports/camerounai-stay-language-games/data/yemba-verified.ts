/**
 * Yemba (Dschang / Menoua) — phrases vérifiées.
 * Sources :
 * - Locuteur (correction Visit Cameroon) : Bonjour → mŋə́ tsà'tsɛ̀
 * - https://www.apprendreleyemba.com (salutations & politesse, dialogues marché / voyage)
 * - Resulam French–Yemba–English Phrasebook (chapitres saluts / adieux)
 *
 * Priorité absolue sur cameroon-int8 et le cache.
 */

/** Clé = français/anglais soft-normalisé → Yemba */
export const YEMBA_VERIFIED_FR: Record<string, string> = {
  // Salutations
  bonjour: "mŋə́ tsà'tsɛ̀",
  hello: "mŋə́ tsà'tsɛ̀",
  salut: "Meŋ ea tsáʼte",
  hi: "Meŋ ea tsáʼte",
  "bonne apres midi": "Mbɔŋmbɔŋ taŋazoko",
  "bonne après-midi": "Mbɔŋmbɔŋ taŋazoko",
  "bonne apres-midi": "Mbɔŋmbɔŋ taŋazoko",
  "good afternoon": "Mbɔŋmbɔŋ taŋazoko",
  bonsoir: "A ea séŋ ei?",
  "bonne nuit": "Mbɔŋmbɔŋ ŋkɔʼɔcwɛt",
  "good morning": "Mbɔŋmbɔŋ ndanjhʉ",
  "good evening": "A ea séŋ ei?",
  "good night": "Mbɔŋmbɔŋ ŋkɔʼɔcwɛt",

  // Politesse
  merci: "Meŋ ea síakne",
  "merci beaucoup": "Meŋ ea síakne",
  "thank you": "Meŋ ea síakne",
  "thanks": "Meŋ ea síakne",
  bienvenue: "zhɛ́ leshʉ́ʼ",
  welcome: "zhɛ́ leshʉ́ʼ",
  "soyez la bienvenue": "pɛ zhɛ́ leshʉ́ʼ",
  "soyez le bienvenu": "pɛ zhɛ́ leshʉ́ʼ",
  "au revoir": "Acʉʼ tetswhi",
  "a bientot": "Acʉʼ tetswhi",
  "à bientôt": "Acʉʼ tetswhi",
  "a la prochaine": "Acʉʼ tetswhi",
  "à la prochaine": "Acʉʼ tetswhi",
  "a plus": "Acʉʼ tetswhi",
  "à plus": "Acʉʼ tetswhi",
  goodbye: "Acʉʼ tetswhi",
  "see you": "Acʉʼ tetswhi",
  "bon voyage": "o zhɛ́ lezíŋ",

  // Santé / nouvelles
  "comment allez-vous": "O ea sáʼ akɔ ɔ?",
  "comment allez-vous ?": "O ea sáʼ akɔ ɔ?",
  "comment ca va": "Álɛkɔ ɔ?",
  "comment ça va": "Álɛkɔ ɔ?",
  "comment ca va ?": "Álɛkɔ ɔ?",
  "comment ça va ?": "Álɛkɔ ɔ?",
  "how are you": "O ea sáʼ akɔ ɔ?",
  "how are you?": "O ea sáʼ akɔ ɔ?",
  "je vais bien": "Meŋ ɛ ntentʉ",
  "je me porte bien": "Meŋ ɛ ntentʉ",
  "i am fine": "Meŋ ɛ ntentʉ",
  "i'm fine": "Meŋ ɛ ntentʉ",

  // Marché / voyage
  "combien ca coute": "eɛ láa a?",
  "combien ça coûte": "eɛ láa a?",
  "combien ca coûte": "eɛ láa a?",
  "combien ça coute": "eɛ láa a?",
  "how much": "eɛ láa a?",
  "how much does it cost": "eɛ láa a?",
  "how much does it cost?": "eɛ láa a?",
  "j'ai compris": "Meŋ ea júʼ",
  "jai compris": "Meŋ ea júʼ",
  "i understand": "Meŋ ea júʼ",

  // Affirmation / négation
  oui: "Mm",
  yes: "Mm",
  non: "ŋgāŋ",
  no: "ŋgāŋ",
  ok: "Apup",
  "d'accord": "Apup",
  daccord: "Apup",
};

/** Yemba → français (formes courantes) */
export const YEMBA_VERIFIED_LOCAL: Record<string, string> = {
  "mŋə́ tsà'tsɛ̀": "Bonjour",
  "mŋə tsà'tsɛ̀": "Bonjour",
  "meŋ ea tsáʼte": "Salut",
  "meŋ ea tsa'te": "Salut",
  "mbɔŋmbɔŋ ndanjhʉ": "Bonjour",
  "mbɔŋmbɔŋ taŋazoko": "Bonne après-midi",
  "mbɔŋmbɔŋ eseŋnjhʉ": "Bonsoir",
  "a ea séŋ ei?": "Bonsoir",
  "a ea seŋ ei?": "Bonsoir",
  "mbɔŋmbɔŋ ŋkɔʼɔcwɛt": "Bonne nuit",
  "meŋ ea síakne": "Merci",
  "meŋ ea siakne": "Merci",
  "zhɛ́ leshʉ́ʼ": "Bienvenue",
  "zhɛ leshʉʼ": "Bienvenue",
  "pɛ zhɛ́ leshʉ́ʼ": "Soyez la bienvenue",
  "acʉʼ tetswhi": "À bientôt",
  "alɛ ncʉʼ tetswhi": "À bientôt",
  "o ea sáʼ akɔ ɔ?": "Comment allez-vous ?",
  "álɛkɔ ɔ?": "Comment ça va ?",
  "meŋ ɛ ntentʉ": "Je vais bien",
  "eɛ láa a?": "Combien ça coûte ?",
  "meŋ ea júʼ": "J’ai compris",
  "o zhɛ́ lezíŋ": "Bon voyage",
  mm: "Oui",
  "ŋgāŋ": "Non",
  "ŋgaŋ": "Non",
  apup: "D’accord",
};
