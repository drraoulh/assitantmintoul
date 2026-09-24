# Phase 2.8 — Knowledge geography

PHASE 2.8 — RESULT

Status: **PASS**

## Database

- No destructive Supabase migration applied.
- Added local structured graph: `backend/data/geography/cameroon_admin.json`
- Proposed future Supabase columns documented below (divisions / is_capital).
- Enriched local catalog: `data/tourist_sites/ouest_complete.json` (+ culture pack)

## Geography

- 10 regions with chef-lieux
- Ouest: 8 départements (Mifi, Noun, Menoua, Bamboutos, Haut-Nkam, Hauts-Plateaux, Koung-Khi, Ndé)
- Bafoussam → Mifi → Ouest; is_region_capital=true
- Localities: Baleng, Bamougoum, Mbapit, Foumbot, Santchou, Balatchi, …

## Ouest enrichment

- ~30 lieux touristiques sourcés (Supabase + curated)
- Culture pack: plats (achu, koki…), traditions, langues, artisanat, hôtel Adys
- Restaurants nommés vérifiés: **aucun** (policy anti-invention)

## Bafoussam

- Visit query places: 3
- Preview: `J’ai actuellement 3 lieu(x) vérifié(s) autour de Bafoussam dans ma base :
- Chefferie de Bafoussam
- Route des artisans (Bafoussam)
- Hauts Plateaux de l'Ouest (autour de Bafoussam)

Je peux te présen`
- Region Q: `Bafoussam se trouve dans la région de l’Ouest du Cameroun.`
- Ouest≠Bafoussam: `Pas exactement. L’Ouest est une région du Cameroun, et Bafoussam en est le chef-lieu.`
- Food: `Plats typiques de l’Ouest / Grassfields documentés dans ma base :
- Achu : Plat emblématique des Grassfields : taro écrasé avec sauce jaune (souvent associée à l’Ouest / hauts plat`
- Culture: `L’Ouest (Grassfields) regroupe hauts plateaux, chefferies bamiléké, royaume Bamoun à Foumban, artisanat, lacs de cratère et cascades. Bafoussam est le chef-lieu ; Foumban, Dschang,`
- Mbapit: `Le lac et le mont Mbapit se trouvent à Mbapit, entre Foumbot et Foumban (département du Noun, région de l’Ouest).`

## Agent 2

- Hierarchical retrieval: IN_CITY / NEARBY / IN_REGION scopes
- `knowledge_completeness` + `verified_places_count`
- Geo facts + Ouest culture evidence injected as KnowledgeEvidence
- Geo facts injected as KnowledgeEvidence (not Qwen knowledge)

## Web fallback

- `WEB_KNOWLEDGE_FALLBACK_ENABLED` (default false)
- When enabled + LOW/NONE completeness → orchestrator may call existing WebSearch
- Results still merged as `[web evidence]` then grounded

## Grounding

- Still enforced; Qwen remains formulation-only
- Geo admin names whitelisted when present in geo evidence

## Tests

- 230 passed, 1 warning in 1.58s
- Checks: {"bafoussam_has_places": true, "bafoussam_not_foumban_as_city": true, "ouest_not_equals_bafoussam": true, "bafoussam_region_ouest": true, "geo_no_planner": true, "around_has_places": true, "ouest_regional": true, "ouest_food_mentions_achu": true, "ouest_culture_evidence": true, "mbapit_located": true, "dschang_hotel_or_soft": true}

## Performance

- Full 6-turn conversation: **87.9 ms** (deterministic Agent 4, no LLM)
- Geo simple turn: **3.8 ms**, planner=False

## Flags

- `KNOWLEDGE_GEOGRAPHY_ENABLED=false` (default)
- `WEB_KNOWLEDGE_FALLBACK_ENABLED=false` (default)
- Other Phase 2 flags unchanged

## Conclusion

Structured geography answers Bafoussam/Ouest relations without inventing tourism facts. City queries no longer dump the whole West region; nearby/regional scopes are explicit.
