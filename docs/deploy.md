# Déploiement en ligne (jury)

Objectif : une API permanente + une app web, sans tunnel Cloudflare temporaire.

## Services Render (`render.yaml`)

| Service | URL |
|---------|-----|
| **smartmboa-tour** (static, `mobile/dist`) | https://smartmboa-tour.onrender.com |
| **cameroon-ai-tour-guide-api** (Docker) | https://cameroon-ai-tour-guide-api.onrender.com |

### Première fois

1. Compte sur https://render.com
2. New → Blueprint → repo `assitantmintoul` → `render.yaml`
3. Secret API : `HUGGINGFACE_HUB_TOKEN`
4. Deploy

### Mettre à jour l’app web (Parler local, UI…)

```powershell
cd mobile
$env:EXPO_PUBLIC_API_URL="https://cameroon-ai-tour-guide-api.onrender.com"
npm run export:web
cd ..
git add mobile/dist render.yaml
git commit -m "Rebuild smartmboa web for Render"
git push origin master
```

Puis sur https://dashboard.render.com → service **smartmboa-tour** → **Manual Deploy** → **Deploy latest commit** (si Auto-Deploy n’a pas encore tourné).

Health API : https://cameroon-ai-tour-guide-api.onrender.com/api/health

## Mobile local / Expo

```env
EXPO_PUBLIC_API_URL=https://cameroon-ai-tour-guide-api.onrender.com
```

Puis redémarre Expo / rebuild.

## Notes latence

Le backend est réglé pour la vitesse :
- modèle `Qwen/Qwen3.5-9B:fastest`
- réponses plus courtes (`LLM_MAX_TOKENS=380`)
- recherche web sautée si la knowledge base locale suffit
- timeout web 4s max
