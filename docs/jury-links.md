# Smartmboa Tour — liens jury

## Application web (interface)
Déployée en static site Render après `npm run export:web`.

## API backend
https://cameroon-ai-tour-guide-api.onrender.com

Health: https://cameroon-ai-tour-guide-api.onrender.com/api/health  
Docs: https://cameroon-ai-tour-guide-api.onrender.com/docs

Dans `mobile/.env` / build web :

```env
EXPO_PUBLIC_API_URL=https://cameroon-ai-tour-guide-api.onrender.com
```

N'oublie pas `HUGGINGFACE_HUB_TOKEN` sur le service API Render pour que le chat réponde.
