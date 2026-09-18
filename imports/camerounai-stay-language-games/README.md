# Import — camerounai / stay-language-games

Source: https://github.com/drraoulh/camerounai/tree/stay-language-games  
Imported as reference assets for Smartmboa Tour (Expo + FastAPI).  
These files are **Next.js / web TypeScript** — they do not run as-is in the mobile app.

## Contents

### `data/` — jeux, phrases, hébergement

| File | Role |
|------|------|
| `games.ts` | Quiz / match / culture game content |
| `missions.ts` | Mission scenarios by language track |
| `medumba-path.ts`, `mbouda-path.ts` | Learning path nodes |
| `medumba-write.ts`, `mbouda-write.ts` | Writing practice items |
| `expressions.ts`, `cameroon-languages.ts`, `yemba-verified.ts` | Phrases / language catalog |
| `medumba-voicebank.ts`, `mbouda-voicebank.ts`, `shupamom-voicebank.ts` | Audio take metadata |
| `hotels.ts`, `stay-cities.ts` | Stay / lodging catalog |

### `lib/` — logique réutilisable

| File | Role |
|------|------|
| `game-progress.ts` | Progress / XP / unlock state |
| `say-phrase.ts` | Phrase lookup + voicebank routing |
| `cultural-voice.ts` | Language track → voice mapping |
| `types.ts` | Shared types (`LanguageTrackId`, etc.) |
| `game-sounds.ts` | UI sound helpers (web Audio API) |

### `audio/`

- `Mbouda/` — recorded takes
- `medumba/` — recorded takes
- `shupamom/` — placeholder only (`.gitkeep` in upstream)

## Porting notes

1. Move curated JSON/TS data into `mobile/` (or seed Supabase) after stripping web-only imports (`@/…`).
2. Rewrite UI with Expo screens; do not copy Next `page.tsx` / DOM components.
3. Point audio assets to `mobile/assets/audio/…` and update voicebank paths.
4. Optional coach API (`/api/games/coach`) can become a FastAPI route later.

## Already wired in mobile

- Screen **Parler local** : `mobile/app/ParlerLocalScreen.tsx`
- Phrases : `mobile/data/expressions.ts`
- Medumba audio samples : `mobile/assets/audio/medumba/`
- Entry from welcome card on the chat home screen
