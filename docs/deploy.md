# Déploiement en ligne (jury)

Objectif : une API permanente, sans tunnel Cloudflare temporaire.

## Backend (Render)

1. Crée un compte sur https://render.com
2. New → Blueprint → connecte le repo `assitantmintoul`
3. Sélectionne `render.yaml` (service `cameroon-ai-tour-guide-api`)
4. Ajoute le secret `HUGGINGFACE_HUB_TOKEN` (Inference Providers)
5. Deploy

Health check : `https://TON-SERVICE.onrender.com/api/health`

## Mobile

Dans `mobile/.env` (ou variables EAS) :

```env
EXPO_PUBLIC_API_URL=https://TON-SERVICE.onrender.com
```

Puis redémarre Expo / rebuild.

## Notes latence

Le backend est réglé pour la vitesse :
- modèle `Qwen/Qwen3.5-9B:fastest`
- réponses plus courtes (`LLM_MAX_TOKENS=380`)
- recherche web sautée si la knowledge base locale suffit
- timeout web 4s max
