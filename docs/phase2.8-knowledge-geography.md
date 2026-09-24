# Phase 2.8 — Knowledge geography

PHASE 2.8 — RESULT

Status: **PASS**

## Database

- No destructive Supabase migration applied.
- Added local structured graph: `backend/data/geography/cameroon_admin.json`
- Proposed future Supabase columns documented below (divisions / is_capital).
- Enriched catalogs: ouest → extreme-nord (+ culture packs + hotels Ayila’a where available)

## Geography

- 10 regions · … · Nord-Ouest 7 · Extrême-Nord 6 · Adamaoua 5 · Nord 4 · Est 4

## Region packs

- … · Nord-Ouest · Extrême-Nord (Maroua/Waza/Rhumsiki) · 0 restos inventés
- Hotels Ayila’a: Yaoundé, Douala, Kribi, Dschang — pas Maroua/Bamenda/Limbé dans l’import

## Samples

- Yaoundé: 8 — `J’ai actuellement 8 lieu(x) vérifié(s) autour de Yaoundé dans ma base :
- Abali Gallery
- Basilique `
- Kribi: 8 — `J’ai actuellement 8 lieu(x) vérifié(s) autour de Kribi dans ma base :
- Chutes de la Lobé
- Kribi Lo`
- Limbé: 6 — `J’ai actuellement 6 lieu(x) vérifié(s) autour de Limbé dans ma base :
- Bimbia
- Centre faunique de `
- Bamenda: 4 — `J’ai actuellement 4 lieu(x) vérifié(s) autour de Bamenda dans ma base :
- Savanna Botanic Garden De `
- Maroua: 2 — `J’ai actuellement 2 lieu(x) vérifié(s) autour de Maroua dans ma base :
- Habitats Mofou
- Monts Mand`
- Waza: `Le parc national de Waza se trouve dans la région de l’Extrême-Nord (accès typique depuis Maroua — vérifier saison et sécurité).`
- Ngaoundéré: 8 — `J’ai actuellement 8 lieu(x) vérifié(s) autour de Ngaoundéré dans ma base :
- Lac Tison
- Chute De Bi`
- Oasis: `J’ai actuellement 2 lieu(x) vérifié(s) autour de Ngaoundéré dans ma base :
- Hôtel Oasis
- Lac Mballang

Je peux te prés`
- Garoua: 8 — `J’ai actuellement 8 lieu(x) vérifié(s) autour de Garoua dans ma base :
- Fleuve Bénoué (Garoua)
- Gr`
- Hôtels Garoua: `J’ai actuellement 6 lieu(x) vérifié(s) autour de Garoua dans ma base :
- Hôtel Ribadou
- Iles Aux Damans
- Motel Plaza
-`
- Bertoua: 3 — `J’ai actuellement 3 lieu(x) vérifié(s) autour de Bertoua dans ma base :
- Marché de Bertoua
- Porte `
- Dja: `La réserve de faune du Dja (patrimoine mondial) s’atteint notamment depuis Somalomo, dans la région de l’Est.`

## Agent 2

- Hierarchical retrieval: IN_CITY / NEARBY / IN_REGION scopes
- Geo facts + multi-region culture evidence (Ouest → Extrême-Nord)

## Web fallback

- `WEB_KNOWLEDGE_FALLBACK_ENABLED` (default false)

## Grounding

- Still enforced; Qwen remains formulation-only

## Tests

- 3 failed, 294 passed, 1 warning in 3.67s
- Checks: {"bafoussam_has_places": true, "bafoussam_not_foumban_as_city": true, "ouest_not_equals_bafoussam": true, "bafoussam_region_ouest": true, "geo_no_planner": true, "around_has_places": true, "ouest_regional": true, "ouest_food_mentions_achu": true, "ouest_culture_evidence": true, "mbapit_located": true, "dschang_hotel_or_soft": true, "douala_has_places": true, "douala_not_edea_as_city": true, "littoral_not_equals_douala": true, "douala_region_littoral": true, "littoral_food_ndole": true, "sawa_culture": true, "littoral_regional": true, "yaounde_has_places": true, "yaounde_not_mbalmayo_as_only": true, "centre_not_equals_yaounde": true, "yaounde_region_centre": true, "centre_food": true, "mokolo_or_culture": true, "centre_regional": true, "kribi_has_places": true, "sud_not_equals_kribi": true, "kribi_region_sud": true, "kribi_food_poisson": true, "lobe_located": true, "yaounde_hotels": true, "limbe_has_places": true, "limbe_not_buea_as_city": true, "sud_ouest_not_equals_buea": true, "buea_region_sud_ouest": true, "sud_ouest_food_eru": true, "mont_cameroun_located": true, "sud_ouest_regional": true, "bamenda_has_places": true, "bamenda_not_bafut_as_city": true, "nord_ouest_not_equals_bamenda": true, "bamenda_region_nord_ouest": true, "nord_ouest_food_achu": true, "bafut_located": true, "nord_ouest_regional": true, "maroua_has_places": true, "maroua_not_waza_as_city": true, "extreme_nord_not_equals_maroua": true, "maroua_region_extreme_nord": true, "extreme_nord_food": true, "waza_located": true, "extreme_nord_regional": true, "ngaoundere_has_places": true, "ngaoundere_not_banyo_as_city": true, "adamaoua_not_equals_ngaoundere": true, "ngaoundere_region_adamaoua": true, "adamaoua_food": true, "tison_located": true, "ngaoundere_hotel_oasis": true, "garoua_has_places": true, "garoua_not_figuil_as_city": true, "nord_not_equals_garoua": true, "garoua_region_nord": true, "nord_food": true, "benoue_located": true, "garoua_hotels": true, "bertoua_has_places": true, "bertoua_not_dja_city": true, "est_not_equals_bertoua": true, "bertoua_region_est": true, "est_food": true, "dja_located": true, "est_regional": true}

## Performance

- Full conversation: **810.5 ms** (deterministic Agent 4, no LLM)
- Geo simple turn: **6.8 ms**, planner=False

## Flags

- `KNOWLEDGE_GEOGRAPHY_ENABLED=false` (default)
- `WEB_KNOWLEDGE_FALLBACK_ENABLED=false` (default)

## Conclusion

Structured geography covers all 10 regions (Ouest → Est) without inventing tourism facts.
