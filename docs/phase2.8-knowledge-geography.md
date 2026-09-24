# Phase 2.8 — Knowledge geography

PHASE 2.8 — RESULT

Status: **PASS**

## Database

- No destructive Supabase migration applied.
- Added local structured graph: `backend/data/geography/cameroon_admin.json`
- Proposed future Supabase columns documented below (divisions / is_capital).
- Enriched local catalog: `data/tourist_sites/bafoussam_environs.json`

## Geography

- 10 regions with chef-lieux
- Ouest divisions: Mifi, Noun, Menoua
- Bafoussam → Mifi → Ouest; is_region_capital=true
- Localities: Baleng, Bamougoum (NEAR Bafoussam)

## Bafoussam

- Visit query places: 3
- Preview: `J’ai actuellement 3 lieu(x) vérifié(s) autour de Bafoussam dans ma base :
- Chefferie de Bafoussam
- Route des artisans (Bafoussam)
- Hauts Plateaux de l'Ouest (autour de Bafoussam)

Je peux te présen`
- Region Q: `Bafoussam se trouve dans la région de l’Ouest du Cameroun.`
- Ouest≠Bafoussam: `Pas exactement. L’Ouest est une région du Cameroun, et Bafoussam en est le chef-lieu.`

## Agent 2

- Hierarchical retrieval: IN_CITY / NEARBY / IN_REGION scopes
- `knowledge_completeness` + `verified_places_count`
- Geo facts injected as KnowledgeEvidence (not Qwen knowledge)

## Web fallback

- `WEB_KNOWLEDGE_FALLBACK_ENABLED` (default false)
- When enabled + LOW/NONE completeness → orchestrator may call existing WebSearch
- Results still merged as `[web evidence]` then grounded

## Grounding

- Still enforced; Qwen remains formulation-only
- Geo admin names whitelisted when present in geo evidence

## Tests

- 220 passed, 1 warning in 1.39s
- Checks: {"bafoussam_has_places": true, "bafoussam_not_foumban_as_city": true, "ouest_not_equals_bafoussam": true, "bafoussam_region_ouest": true, "geo_no_planner": true, "around_has_places": true, "ouest_regional": true}

## Performance

- Full 6-turn conversation: **53.4 ms** (deterministic Agent 4, no LLM)
- Geo simple turn: **3.2 ms**, planner=False

## Flags

- `KNOWLEDGE_GEOGRAPHY_ENABLED=false` (default)
- `WEB_KNOWLEDGE_FALLBACK_ENABLED=false` (default)
- Other Phase 2 flags unchanged

## Conclusion

Structured geography answers Bafoussam/Ouest relations without inventing tourism facts. City queries no longer dump the whole West region; nearby/regional scopes are explicit.
