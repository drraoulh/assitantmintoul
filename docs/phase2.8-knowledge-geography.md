# Phase 2.8 — Knowledge geography

PHASE 2.8 — RESULT

Status: **PASS**

## Database

- No destructive Supabase migration applied.
- Added local structured graph: `backend/data/geography/cameroon_admin.json`
- Proposed future Supabase columns documented below (divisions / is_capital).
- Enriched catalogs: ouest / littoral / centre / sud (+ culture packs + hotels Ayila’a)

## Geography

- 10 regions · Ouest 8 · Littoral 4 · Centre 4 · Sud 4 (Océan, Mvila, Dja-et-Lobo, Vallée-du-Ntem)

## Region packs

- Ouest · Littoral · Centre · Sud (Kribi/Lobé/Campo) · 0 restos inventés
- Hotels sourcés Ayila’a (Yaoundé, Douala, Kribi, Dschang)

## Samples

- Yaoundé: 8 — `J’ai actuellement 8 lieu(x) vérifié(s) autour de Yaoundé dans ma base :
- Abali Gallery
- Basilique `
- Kribi: 8 — `J’ai actuellement 8 lieu(x) vérifié(s) autour de Kribi dans ma base :
- Chutes de la Lobé
- Kribi Lo`
- Lobé: `Les chutes de la Lobé se trouvent près de Kribi (département de l’Océan, région du Sud).`
- Hotels Yaoundé: `J’ai actuellement 6 lieu(x) vérifié(s) autour de Yaoundé dans ma base :
- Galerie Atelier D'art Afrobantu Mekouti
- La Place De L'indépendance
- Mont Fébé
- Ron`

## Agent 2

- Hierarchical retrieval: IN_CITY / NEARBY / IN_REGION scopes
- `knowledge_completeness` + `verified_places_count`
- Geo facts + multi-region culture evidence (Ouest, Littoral, Centre, Sud)
- Geo facts injected as KnowledgeEvidence (not Qwen knowledge)

## Web fallback

- `WEB_KNOWLEDGE_FALLBACK_ENABLED` (default false)
- When enabled + LOW/NONE completeness → orchestrator may call existing WebSearch
- Results still merged as `[web evidence]` then grounded

## Grounding

- Still enforced; Qwen remains formulation-only
- Geo admin names whitelisted when present in geo evidence

## Tests

- 249 passed, 1 warning in 2.15s
- Checks: {"bafoussam_has_places": true, "bafoussam_not_foumban_as_city": true, "ouest_not_equals_bafoussam": true, "bafoussam_region_ouest": true, "geo_no_planner": true, "around_has_places": true, "ouest_regional": true, "ouest_food_mentions_achu": true, "ouest_culture_evidence": true, "mbapit_located": true, "dschang_hotel_or_soft": true, "douala_has_places": true, "douala_not_edea_as_city": true, "littoral_not_equals_douala": true, "douala_region_littoral": true, "littoral_food_ndole": true, "sawa_culture": true, "littoral_regional": true, "yaounde_has_places": true, "yaounde_not_mbalmayo_as_only": true, "centre_not_equals_yaounde": true, "yaounde_region_centre": true, "centre_food": true, "mokolo_or_culture": true, "centre_regional": true, "kribi_has_places": true, "sud_not_equals_kribi": true, "kribi_region_sud": true, "kribi_food_poisson": true, "lobe_located": true, "yaounde_hotels": true}

## Performance

- Full 6-turn conversation: **302.9 ms** (deterministic Agent 4, no LLM)
- Geo simple turn: **5.8 ms**, planner=False

## Flags

- `KNOWLEDGE_GEOGRAPHY_ENABLED=false` (default)
- `WEB_KNOWLEDGE_FALLBACK_ENABLED=false` (default)
- Other Phase 2 flags unchanged

## Conclusion

Structured geography answers Bafoussam/Ouest relations without inventing tourism facts. City queries no longer dump the whole West region; nearby/regional scopes are explicit.
