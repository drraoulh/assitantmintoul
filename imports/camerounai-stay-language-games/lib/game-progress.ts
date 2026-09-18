export const XP_CORRECT = 20;
export const XP_MISSION_BONUS = 30;

export type Rank = {
  id: 1 | 2 | 3 | 4 | 5;
  xp: number;
  emoji: string;
  titleFr: string;
  titleEn: string;
  blurbFr: string;
  blurbEn: string;
};

export const RANKS: Rank[] = [
  {
    id: 1,
    xp: 0,
    emoji: "🧳",
    titleFr: "Visiteur",
    titleEn: "Visitor",
    blurbFr: "Vous arrivez. Les premiers mots suffisent déjà à ouvrir une porte.",
    blurbEn: "You have just arrived. The first words already open a door.",
  },
  {
    id: 2,
    xp: 80,
    emoji: "🗺️",
    titleFr: "Explorateur",
    titleEn: "Explorer",
    blurbFr: "Vous vous orientez : marché, taxi, salutations.",
    blurbEn: "You are finding your way: market, taxi, greetings.",
  },
  {
    id: 3,
    xp: 200,
    emoji: "🌍",
    titleFr: "Voyageur averti",
    titleEn: "Seasoned traveller",
    blurbFr: "Vous tenez les phrases de séjour, pas un dictionnaire entier.",
    blurbEn: "You hold the stay phrases — not a whole dictionary.",
  },
  {
    id: 4,
    xp: 400,
    emoji: "🇨🇲",
    titleFr: "Connaisseur du Cameroun",
    titleEn: "Cameroon connoisseur",
    blurbFr: "Aires, régions et usages : vous reliez les lieux aux paroles.",
    blurbEn: "Areas, regions and usage: you connect places to words.",
  },
  {
    id: 5,
    xp: 700,
    emoji: "🏆",
    titleFr: "Ambassadeur culturel",
    titleEn: "Cultural ambassador",
    blurbFr: "Vous pouvez transmettre : langues de séjour et culture du pays.",
    blurbEn: "You can pass it on: stay languages and the country’s culture.",
  },
];

export type Achievement = {
  id: string;
  titleFr: string;
  titleEn: string;
  bodyFr: string;
  bodyEn: string;
  emoji: string;
};

export const ACHIEVEMENTS: Achievement[] = [
  {
    id: "first-mission",
    emoji: "⭐",
    titleFr: "Première mission",
    titleEn: "First mission",
    bodyFr: "Vous avez terminé une Mission Locale.",
    bodyEn: "You completed a Local Mission.",
  },
  {
    id: "four-areas",
    emoji: "🧭",
    titleFr: "Je connais les 4 aires culturelles",
    titleEn: "I know the 4 cultural areas",
    bodyFr: "Sawa, Grassfields, Fang-Beti, Soudano-sahélien.",
    bodyEn: "Sawa, Grassfields, Fang-Beti, Sudano-Sahelian.",
  },
  {
    id: "ten-regions",
    emoji: "🏆",
    titleFr: "Je connais les 10 aires culturelles",
    titleEn: "I know the 10 cultural territories",
    bodyFr:
      "Une mission par région officielle : le Cameroun en dix territoires culturels.",
    bodyEn:
      "One mission per official region: Cameroon in ten cultural territories.",
  },
  {
    id: "survival-four",
    emoji: "🗣️",
    titleFr: "Survie dans les 5 langues de séjour",
    titleEn: "Survival in all 5 stay languages",
    bodyFr:
      "Duala, Yemba, Shüpamom, Ewondo, Fulfulde : les mots pour tenir au quotidien.",
    bodyEn:
      "Duala, Yemba, Shüpamom, Ewondo, Fulfulde: the words that get you through the day.",
  },
  {
    id: "ambassador",
    emoji: "🇨🇲",
    titleFr: "Ambassadeur culturel",
    titleEn: "Cultural ambassador",
    bodyFr: "Rang 5 atteint — pour voyageurs et Camerounais.",
    bodyEn: "Rank 5 reached — for travellers and Cameroonians alike.",
  },
];

export type GameProgress = {
  xp: number;
  expressions: string[];
  missions: string[];
  regions: string[];
  areas: string[];
  achievements: string[];
};

export const EMPTY_PROGRESS: GameProgress = {
  xp: 0,
  expressions: [],
  missions: [],
  regions: [],
  areas: [],
  achievements: [],
};

export const STORAGE_KEY = "vc-game-progress";

export function rankForXp(xp: number): Rank {
  let current = RANKS[0];
  for (const r of RANKS) {
    if (xp >= r.xp) current = r;
  }
  return current;
}

export function nextRank(xp: number): Rank | null {
  const current = rankForXp(xp);
  return RANKS.find((r) => r.id === current.id + 1) ?? null;
}

export function parseProgress(raw: string | null): GameProgress {
  if (!raw) return { ...EMPTY_PROGRESS };
  try {
    const data = JSON.parse(raw) as Partial<GameProgress>;
    return {
      xp: typeof data.xp === "number" ? data.xp : 0,
      expressions: Array.isArray(data.expressions) ? data.expressions : [],
      missions: Array.isArray(data.missions) ? data.missions : [],
      regions: Array.isArray(data.regions) ? data.regions : [],
      areas: Array.isArray(data.areas) ? data.areas : [],
      achievements: Array.isArray(data.achievements) ? data.achievements : [],
    };
  } catch {
    return { ...EMPTY_PROGRESS };
  }
}

function uniq(list: string[], add: string[]) {
  return [...new Set([...list, ...add])];
}

export function applyRewards(
  prev: GameProgress,
  reward: {
    xp?: number;
    expressionId?: string;
    missionId?: string;
    regionId?: string;
    areaId?: string;
  },
): { next: GameProgress; newAchievements: Achievement[]; rankedUp: Rank | null } {
  const before = rankForXp(prev.xp);
  const next: GameProgress = {
    xp: prev.xp + (reward.xp ?? 0),
    expressions: reward.expressionId
      ? uniq(prev.expressions, [reward.expressionId])
      : prev.expressions,
    missions: reward.missionId ? uniq(prev.missions, [reward.missionId]) : prev.missions,
    regions: reward.regionId ? uniq(prev.regions, [reward.regionId]) : prev.regions,
    areas: reward.areaId ? uniq(prev.areas, [reward.areaId]) : prev.areas,
    achievements: prev.achievements,
  };

  const unlocked: string[] = [];
  if (next.missions.length >= 1) unlocked.push("first-mission");
  if (next.areas.length >= 4) unlocked.push("four-areas");
  if (next.regions.length >= 10) unlocked.push("ten-regions");
  const survivalDone = [
    "sawa-survival",
    "grassfields-survival",
    "shupamom-survival",
    "fang-beti-survival",
    "sahel-survival",
  ];
  if (survivalDone.every((id) => next.missions.includes(id))) unlocked.push("survival-four");
  if (rankForXp(next.xp).id >= 5) unlocked.push("ambassador");

  const fresh = unlocked.filter((id) => !next.achievements.includes(id));
  next.achievements = uniq(next.achievements, unlocked);
  const after = rankForXp(next.xp);

  return {
    next,
    newAchievements: ACHIEVEMENTS.filter((a) => fresh.includes(a.id)),
    rankedUp: after.id > before.id ? after : null,
  };
}
