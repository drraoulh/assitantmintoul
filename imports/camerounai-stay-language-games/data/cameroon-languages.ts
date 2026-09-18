/**
 * Cameroon languages — French-pivot MT via flagship-ai/cameroon-int8
 * Pairs: francais-{slug} | {slug}-francais (~119 pair folders)
 * @see https://huggingface.co/flagship-ai/cameroon-int8
 */

export type CameroonLang = {
  slug: string;
  nameFr: string;
  nameEn: string;
  /** Standalone Marian on HF Hub (often unavailable on Inference Providers) */
  hubFrToLocal?: string;
  hubLocalToFr?: string;
};

/** Official cameroon-int8 coverage — Yemba first (Visit Cameroon focus language). */
export const CAMEROON_LANGS: CameroonLang[] = [
  { slug: "yemba", nameFr: "Yemba (Dschang / Ouest)", nameEn: "Yemba (Dschang / West)" },
  {
    slug: "shupamom",
    nameFr: "Shüpamom (Bamoun / Foumban)",
    nameEn: "Shüpamom (Bamum / Foumban)",
  },
  { slug: "ewondo", nameFr: "Ewondo", nameEn: "Ewondo" },
  { slug: "aghem", nameFr: "Aghem", nameEn: "Aghem" },
  { slug: "awing", nameFr: "Awing", nameEn: "Awing" },
  { slug: "babanki", nameFr: "Babanki", nameEn: "Babanki" },
  { slug: "bafia", nameFr: "Bafia", nameEn: "Bafia" },
  { slug: "bakoko", nameFr: "Bakoko", nameEn: "Bakoko" },
  { slug: "bakweri", nameFr: "Bakweri", nameEn: "Bakweri" },
  { slug: "bidwee", nameFr: "Bidwee", nameEn: "Bidwee" },
  {
    slug: "bulu",
    nameFr: "Bulu",
    nameEn: "Bulu",
    hubFrToLocal: "flagship-ai/francais-bulu",
    hubLocalToFr: "flagship-ai/bulu-francais",
  },
  { slug: "bum", nameFr: "Bum", nameEn: "Bum" },
  { slug: "cuvok", nameFr: "Cuvok", nameEn: "Cuvok" },
  { slug: "denya", nameFr: "Denya", nameEn: "Denya" },
  { slug: "dii", nameFr: "Dii", nameEn: "Dii" },
  { slug: "doyayo", nameFr: "Doyayo", nameEn: "Doyayo" },
  { slug: "ejagham", nameFr: "Ejagham", nameEn: "Ejagham" },
  { slug: "english", nameFr: "English (pivot CM)", nameEn: "English (CM pivot)" },
  { slug: "esimbi", nameFr: "Esimbi", nameEn: "Esimbi" },
  {
    slug: "fufulde",
    nameFr: "Fulfulde",
    nameEn: "Fulfulde",
    hubFrToLocal: "flagship-ai/francais-fufulde",
    hubLocalToFr: "flagship-ai/fufulde-francais",
  },
  { slug: "gbaya", nameFr: "Gbaya", nameEn: "Gbaya" },
  {
    slug: "ghomala",
    nameFr: "Ghomálá'",
    nameEn: "Ghomala",
    hubFrToLocal: "flagship-ai/francais-ghomala",
    hubLocalToFr: "flagship-ai/ghomala-francais",
  },
  { slug: "guidar", nameFr: "Guidar", nameEn: "Guidar" },
  { slug: "guiziga", nameFr: "Guiziga", nameEn: "Guiziga" },
  { slug: "isu", nameFr: "Isu", nameEn: "Isu" },
  { slug: "kapsiki", nameFr: "Kapsiki", nameEn: "Kapsiki" },
  { slug: "kenyang", nameFr: "Kenyang", nameEn: "Kenyang" },
  { slug: "koonzime", nameFr: "Koonzime", nameEn: "Koonzime" },
  { slug: "lamnso", nameFr: "Lamnsó'", nameEn: "Lamnso" },
  { slug: "limbum", nameFr: "Limbum", nameEn: "Limbum" },
  { slug: "mankon", nameFr: "Mankon", nameEn: "Mankon" },
  { slug: "massana", nameFr: "Massana", nameEn: "Massana" },
  { slug: "mbembe", nameFr: "Mbembe", nameEn: "Mbembe" },
  { slug: "medumba", nameFr: "Medumba", nameEn: "Medumba" },
  { slug: "meta", nameFr: "Meta'", nameEn: "Meta" },
  { slug: "mmen", nameFr: "Mmen", nameEn: "Mmen" },
  { slug: "mofa", nameFr: "Mofa", nameEn: "Mofa" },
  { slug: "mofu", nameFr: "Mofu", nameEn: "Mofu" },
  { slug: "moghamo", nameFr: "Moghamo", nameEn: "Moghamo" },
  { slug: "mpumpong", nameFr: "Mpumpong", nameEn: "Mpumpong" },
  { slug: "mundani", nameFr: "Mundani", nameEn: "Mundani" },
  { slug: "ngi", nameFr: "Ngi", nameEn: "Ngi" },
  { slug: "ngienboum", nameFr: "Ngienboum", nameEn: "Ngienboum" },
  { slug: "ngomba", nameFr: "Ngomba", nameEn: "Ngomba" },
  { slug: "ngombale", nameFr: "Ngombale", nameEn: "Ngombale" },
  { slug: "ngwo", nameFr: "Ngwo", nameEn: "Ngwo" },
  { slug: "nomaande", nameFr: "Nomaande", nameEn: "Nomaande" },
  { slug: "nugunu", nameFr: "Nugunu", nameEn: "Nugunu" },
  { slug: "oku", nameFr: "Oku", nameEn: "Oku" },
  { slug: "pana", nameFr: "Pana", nameEn: "Pana" },
  { slug: "peere", nameFr: "Peere", nameEn: "Peere" },
  {
    slug: "pinyin",
    nameFr: "Pinyin (Grassfields)",
    nameEn: "Pinyin (Grassfields)",
    hubFrToLocal: "flagship-ai/francais-pinyin",
    hubLocalToFr: "flagship-ai/pinyin-francais",
  },
  { slug: "punu", nameFr: "Punu", nameEn: "Punu" },
  { slug: "samba", nameFr: "Samba", nameEn: "Samba" },
  { slug: "tunen", nameFr: "Tunen", nameEn: "Tunen" },
  { slug: "tupuri", nameFr: "Tupuri", nameEn: "Tupuri" },
  { slug: "vute", nameFr: "Vute", nameEn: "Vute" },
  { slug: "weh", nameFr: "Weh", nameEn: "Weh" },
  { slug: "yambeta", nameFr: "Yambeta", nameEn: "Yambeta" },
];

export function getCameroonLang(slug: string) {
  return CAMEROON_LANGS.find((l) => l.slug === slug) ?? null;
}

export function pairFrToLocal(slug: string) {
  return `francais-${slug}`;
}

export function pairLocalToFr(slug: string) {
  return `${slug}-francais`;
}
