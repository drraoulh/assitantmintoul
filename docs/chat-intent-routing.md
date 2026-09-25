# SmartMboa — Routage du chat par intention réelle

Le chat choisit ses sources selon **ce que l'utilisateur veut**, pas selon ce que contient la base SmartMboa.
Le Web est la source principale, et la KB sert de complément ; elle ne route jamais.

## Intentions

`IntentResult.chat_intent` est l'intention exposée au client, dans `ChatResponse.routing.chat_intent`.

| chat_intent | Intention interne | Exemple |
|---|---|---|
| `GREETING` | `CLARIFICATION` (salutation) | « Bonjour » |
| `TRAVEL_ROUTE` | `TRAVEL_ROUTE` | « Je veux quitter Yaoundé pour arriver à Buea, que faire ? » |
| `ITINERARY` | `ITINERARY` / `BUDGET_TRIP` (+ origine/destination) | « Je vais de Yaoundé à Buea pendant 3 jours » |
| `PLACE_SEARCH` | `PLACE_SEARCH` | « Que visiter à Buea ? », « Je suis à Yaoundé, que puis-je visiter ? » |
| `PLACE_DETAILS` | `PLACE_DETAILS` | « Horaires du musée national de Yaoundé » |
| `GASTRONOMY` | `FOOD` | « Je veux voir le Eru », « Plat traditionnel du Centre » |
| `RESTAURANT_SEARCH` | `FOOD` + `FORCED_RESTAURANT_SEARCH` | « Où manger du Eru à Buea ? » |
| `HOTEL_SEARCH` | `HOTEL` | « Hôtels à Kribi » |
| `CULTURE` | `CULTURE` | « Tradition du Ngondo » |
| `CURRENT_INFORMATION` | `WEB_SEARCH` | « Festivals ce mois-ci » |
| `IMAGE_SEARCH` | `IMAGE_SEARCH` | « Montre-moi des photos de Kribi » |
| `GENERAL_CHAT` | `SIMPLE_QA` / `TOURISM_INFO` | « Qui est le président du Cameroun ? » |

## Extraction (Agent 1, `intent/extractors.py`)

- **Origine → destination.** Il faut un indice de déplacement (aller, quitter, trajet, bus, get, travel…), puis l'un de ces motifs :
  - `de|depuis|quitter|partir de X … à|vers|pour|jusqu'à Y` ;
  - `entre X et Y` ;
  - `from X to Y` ;
  - `X - Y` ;
  - destination seule : « aller à Y ».
- **La destination est le contexte touristique.** On pose `city = location = destination`, et la région est celle de la destination. L'origine ne sert qu'au trajet : aucune recherche de lieux n'est lancée sur elle.
- **Plat.** `dish` est reconnu dans un lexique de plats camerounais (Eru, Ndolé, Achu, Koki, Nnam ngon, Kpem…).
- **Photos.** `wants_images` vaut vrai pour photo/image/picture, ou pour « voir » suivi d'un plat.
- **Activités.** `wants_activities` vaut vrai pour que faire, que visiter, things to do…
- **Changement de contexte.** Une région ou une ville citée dans le message remplace celle du contexte : « Et le plat du Centre ? » → Centre, plus Sud-Ouest.

## Sources (orchestrateur)

1. **Recherche Web.**
   - `FORCED_*` pour trajet, hôtel, restaurant et actualité ; sinon `WEB_FIRST` pour tout le chat texte.
   - Les requêtes partent en parallèle : jusqu'à 5 pour un trajet, 3 sinon.
2. **Recherche d'images.** Si `wants_images`, un appel `search_images` (Serper `/images`) est lancé en parallèle dès l'intention connue.
3. **KB en complément.**
   - Les lieux sont filtrés par intention (`_scope_places`) : aucun lieu pour un plat ou des photos.
   - Pour un trajet, seulement les lieux de la destination, et uniquement si l'utilisateur demande quoi faire.
4. **Synthèse.** Qwen, ou le rendu déterministe. Ni l'un ni l'autre n'invente : ce qui manque est dit.

### Requêtes d'un trajet (`query_builder.route_queries`)

Pour « Je veux quitter Yaoundé pour arriver à Buea, que faire ? » :

```
transport Yaoundé Buea Cameroun bus agence de voyage
trajet Yaoundé Buea durée route distance
how to travel from Yaoundé to Buea Cameroon
que faire à Buea Cameroun
things to do in Buea Cameroon
```

### Requêtes d'un plat (`query_builder.dish_queries`)

- Pour « Je veux voir le Eru » :
  - `Eru plat traditionnel camerounais`
  - `Eru Cameroonian dish`
  - `Eru Cameroun recette origine`
  - image : `Eru plat camerounais`
- Pour « Où manger du Eru à Buea ? » :
  - `restaurant Eru Buea Cameroun`
  - `où manger Eru à Buea`
  - `best restaurants Eru Buea Cameroon`

## UI (`structured_ui.build_structured_ui`)

| Élément | Affiché pour |
|---|---|
| PlaceCards | `PLACE_LIST`, `PLACE_DETAILS`, `ITINERARY`, `BUDGET_TRIP`, `NATURE`, `HOTEL`, `BOOKING`, `VISION`, `TRAVEL_ROUTE` (lieux de la destination seulement) |
| Carte | Uniquement avec des lieux. Pour un trajet : marqueurs origine et destination, placés à la médiane des lieux du catalogue de chaque ville (pas de coordonnées inventées) |
| Images | `ChatResponse.images`, résultats de la recherche d'images avec le lien vers la page source |
| Jamais | Lieux ou carte pour un plat, un restaurant introuvable dans le catalogue, des photos ou une question générale |

`ChatResponse.routing` contient :
- `chat_intent`, `intent`, `location`, `origin`, `destination` ;
- `dish`, `duration_days`, `wants_images`, `is_route`, `web_reason`.

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `SERPER_API_KEY` | — | Provider Web et images principal (Render → Environment, jamais commité) |
| `WEB_SEARCH_PROVIDER` | `auto` | Serper, puis Tavily, puis Brave, avec le keyless toujours en secours |
| `CHAT_WEB_FIRST_ENABLED` | `true` | Recherche Web pour toutes les intentions conversationnelles en mode texte |
| `CHAT_IMAGE_SEARCH_ENABLED` | `true` | Recherche d'images quand des photos sont demandées |
| `IMAGE_SEARCH_MAX_RESULTS` | `6` | Nombre d'images renvoyées |
| `IMAGE_SEARCH_TIMEOUT_SECONDS` | `6` | Timeout de la recherche d'images |
| `AGENT_ORCHESTRATOR_ENABLED` / `AGENT_ORCHESTRATOR_USE_LLM` | `true` / `true` en prod | Orchestrateur, synthèse par Qwen |
| `HUGGINGFACE_HUB_TOKEN` | — | Qwen |

## Tests

`backend/tests/test_chat_intent_routing_e2e.py` passe les 10 cas obligatoires par `POST /api/chat`, avec l'orchestrateur actif et un provider Web/images qui enregistre les requêtes.

Pour chaque cas, on vérifie :
- le routage ;
- les requêtes réellement envoyées ;
- la présence de sources `WEB` et d'images ;
- l'absence de lieux ou de carte quand ils ne sont pas pertinents.
