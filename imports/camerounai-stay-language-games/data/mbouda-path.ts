import type { MedumbaPathNode } from "@/data/medumba-path";

export const MBOUDA_PATH: MedumbaPathNode[] = [
  {
    id: "translate-day",
    kind: "star",
    lesson: "translate",
    titleFr: "La journée",
    titleEn: "The day",
    offset: 0,
  },
  {
    id: "practice-day",
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
    titleFr: "Tenir à Mbouda",
    titleEn: "Getting through Mbouda",
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
