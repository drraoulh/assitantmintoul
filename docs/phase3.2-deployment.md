# Phase 3.2 — Production deployment (Next.js + FastAPI)

## Architecture (current)

```
https://smartmboa-tour.onrender.com     Expo static (mobile/dist) — LEGACY jury UI
https://smartmboa-web.onrender.com      Next.js Node (frontend-web/) — NEW web UI
https://cameroon-ai-tour-guide-api.onrender.com
        └── FastAPI + Agents 1–4 + KB + Voice WS + Vision
```

Domains above are the **existing / Blueprint-named** Render hostnames.
Do **not** invent custom domains until DNS is configured in Render.

Temporary dual-frontend:

```
Expo static  ──┐
               ├──▶ FastAPI API
Next.js web ───┘
```

Expo is **not** removed until Next.js is validated in production.

## Frontend deployment (Next.js)

Service: `smartmboa-web` in `render.yaml`

| Step | Command |
|------|---------|
| Build | `npm ci && npm run build` (rootDir `frontend-web`) |
| Start | `npm run start` → `next start --hostname 0.0.0.0 --port $PORT` |

Env (public only):

```
NEXT_PUBLIC_API_URL=https://cameroon-ai-tour-guide-api.onrender.com
NODE_VERSION=22.14.0
```

**Never** put in `NEXT_PUBLIC_*`:

- `HUGGINGFACE_HUB_TOKEN` / HF keys
- `GEMINI_API_KEY`
- `FISH_AUDIO_API_KEY`
- Supabase service role / DB passwords

Local:

```bash
cd frontend-web
cp .env.example .env.local
npm install
npm run build
npm run start   # http://127.0.0.1:3000
```

## Backend deployment (unchanged Docker)

Service: `cameroon-ai-tour-guide-api`

- Dockerfile at repo root
- Health: `GET /api/health`
- Voice WS: `wss://cameroon-ai-tour-guide-api.onrender.com/api/voice/session`

## CORS

`CORS_ORIGINS` (production Blueprint):

```
http://localhost:3000,
http://127.0.0.1:3000,
https://smartmboa-tour.onrender.com,
https://smartmboa-web.onrender.com
```

After first Blueprint sync, confirm the Next.js hostname in the Render dashboard
and update `CORS_ORIGINS` if Render assigned a different name.

## WebSocket production

Frontend helper: `getVoiceWebSocketUrl()` in `frontend-web/src/lib/config.ts`

- `https://…` → `wss://…/api/voice/session`
- `http://…` → `ws://…/api/voice/session` (local only)

Streaming order unchanged (TTFA-safe):

```
audio / tokens stream first → turn_done (+ structured UI) later
```

## Environment variables (names only)

### Frontend (`frontend-web/.env.example`)

| Name | Side |
|------|------|
| `NEXT_PUBLIC_API_URL` | public |

### Backend (root `.env.example` + Render secrets)

| Name | Notes |
|------|------|
| `DATABASE_URL` | Postgres / Supabase |
| `DATABASE_ENABLED` | true in prod |
| `HUGGINGFACE_HUB_TOKEN` | secret |
| `GEMINI_API_KEY` | secret |
| `FISH_AUDIO_API_KEY` | secret |
| `CORS_ORIGINS` | explicit origins |
| `AGENT_ORCHESTRATOR_*` | agents on |
| `GROUNDING_ENFORCEMENT_ENABLED` | must stay true |
| `KNOWLEDGE_GEOGRAPHY_ENABLED` | Phase 2.8 |

There is no separate `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` in Settings —
the app uses `DATABASE_URL` (asyncpg). Do not invent unused env vars.

## Tests (pre-deploy)

```bash
# Frontend
cd frontend-web && npm run build && npm run start

# Backend unit (Phase 3.1 structured UI)
cd backend && python3 -m pytest tests/test_chat_response_structured.py -q

# Live API
curl -sS https://cameroon-ai-tour-guide-api.onrender.com/api/health
```

Manual E2E against local Next + prod API (or local API):

1. `/` home
2. `/explorer` regions
3. `/destinations?region=Ouest`
4. `/assistant` — Bafoussam place search (structured `places`)
5. Planifier itinerary
6. Voice (WSS + audio chunks + `turn_done.ui`)
7. Vision upload

## Rollback

| Failure | Action |
|---------|--------|
| Next.js (`smartmboa-web`) broken | Keep using Expo URL `https://smartmboa-tour.onrender.com`; pause/suspend `smartmboa-web` in Render |
| Backend regression | Render → API service → **Rollback** to previous deploy; keep Expo + Next pointed at last good API |
| CORS mistake | Temporarily set `CORS_ORIGINS=*` in Render dashboard, redeploy API, then restore explicit list |

Do **not** delete `mobile/`, `mobile/dist`, or the `smartmboa-tour` static service until Next.js is fully validated.

## Monitoring (existing)

- Voice / chat: PhaseTimer + LLM stream traces (no secrets)
- Structured UI: `structured_build_ms` on ChatResponse / turn_done
- Do not log tokens, passwords, or service-role keys

## Known limitations

- Free Render cold starts (~30–60s+) for API and Node web
- Next.js public URL is live only after Blueprint merge + first successful deploy
- Custom domains (web.smartmboa… / api.smartmboa…) are optional and not configured here
