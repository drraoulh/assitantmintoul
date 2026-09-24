# Phase 2.2 — Agent 2 : Knowledge & Retrieval

## 1. Architecture créée

```
IntentResult + user_query
        │
        ▼
┌───────────────────────────────────────┐
│ AGENT 2 — Knowledge & Retrieval       │
│  1. PlaceRetriever (structured)       │
│  2. KnowledgeRetriever (TF-IDF docs)  │
│  3. SourceValidator / missing info    │
└───────────────────┬───────────────────┘
                    │
                    ▼
             KnowledgeResult
        (evidences only — no prose)
```

**Order:** structured Supabase/catalog places → `knowledge_chunks` / local TF-IDF → web flag only (`web_needed`), never invent.

**No LLM** in Agent 2. **pgvector stays off** (`RAG_VECTOR_ENABLED=false`).

Production chat/voice path **unchanged**. Observe-only via `KNOWLEDGE_AGENT_OBSERVE=false` (default).

---

## 2. Fichiers créés / modifiés

### Créés
| Path | Role |
|------|------|
| `backend/app/services/agents/knowledge/__init__.py` | Public API |
| `…/models.py` | `KnowledgeResult`, `PlaceEvidence`, … |
| `…/topk.py` | Configurable Top-K by intent |
| `…/place_store.py` | `PlaceRecord` / `PlaceIndex` |
| `…/scoring.py` | Explainable scores + hard filters |
| `…/place_retriever.py` | Structured place search |
| `…/knowledge_retriever.py` | Doc retrieval (async TF-IDF) |
| `…/source_validator.py` | Anti-hallucination + missing + confidence |
| `…/supabase_places.py` | Async Supabase loader (eco_tags, activities) |
| `…/agent.py` | `KnowledgeAgent` orchestrator |
| `…/compare.py` | Old RAG vs Agent 2 diagnostic |
| `backend/tests/test_knowledge_agent.py` | Mandatory tests |
| `backend/scripts/benchmark_knowledge_agent.py` | Latency bench |
| `docs/phase2-agent2-knowledge-latency.json` | Bench output |
| `docs/phase2-agent2-knowledge.md` | This report |

### Modifiés
| Path | Change |
|------|--------|
| `backend/app/core/config.py` | `KNOWLEDGE_AGENT_OBSERVE` / `ENABLED` (default false) |
| `backend/app/services/ai/huggingface.py` | Observe-only Agent 2 timing/meta |
| `backend/app/services/agents/__init__.py` | Export Agent 2 |

**Not modified:** HybridRAG control plane, `route_query`, voice WS, Whisper, Fish, Qwen, frontend.

---

## 3. Tables Supabase utilisées

Verified against live schema (no SQLAlchemy ORM for tourism):

| Table | Usage |
|-------|--------|
| `places` | Core structured retrieval (`is_published`, names FR/EN, costs, duration, cultural/eco info) |
| `cities` / `regions` | City/region filters via FK joins |
| `categories` | Category hard filters |
| `cultural_zones` | Culture matching |
| `sources` | `SourceEvidence` (URLs only if present) |
| `place_eco_tags` / `eco_tags` | Nature scoring (joined when DB load used) |
| `place_activities` | Activities list (may be empty) |
| `knowledge_chunks` | Via existing LocalRAG / HybridRAG chunks (not re-enabled vector) |
| `place_images` | Not required for Agent 2 evidence payload (available elsewhere) |
| `itineraries*` | **Not used** (Agent 3) |

Offline / tests: `PlaceIndex` from fixtures or `SiteCatalog` JSON under `data/tourist_sites/`.

---

## 4. Stratégie structured-first

1. Resolve `city` / `region` / name from `IntentResult` (Agent 1).
2. Filter `is_published = true` only.
3. Apply intent hard filters (NATURE ≠ random monuments, FOOD ≠ hotels, …).
4. Score with transparent weights: name > city > region > category/eco/culture > text overlap.
5. Cap with intent Top-K.

---

## 5. Stratégie document retrieval

- Reuse `LocalRAGService` TF-IDF (async `retrieve_chunks`).
- Light query normalization (food/culture/city).
- Truncate chunk content (`KNOWLEDGE_CONTENT_MAX_CHARS = 600`).
- No vector/HF embedding activation in this phase.

---

## 6. Stratégie web fallback

`web_needed = true` only when:

- Intent is `BOOKING` / `WEB_SEARCH`, or
- `HOTEL` with missing places/availability, or
- Agent 1 already set `needs_web` / `needs_booking`, or
- Confidence very low with empty local evidence.

Web is **not** fetched by Agent 2 — only flagged for later stages.

---

## 7. Modèle `KnowledgeResult`

