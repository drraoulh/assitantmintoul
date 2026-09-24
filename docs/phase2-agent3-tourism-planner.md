# Phase 2.3 — Agent 3 : Tourism Planner

## 1. Architecture

```
USER QUERY
    ↓
AGENT 1 → IntentResult
    ↓
AGENT 2 → KnowledgeResult (PlaceEvidence only)
    ↓
AGENT 3 → TourismPlan   ← this phase
    ↓
AGENT 4 (not implemented)
```

**Strategy:** rules + data first. No LLM. No invented places/prices/hours/activities.

---

## 2. Fichiers créés / modifiés

### Créés
| Path | Role |
|------|------|
| `backend/app/services/agents/planner/__init__.py` | Public API |
| `…/models.py` | `TourismPlan`, `PlanDay`, `PlanItem` |
| `…/geo_utils.py` | Haversine (geographical distance only) |
| `…/budget_utils.py` | WITHIN / OVER / PARTIAL / UNKNOWN |
| `…/scoring.py` | Explainable interest/location/eco/culture scores |
| `…/agent.py` | Deterministic planner algorithm |
| `…/compare.py` | Old ids vs Agent 3 diagnostic |
| `backend/tests/test_tourism_planner.py` | Mandatory tests |
| `backend/scripts/benchmark_tourism_planner.py` | Latency bench |
| `docs/phase2-agent3-tourism-planner-latency.json` | Bench output |
| `docs/phase2-agent3-tourism-planner.md` | This report |

### Modifiés
| Path | Change |
|------|--------|
| `backend/app/core/config.py` | `TOURISM_PLANNER_OBSERVE` / `ENABLED` (default false) |
| `backend/app/services/ai/huggingface.py` | Observe-only planner metrics |
| `backend/app/services/agents/__init__.py` | Export planner |

**Not modified:** Agent 1/2 logic, HybridRAG, voice pipeline, pgvector, Qwen/Whisper/Fish.

---

## 3. Modèles créés

```python
TourismPlan:
  plan_type, duration_days, currency="XAF"
  total_estimated_cost_xaf | None
  known_cost_xaf | None
  budget_status: WITHIN_BUDGET | OVER_BUDGET | UNKNOWN | PARTIAL
  feasibility: FEASIBLE | PARTIAL | NOT_FEASIBLE | INSUFFICIENT_DATA
  days: list[PlanDay]
  selected_places: list[str]          # ⊆ Agent2 place_ids
  interests_covered / interests_not_covered
  constraints_applied, warnings, missing_information
  needs_web, confidence, *latency fields

PlanDay: day, title, city, places, estimated_day_cost_xaf?, duration?, notes
PlanItem: place_id, place_name, order, costs?, distance_from_previous_km?,
          category, eco_tags, reason, score_breakdown
```

---

## 4. Données utilisées

From `PlaceEvidence` (Agent 2 / Supabase-aligned fields):

- `place_id`, `name`, `city`, `region`
- `category`, `eco_tags`, `cultural_info`, `eco_info`, `activities`
- `estimated_cost_xaf`, `recommended_duration_hours`
- `latitude`, `longitude`, `is_published`, `evidence_score`

No transport tariffs invented. No hotel/restaurant invention.

---

## 5. Algorithme de sélection

1. Dedupe + drop unpublished / empty ids  
2. Resolve `duration_days` (missing → flag + pack as 1 day, no silent multi-day invent)  
3. Score each place (evidence, interest, location, eco, culture, budget, distance penalty)  
4. Select with **interest coverage** (at least one place per interest when available)  
5. Budget trim: keep protected interest places; drop extras that don’t fit  
6. Group by city/region → assign to days  
7. Within day: nearest-neighbor order if coordinates exist  
8. Assess budget / feasibility / confidence  

---

## 6. Stratégie géographique

- Haversine only → **geographical** km, never claimed as driving distance  
- Missing coords → `distance_from_previous_km = null`  
- City grouping preferred; region as fallback  
- Short trips prefer intent city cluster  

