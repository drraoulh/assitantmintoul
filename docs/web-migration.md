# SmartMboa Tour — Web Migration

## Architecture actuelle

```
mobile/          Expo + React Native (+ web export → mobile/dist)
backend/         FastAPI + Agents 1–4 + KB + Voice + Vision
```

Production jury aujourd’hui :
- Static : `smartmboa-tour` ← `mobile/dist` (Expo export)
- API : `cameroon-ai-tour-guide-api` ← Docker FastAPI

## Architecture cible

```
frontend-web/    Next.js (App Router) + React + TypeScript
backend/         inchangé (FastAPI, 4 agents, grounding, voice WS…)
mobile/          conservé jusqu’à validation complète du web
```

```
Next.js ──REST/WS──▶ FastAPI ──▶ Agent1 → Agent2 → Agent3 → Agent4
                                      │
                         Supabase / Qwen / Gemini / Whisper / Fish
```

## Pourquoi Next.js

- Expérience Web native (SEO, routing, perf) vs Expo web mono-page chat
- Design touristique multi-pages (Explorer, Destinations, Planner…)
- Réutilise les mêmes contrats API / WebSocket déjà exposés

## Structure frontend

Voir `frontend-web/src/` :
- `app/` pages
- `components/` layout, places, maps, assistant, ui
- `lib/api` client HTTP
- `lib/websocket` voice session
- `lib/regions` 10 régions (admin vérifié)
- `lib/trip-store` Mon voyage (localStorage)

## API

`NEXT_PUBLIC_API_URL` → base FastAPI.

Endpoints utilisés :
- `GET /api/health`
- `POST /api/chat`
- `GET /api/tourist-sites` (+ nearby, `/{id}`)
- `POST /api/vision/identify`
- `POST /api/speech/synthesize`
- `WS /api/voice/session`
- conversations CRUD

## WebSocket / Voice

`VoiceSocket` porte le protocole existant (`token`, `audio_chunk`, …).
Le front lit l’audio dès les chunks (pas d’attente de fin de réponse).

## Vision

Upload → `/api/vision/identify` → prompt guide → `/api/chat`.

## Maps

Leaflet + OpenStreetMap. Marqueurs **uniquement** si `latitude`/`longitude` fournis par l’API.

## Deployment

```bash
cd frontend-web
cp .env.example .env.local
npm install
npm run build
npm start
```

Render : prévoir un service Node/static séparé pointant sur `frontend-web` (Expo `mobile/` reste inchangé).

## Environment variables

| Var | Side | Role |
|-----|------|------|
| `NEXT_PUBLIC_API_URL` | front | URL FastAPI publique |
| HF / Gemini / Fish / Supabase keys | **backend only** | jamais dans le front |

## Tests

- `npm run build` dans `frontend-web`
- Pages : Home, Explorer, Destinations, Assistant, Vision, Planifier, Hotels, Booking, Mon voyage
- Backend unavailable → messages utilisateur génériques

## Migration status

| Étape | Status |
|-------|--------|
| Audit | Done |
| Setup Next.js | Done |
| Design system + layout | Done |
| API client + WS | Done |
| Home / Explorer / Destinations | Done |
| Assistant + ResponseRenderer | Done |
| Map Leaflet | Done |
| Planner / Hotels / Booking demo | Done |
| Vision / Voice | Done (voice basique MediaRecorder) |
| Mon voyage | Done |
| Expo removed | **No** — conservé |
| Production Next on Render | Pending |

## Risks / limitations

- `ChatResponse` HTTP n’expose pas encore `response_type` / `UIBlock` → UI dérivée de `sources` + tourist-sites
- Booking / email = **démonstration front** (pas de provider ni SMTP backend)
- Hotels list = filtre catégorie catalogue ; Ayila’a via assistant si absent du filtre
- Voice web : session courte MediaRecorder (pas encore hands-free continu équivalent Expo)
