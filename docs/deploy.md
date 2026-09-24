# Déploiement en ligne (jury)

Objectif : une API permanente + frontends web, sans tunnel Cloudflare temporaire.

## Services Render (`render.yaml`)

| Service | URL | Runtime |
|---------|-----|---------|
| **smartmboa-tour** | https://smartmboa-tour.onrender.com | static Expo `mobile/dist` (legacy) |
| **smartmboa-web** | https://smartmboa-web.onrender.com | Next.js `frontend-web/` (new) |
| **cameroon-ai-tour-guide-api** | https://cameroon-ai-tour-guide-api.onrender.com | Docker FastAPI |

Détails : `docs/phase3.2-deployment.md`.

### Première fois

1. Compte sur https://render.com
2. New → Blueprint → repo → `render.yaml`
3. Secrets API dashboard : `HUGGINGFACE_HUB_TOKEN`, `GEMINI_API_KEY`, `FISH_AUDIO_API_KEY`, `DATABASE_URL`
4. Deploy

### Mettre à jour Expo (legacy)

```powershell
cd mobile
$env:EXPO_PUBLIC_API_URL="https://cameroon-ai-tour-guide-api.onrender.com"
npm run export:web
cd ..
git add mobile/dist
git commit -m "Rebuild Expo web for Render"
git push origin master
```

### Mettre à jour Next.js

Push `frontend-web/` sur `master`. Variable :

```
NEXT_PUBLIC_API_URL=https://cameroon-ai-tour-guide-api.onrender.com
```

Health API : https://cameroon-ai-tour-guide-api.onrender.com/api/health

## Mobile local / Expo

```env
EXPO_PUBLIC_API_URL=https://cameroon-ai-tour-guide-api.onrender.com
```

## Next.js local

```env
# frontend-web/.env.local
NEXT_PUBLIC_API_URL=https://cameroon-ai-tour-guide-api.onrender.com
# or http://127.0.0.1:8000 for local API
```

```bash
cd frontend-web && npm install && npm run build && npm run start
```
