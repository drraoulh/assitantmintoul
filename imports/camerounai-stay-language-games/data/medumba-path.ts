export type PathKind = "star" | "dumbbell" | "chest" | "headphones";

export type MedumbaPathNode = {
  id: string;
  kind: PathKind;
  lesson: "translate" | "practice" | "chest" | "survival";
  titleFr: string;
  titleEn: string;
  offset: number;
};

export const MEDUMBA_PATH: MedumbaPathNode[] = [
  {
    id: "translate-greet",
    kind: "star",
    lesson: "translate",
    titleFr: "Saluts",
    titleEn: "Greetings",
    offset: 0,
  },
  {
    id: "practice-greet",
    kind: "dumbbell",
    lesson: "practice",
    titleFr: "Entraînement",
    titleEn: "Practice",
    offset: -56,
  },
  {
    id: "chest-1",
    kind: "chest",
    lesson: "chest",
    titleFr: "Coffre",
    titleEn: "Chest",
    offset: 48,
  },
  {
    id: "listen-survival",
    kind: "headphones",
    lesson: "survival",
    titleFr: "Tenir à Bangangté",
    titleEn: "Getting through Bangangté",
    offset: -24,
  },
  {
    id: "star-locked",
    kind: "star",
    lesson: "translate",
    titleFr: "À suivre",
    titleEn: "Coming up",
    offset: 40,
  },
];