---

## 7. Stratégie budget

| Case | Result |
|------|--------|
| All costs known & ≤ budget | `WITHIN_BUDGET`, `total_estimated_cost_xaf = sum` |
| All known & > budget | `OVER_BUDGET`, `NOT_FEASIBLE` |
| Any null cost | `PARTIAL`, `total_estimated_cost_xaf = null`, `known_cost_xaf = sum(known)` |
| No budget given | `UNKNOWN` (or PARTIAL if costs missing) |

**Never** multiply by `people` / `children`. Warnings explain undocumented pricing modes.

---

## 8. Gestion des données manquantes

`missing_information` may include: `duration_days`, `estimated_cost_xaf`, Agent 2 gaps, etc.  
`warnings` for: missing place costs, transport unavailable, people/children pricing, duration default packing.

---

## 9. Anti-hallucination

- `selected_places ⊆ KnowledgeResult.places` (published only)  
- No synthetic place ids  
- Null costs stay null  
- Null durations stay null  
- Empty Agent 2 → `feasibility = INSUFFICIENT_DATA`, no fake days of attractions  

---

## 10. Scoring (inspectable)

Per place `score_breakdown`:

| Component | Role |
|-----------|------|
| `evidence` | Agent 2 evidence_score |
| `interest_match` | nature/culture/food coverage |
| `location_score` | city/region match |
| `eco_score` / `culture_score` | thematic evidence |
| `budget_score` | known cost vs budget |
| `distance_penalty` | reserved / geo soft penalty |

Stored on each `PlanItem.reason` / `score_breakdown`.

---

## 11. Performance

From `docs/phase2-agent3-tourism-planner-latency.json`:

| Metric | Value |
|--------|-------|
| Median | **0.26 ms** |
| Mean | **0.22 ms** |
| p95 | **0.32 ms** |
| Max | **0.39 ms** |
| Target | **< 100 ms** warm |

Voice unchanged while `TOURISM_PLANNER_OBSERVE=false`.

---

## 12. Tests

```text
pytest -q
136 passed
```

= **119** prior + **17** Agent 3 tests (`test_tourism_planner.py`) covering the 15 mandatory scenarios (+ latency + compare).

---

## 13. Comparaison old / new

`compare_plan(query, intent, knowledge)` returns legacy raw place ids vs Agent 3 selected/day layout, plus `subset_ok`.

Observe flag: `TOURISM_PLANNER_OBSERVE=true` logs `tourism_planner` metrics without changing answers.

---

## 14. Limites

1. No road network — distances are great-circle only.  
2. No transport/hotel cost model without evidence.  
3. Without `duration_days`, packs into 1 day + warning (does not invent a 3-day story).  
4. Interest detection is keyword/category based on Agent 2 fields — limited by evidence quality.  
5. Catalog offline path may yield `INSUFFICIENT_DATA` when Agent 2 returns no places for a query.  
6. LLM not used — nuance/phrasing deferred to Agent 4.

---

## 15. Recommandations pour Agent 4

Agent 4 should:

1. Consume `TourismPlan` only — never add places.  
2. Surface `warnings` / `missing_information` honestly (“prix non renseigné”).  
3. Phrase distances as geographical if present.  
4. If `feasibility = INSUFFICIENT_DATA`, ask clarifying questions instead of inventing a trip.  
5. If `budget_status = PARTIAL`, say known subtotal + unknowns.  
6. Keep voice TTFA: generate short spoken summaries from plan structure.

### Flags

```bash
TOURISM_PLANNER_OBSERVE=false
TOURISM_PLANNER_ENABLED=false
```

### API

```python
from app.services.agents.planner import build_tourism_plan

plan = build_tourism_plan(user_query, intent_result, knowledge_result)
# plan.days[*].places[*].place_id ⊆ knowledge_result.places
```

---

## Out of scope (confirmed)

Agent 4, voice changes, replacing Agents 1/2, pgvector, booking, LLM itinerary generation.
