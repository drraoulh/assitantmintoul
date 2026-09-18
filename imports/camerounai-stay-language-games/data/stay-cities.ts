import type { LanguageTrackId } from "@/lib/types";

export type StayCity = {
  id: string;
  nameFr: string;
  nameEn: string;
  aliases: string[];
  langId: LanguageTrackId;
  language: string;
  regionFr: string;
  regionEn: string;
  noteFr: string;
  noteEn: string;
};

export const STAY_CITIES: StayCity[] = [
  {
    id: "douala",
    nameFr: "Douala",
    nameEn: "Douala",
    aliases: ["douala", "akwa", "bonanjo"],
    langId: "duala",
    language: "Duala",
    regionFr: "Littoral · côte Sawa",
    regionEn: "Littoral · Sawa coast",
    noteFr: "Premier mot dans la rue : Mbolo. On ne précipite pas le salut.",
    noteEn: "First word in the street: Mbolo. Do not rush the greeting.",
  },
  {
    id: "kribi",
    nameFr: "Kribi",
    nameEn: "Kribi",
    aliases: ["kribi"],
    langId: "duala",
    language: "Duala",
    regionFr: "Sud · côte",
    regionEn: "South · coast",
    noteFr: "Même politesse Sawa qu’à Douala : Mbolo d’abord, puis le reste.",
    noteEn: "Same Sawa courtesy as in Douala: Mbolo first, then the rest.",
  },
  {
    id: "limbe",
    nameFr: "Limbé",
    nameEn: "Limbe",
    aliases: ["limbe", "limbé"],
    langId: "duala",
    language: "Duala",
    regionFr: "Sud-Ouest · côte",
    regionEn: "South-West · coast",
    noteFr: "Ville anglophone, mais Duala reste un salut côtier utile.",
    noteEn: "An English-speaking town, but Duala remains a useful coastal greeting.",
  },
  {
    id: "yaounde",
    nameFr: "Yaoundé",
    nameEn: "Yaoundé",
    aliases: ["yaounde", "yaoundé", "yaounde"],
    langId: "ewondo",
    language: "Ewondo",
    regionFr: "Centre · plateau Fang-Beti",
    regionEn: "Centre · Fang-Beti plateau",
    noteFr: "Mbolo aussi, mais le ton ewondo est plus net qu’à la côte. Akiba pour merci.",
    noteEn: "Mbolo too, but the Ewondo tone is crisper than on the coast. Akiba for thank you.",
  },
  {
    id: "dschang",
    nameFr: "Dschang",
    nameEn: "Dschang",
    aliases: ["dschang"],
    langId: "yemba",
    language: "Yemba",
    regionFr: "Ouest · Menoua",
    regionEn: "West · Menoua",
    noteFr: "Tons hauts-bas. Bonjour se dit mŋə́ tsà'tsɛ̀, pas Mbolo.",
    noteEn: "Rise-and-fall tones. Hello is mŋə́ tsà'tsɛ̀, not Mbolo.",
  },
  {
    id: "foumban",
    nameFr: "Foumban",
    nameEn: "Foumban",
    aliases: ["foumban", "bamoun", "bamum"],
    langId: "shupamom",
    language: "Shüpamom",
    regionFr: "Ouest · palais Bamoun",
    regionEn: "West · Bamum palace",
    noteFr: "Me sha’ashe : l’apostrophe est une coupe de gorge, pas un e muet.",
    noteEn: "Me sha’ashe: the apostrophe is a glottal cut, not a silent French e.",
  },
  {
    id: "bangangte",
    nameFr: "Bangangté",
    nameEn: "Bangangté",
    aliases: ["bangangte", "bangangté", "nde", "ndé"],
    langId: "medumba",
    language: "Medumba",
    regionFr: "Ouest · Ndé",
    regionEn: "West · Ndé",
    noteFr: "O zi à ? est une question de salut. Le locuteur dicte le ton.",
    noteEn: "O zi à? is a greeting-question. The speaker dictates the tone.",
  },
  {
    id: "mbouda",
    nameFr: "Mbouda",
    nameEn: "Mbouda",
    aliases: ["mbouda", "ngiemboon", "ngyemboon"],
    langId: "mbouda",
    language: "Mbouda",
    regionFr: "Ouest · Bamboutos",
    regionEn: "West · Bamboutos",
    noteFr: "Ngiemboon de Mbouda. On écoute le locuteur ; on n’invente pas l’orthographe.",
    noteEn: "Ngiemboon of Mbouda. Listen to the speaker; we do not invent the spelling.",
  },
  {
    id: "bafoussam",
    nameFr: "Bafoussam",
    nameEn: "Bafoussam",
    aliases: ["bafoussam"],
    langId: "mbouda",
    language: "Mbouda",
    regionFr: "Ouest · chef-lieu",
    regionEn: "West · regional capital",
    noteFr:
      "À Bafoussam on parle surtout Ghomálá'. Le jeu de séjour le plus proche avec un locuteur, c’est le ngiemboon de Mbouda, à côté.",
    noteEn:
      "In Bafoussam people mainly speak Ghomálá'. The closest stay game with a speaker is Ngiemboon of nearby Mbouda.",
  },
  {
    id: "maroua",
    nameFr: "Maroua",
    nameEn: "Maroua",
    aliases: ["maroua"],
    langId: "fulfulde",
    language: "Fulfulde",
    regionFr: "Extrême-Nord · savane",
    regionEn: "Far North · savannah",
    noteFr: "Jam na ? se dit posément. Ce n’est pas un « hi » jeté.",
    noteEn: "Jam na? is said calmly. It is not a tossed-off “hi”.",
  },
  {
    id: "garoua",
    nameFr: "Garoua",
    nameEn: "Garoua",
    aliases: ["garoua"],
    langId: "fulfulde",
    language: "Fulfulde",
    regionFr: "Nord",
    regionEn: "North",
    noteFr: "Même Fulfulde de séjour qu’à Maroua : Jam, puis Usoko pour merci.",
    noteEn: "The same stay Fulfulde as in Maroua: Jam, then Usoko for thank you.",
  },
  {
    id: "ngaoundere",
    nameFr: "Ngaoundéré",
    nameEn: "Ngaoundéré",
    aliases: ["ngaoundere", "ngaoundéré", "ngaoundere"],
    langId: "fulfulde",
    language: "Fulfulde",
    regionFr: "Adamaoua",
    regionEn: "Adamawa",
    noteFr: "Porte du Nord. Jam na ? ouvre l’échange.",
    noteEn: "Gateway to the North. Jam na? opens the exchange.",
  },
];

const fold = (s: string) =>
  s
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/['ʼ‘’`]/g, "")
    .trim();

export function stayCityById(id: string) {
  return STAY_CITIES.find((c) => c.id === id) ?? null;
}

export function findStayCity(text: string) {
  const f = fold(text);
  return (
    STAY_CITIES.find((c) => c.aliases.some((a) => f.includes(fold(a)))) ??
    STAY_CITIES.find((c) => f.includes(fold(c.nameFr)) || f.includes(fold(c.nameEn))) ??
    null
  );
}