```python
class KnowledgeResult(BaseModel):
    query: str
    intent: str
    places: list[PlaceEvidence]
    knowledge: list[KnowledgeEvidence]
    sources: list[SourceEvidence]
    missing_information: list[str]
    web_needed: bool
    confidence: float
    place_retrieval_ms / knowledge_retrieval_ms / source_resolution_ms / total_agent2_ms
```

`PlaceEvidence.estimated_cost_xaf` stays `null` when unknown. `activities = []` when undocumented.

---

## 8. Anti-hallucination rules

1. Every `place_id` must exist in the published index.
2. Unpublished places never returned.
3. No invented prices, hours, activities, or URLs.
4. Unknown place names → empty / only real matches (Test: Parc XYZ).
5. `missing_information` lists gaps (`opening_hours`, `current_price`, `estimated_cost_xaf`, …).
6. Agent 2 never writes itinerary days or final user prose.

---

## 9. Scoring

Additive, explainable (`match_reasons`):

| Signal | Weight (approx.) |
|--------|------------------|
| Exact / bilingual name | 0.50–0.55 |
| City match | 0.18–0.25 |
| Region match | 0.15 |
| Nature/culture/food category | 0.08–0.22 |
| Known cost (budget trips) | 0.08 |
| Text overlap | ≤ 0.12 |

Hard filters reject intent-irrelevant categories before ranking.

---

## 10. Top-K (configurable in `topk.py`)

| Intent | Places | Knowledge |
|--------|-------:|----------:|
| PLACE_DETAILS | 3 | 3 |
| PLACE_SEARCH | 8 | 3 |
| NATURE / CULTURE | 8 | 3–5 |
| ITINERARY / BUDGET_TRIP | 12 | 3–4 |
| FOOD | 5 | 6 |
| SIMPLE_QA | 0 | 4 |

---

## 11. Latence

From `docs/phase2-agent2-knowledge-latency.json` (catalog index, warm):

| Metric | Value |
|--------|-------|
| Median total | **2.55 ms** |
| Mean total | **2.65 ms** |
| p95 total | **3.93 ms** |
| Mean place retrieval | **2.12 ms** |
| Mean knowledge retrieval | **0.38 ms** |
| Catalog index size (bench) | 70 places |
| Target | **< 100 ms** for simple local queries |

Voice path unaffected while `KNOWLEDGE_AGENT_OBSERVE=false`.

---

## 12. Tests

```text
pytest -q
119 passed
```

= previous **106** + **13** Agent 2 tests (`test_knowledge_agent.py`).

Mandatory coverage: Yaoundé search, Mont Cameroun, nature eco evidence, culture Sawa, food knowledge, unknown place, budget costs, unpublished filter, null cost, low-confidence empty, latency, compare diagnostic, observability.

---

## 13. Comparaison old / new

`compare_retrieval(query)` returns:

- `old_retrieval`: legacy TF-IDF chunk ids/titles
- `agent2`: place ids/names, chunk ids, latency, missing, confidence

Enable dual observe in staging with `KNOWLEDGE_AGENT_OBSERVE=true` (metrics only).

---

## 14. Problèmes rencontrés

1. **No ORM** for tourism tables — raw SQL + `PlaceRecord` abstraction.
2. **`place_activities` empty** in current DB — activities often `[]` (honest).
3. **RAG API is async** — Agent 2 `retrieve` is async; `retrieve_sync` for scripts/tests.
4. **Sawa** barely present as structured places in JSON; culture evidence relies on cultural_info fixtures + knowledge docs.
5. Catalog `TouristSiteRecord.price` is a string — cost parsed only when numeric XAF present; otherwise `null`.

---

## 15. Recommandation pour l’Agent 3

Agent 3 (Tourism Planner) should:

1. Consume `KnowledgeResult.places` as **verified candidates only**.
2. Select/order by duration, budget, interests — never add places absent from Agent 2.
3. Treat `estimated_cost_xaf is None` as unknown, not zero.
4. Use `missing_information` to ask clarifying questions or defer to Agent 4 honesty.
5. Keep itinerary generation **out of** Agent 2 (already enforced).

### Progressive integration

| Step | Action |
|------|--------|
| Now | Isolated Agent 2 + tests + observe flag off |
| Next | Staging observe + compare logs |
| Later | Feed `KnowledgeResult` into Agent 3; still don’t replace HybridRAG until dual-run OK |

### Flags

```bash
KNOWLEDGE_AGENT_OBSERVE=false
KNOWLEDGE_AGENT_ENABLED=false   # reserved
```

### API

```python
from app.services.agents.intent import classify_intent
from app.services.agents.knowledge import KnowledgeAgent, retrieve_knowledge

intent = classify_intent("Que visiter à Yaoundé ?")
result = await retrieve_knowledge("Que visiter à Yaoundé ?", intent)
# result.places[*].place_id are real index ids only
```

---

## Out of scope (confirmed)

Agent 3 / 4, planner, booking, voice architecture changes, enabling pgvector.
