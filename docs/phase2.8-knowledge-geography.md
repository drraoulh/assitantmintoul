# Phase 2.8 — Knowledge geography

PHASE 2.8 — RESULT

Status: **PASS**

## Database

- No destructive Supabase migration applied.
- Added local structured graph: `backend/data/geography/cameroon_admin.json`
- Proposed future Supabase columns documented below (divisions / is_capital).
- Enriched local catalogs: `ouest_complete.json`, `littoral_complete.json` (+ culture packs)

## Geography

- 10 regions with chef-lieux
- Ouest: 8 départements · Littoral: 4 (Wouri, Sanaga-Maritime, Moungo, Nkam)
- Bafoussam → Mifi → Ouest; Douala → Wouri → Littoral

## Ouest enrichment

- ~30 lieux · culture pack (achu, koki, chefferies, Adys) · 0 restos inventés

## Littoral enrichment

- ~31 lieux · culture pack (ndolé, Sawa, Duala, Krystal Palace) · 0 restos inventés

## Samples

- Bafoussam visit: 3 places — `J’ai actuellement 3 lieu(x) vérifié(s) autour de Bafoussam dans ma base :
- Chefferie de Bafoussam
- Route des artisans (Bafoussam)
- Hauts Plateaux de l'Ouest `
- Douala visit: 8 places — `J’ai actuellement 8 lieu(x) vérifié(s) autour de Douala dans ma base :
- Chutes De Mbang-Ebongo
- Doual'art
- Fleuve Dibamba
- Ile De Manoka
- Jardin Botanique `
- Littoral≠Douala: `Pas exactement. Le Littoral est une région du Cameroun, et Douala en est le chef-lieu.`
- Ndolé: `Plats typiques documentés dans ma base :
- Ndolé : Plat emblématique surtout associé à Douala / Littoral : feuilles amères, arachide, poisson ou viande.
- Poissons et cuisine urbai`
- Sawa: `Le Littoral a pour chef-lieu Douala, capitale économique et hub aérien du Cameroun. Cultures Sawa, estuaire du Wouri, quartiers Bonanjo / Akwa / Bonapriso, et portes vers Edéa (San`

## Agent 2

- Hierarchical retrieval: IN_CITY / NEARBY / IN_REGION scopes
- `knowledge_completeness` + `verified_places_count`
- Geo facts + multi-region culture evidence (Ouest, Littoral)
- Geo facts injected as KnowledgeEvidence (not Qwen knowledge)

## Web fallback

- `WEB_KNOWLEDGE_FALLBACK_ENABLED` (default false)
- When enabled + LOW/NONE completeness → orchestrator may call existing WebSearch
- Results still merged as `[web evidence]` then grounded

## Grounding

- Still enforced; Qwen remains formulation-only
- Geo admin names whitelisted when present in geo evidence

## Tests

- 236 passed, 1 warning in 1.76s
- Checks: {"bafoussam_has_places": true, "bafoussam_not_foumban_as_city": true, "ouest_not_equals_bafoussam": true, "bafoussam_region_ouest": true, "geo_no_planner": true, "around_has_places": true, "ouest_regional": true, "ouest_food_mentions_achu": true, "ouest_culture_evidence": true, "mbapit_located": true, "dschang_hotel_or_soft": true, "douala_has_places": true, "douala_not_edea_as_city": true, "littoral_not_equals_douala": true, "douala_region_littoral": true, "littoral_food_ndole": true, "sawa_culture": true, "littoral_regional": true}

## Performance

- Full 6-turn conversation: **151.5 ms** (deterministic Agent 4, no LLM)
- Geo simple turn: **4.7 ms**, planner=False

## Flags

- `KNOWLEDGE_GEOGRAPHY_ENABLED=false` (default)
- `WEB_KNOWLEDGE_FALLBACK_ENABLED=false` (default)
- Other Phase 2 flags unchanged

## Conclusion

Structured geography answers Bafoussam/Ouest relations without inventing tourism facts. City queries no longer dump the whole West region; nearby/regional scopes are explicit.
