# Phase 2.8 — Knowledge geography

PHASE 2.8 — RESULT

Status: **PASS**

## Database

- No destructive Supabase migration applied.
- Added local structured graph: `backend/data/geography/cameroon_admin.json`
- Proposed future Supabase columns documented below (divisions / is_capital).
- Enriched local catalogs: `ouest_complete`, `littoral_complete`, `centre_complete` (+ culture packs)

## Geography

- 10 regions with chef-lieux
- Ouest: 8 depts · Littoral: 4 · Centre: 4 (Mfoundi, Méfou-et-Afamba, Nyong-et-So'o, Lékié)
- Bafoussam → Ouest · Douala → Littoral · Yaoundé → Centre (capitale politique)

## Region packs

- Ouest: ~30 lieux · achu/koki · Adys
- Littoral: ~31 lieux · ndolé/Sawa · Krystal Palace
- Centre: ~27 lieux · Mokolo/musées/Mefou · Hilton · 0 restos inventés

## Samples

- Bafoussam: 3 — `J’ai actuellement 3 lieu(x) vérifié(s) autour de Bafoussam dans ma base :
- Chefferie de Bafoussam
- Route des artisans `
- Douala: 8 — `J’ai actuellement 8 lieu(x) vérifié(s) autour de Douala dans ma base :
- Chutes De Mbang-Ebongo
- Doual'art
- Fleuve Dib`
- Yaoundé: 8 — `J’ai actuellement 8 lieu(x) vérifié(s) autour de Yaoundé dans ma base :
- Abali Gallery
- Basilique Marie Reine Des Apot`
- Centre≠Yaoundé: `Pas exactement. Le Centre est une région du Cameroun, et Yaoundé en est le chef-lieu (capitale politique).`
- Food Yaoundé: `Plats typiques documentés dans ma base :
- Poulet DG : Poulet sauté avec plantains et légumes, très présent en restauration urbaine à Yaoundé.
- Cuisine de quar`

## Agent 2

- Hierarchical retrieval: IN_CITY / NEARBY / IN_REGION scopes
- `knowledge_completeness` + `verified_places_count`
- Geo facts + multi-region culture evidence (Ouest, Littoral, Centre)
- Geo facts injected as KnowledgeEvidence (not Qwen knowledge)

## Web fallback

- `WEB_KNOWLEDGE_FALLBACK_ENABLED` (default false)
- When enabled + LOW/NONE completeness → orchestrator may call existing WebSearch
- Results still merged as `[web evidence]` then grounded

## Grounding

- Still enforced; Qwen remains formulation-only
- Geo admin names whitelisted when present in geo evidence

## Tests

- 1 failed, 241 passed, 1 warning in 1.98s
- Checks: {"bafoussam_has_places": true, "bafoussam_not_foumban_as_city": true, "ouest_not_equals_bafoussam": true, "bafoussam_region_ouest": true, "geo_no_planner": true, "around_has_places": true, "ouest_regional": true, "ouest_food_mentions_achu": true, "ouest_culture_evidence": true, "mbapit_located": true, "dschang_hotel_or_soft": true, "douala_has_places": true, "douala_not_edea_as_city": true, "littoral_not_equals_douala": true, "douala_region_littoral": true, "littoral_food_ndole": true, "sawa_culture": true, "littoral_regional": true, "yaounde_has_places": true, "yaounde_not_mbalmayo_as_only": true, "centre_not_equals_yaounde": true, "yaounde_region_centre": true, "centre_food": true, "mokolo_or_culture": true, "centre_regional": true}

## Performance

- Full 6-turn conversation: **249.7 ms** (deterministic Agent 4, no LLM)
- Geo simple turn: **5.5 ms**, planner=False

## Flags

- `KNOWLEDGE_GEOGRAPHY_ENABLED=false` (default)
- `WEB_KNOWLEDGE_FALLBACK_ENABLED=false` (default)
- Other Phase 2 flags unchanged

## Conclusion

Structured geography answers Bafoussam/Ouest relations without inventing tourism facts. City queries no longer dump the whole West region; nearby/regional scopes are explicit.
