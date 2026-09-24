# Phase 2.1 — Agent 1 : Intent & Router

## 1. Architecture créée

```
USER message
    │
    ▼
┌─────────────────────────────────────┐
│ AGENT 1 — Intent & Router           │
│  extract_slots (never invent)       │
│  classify_with_rules (fast path)    │
│  apply_matrix (capabilities)        │
│  confidence gate → CLARIFICATION    │
└─────────────────┬───────────────────┘
                  │ IntentResult (structured)
                  ▼
     (downstream agents — NOT in this phase)
```

**Strategy chosen: Option B — hybrid rules-first.**

| Mode | Path | Why |
|------|------|-----|
| `voice` | Rules only | Protects TTFA (~1.1 s warm); no extra LLM RTT |
| `text` | Rules first; optional LLM flag (off by default) | Low cost; LLM hook reserved for Phase 2.x |

Agent 1 **never** drafts the final answer.

The legacy `route_query()` (simple vs grounded) remains the production router. Agent 1 is isolated + observe-only behind `INTENT_ROUTER_OBSERVE=false` by default.

---

## 2. Fichiers créés / modifiés

### Créés
| Path | Role |
|------|------|
| `backend/app/services/agents/__init__.py` | Package export |
| `backend/app/services/agents/intent/__init__.py` | Agent 1 public API |
| `backend/app/services/agents/intent/models.py` | `Intent`, `IntentResult` |
| `backend/app/services/agents/intent/matrix.py` | Capability routing matrix |
| `backend/app/services/agents/intent/extractors.py` | Slot extraction (no invention) |
| `backend/app/services/agents/intent/rules.py` | Rule-based classifier |
| `backend/app/services/agents/intent/router.py` | Hybrid `IntentRouter` |
| `backend/app/services/agents/intent/bridge.py` | Map → legacy `QueryRoute` + dual observe |
| `backend/tests/test_intent_router.py` | Mandatory + latency tests |
| `backend/scripts/benchmark_intent_router.py` | Latency bench |
| `docs/phase2-agent1-router-latency.json` | Bench output |
| `docs/phase2-agent1-router.md` | This report |

### Modifiés (minimal, non-breaking)
| Path | Change |
|------|--------|
| `backend/app/core/config.py` | `INTENT_ROUTER_OBSERVE` / `INTENT_ROUTER_ENABLED` (default `false`) |
| `backend/app/services/ai/huggingface.py` | Observe-only dual classify when flag on; **does not change** `route_query` decision |

**Not modified:** WebSocket voice stream, Whisper, Fish, conversation store, Supabase pools, RAG, Qwen model, frontend voice.

---

## 3. Format `IntentResult`

```python
class IntentResult(BaseModel):
    intent: IntentName
    location: str | None = None
    region: str | None = None
    city: str | None = None
    duration_days: int | None = None
    budget_xaf: int | None = None
    people: int | None = None
    children: int | None = None
    interests: list[str] = []
    travel_style: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    language: str | None = None
    needs_knowledge: bool = False
    needs_places: bool = False
    needs_planner: bool = False
    needs_web: bool = False
    needs_booking: bool = False
    needs_vision: bool = False
    confidence: float  # 0..1
    reason: str = ""
    request_id: str | None = None
    router_latency_ms: float | None = None
    source: Literal["rules", "hybrid", "llm", "fallback"] = "rules"
```

Observability payload (no raw user text): `request_id`, `intent`, `confidence`, `router_latency_ms`, capability flags, `source`.

---

## 4. Taxonomie des intents

| Intent | Rôle |
|--------|------|
| `SIMPLE_QA` | Faits généraux (capitale, monnaie, régions…) |
| `TOURISM_INFO` | Tourisme général Cameroun |
| `PLACE_SEARCH` | Liste / suggestions de lieux |
| `PLACE_DETAILS` | Un lieu nommé (Mont Cameroun, musée…) |
| `ITINERARY` | Circuit / N jours |
| `BUDGET_TRIP` | Voyage avec budget explicite |
| `NATURE` | Nature / parcs / écotourisme |
| `CULTURE` | Patrimoine / cultures (ex. Sawa) |
| `FOOD` | Gastronomie |
| `HOTEL` | Hébergement |
| `BOOKING` | Intention de réservation (`needs_booking=true` only) |
| `VISION` | Analyse d’image |
| `WEB_SEARCH` | Info fraîche / absente KB |
| `CLARIFICATION` | Confiance < 0.60 — pas de chaîne complexe |

---

## 5. Routing matrix

| Intent | KB | Places | Planner | Web | Booking | Vision |
|--------|:--:|:------:|:-------:|:---:|:-------:|:------:|
| SIMPLE_QA | ✓ | | | | | |
| TOURISM_INFO | ✓ | | | | | |
| PLACE_SEARCH | ✓ | ✓ | | | | |
| PLACE_DETAILS | ✓ | ✓ | | | | |
| ITINERARY | ✓ | ✓ | ✓ | | | |
| BUDGET_TRIP | ✓ | ✓ | ✓ | | | |
| NATURE | ✓ | ✓ | opt* | | | |
| CULTURE | ✓ | ✓ | opt* | | | |
| FOOD | ✓ | opt† | | | | |
| HOTEL | ✓ | ✓ | | opt | | |
| BOOKING | | ✓ | | ✓ | ✓ | |
| VISION | | | | | | ✓ |
| WEB_SEARCH | | | | ✓ | | |
| CLARIFICATION | ✓ | | | | | |

\* Planner if `duration_days` or `budget_xaf` present.  
† Places if city/location present.

Matrix lives in `matrix.py` and is editable without touching the classifier.

---

## 6. Exemples de classification

| Input | Intent | Key slots / flags |
|-------|--------|-------------------|
| Quelle est la capitale du Cameroun ? | `SIMPLE_QA` | `needs_knowledge` |
| Que visiter à Yaoundé ? | `PLACE_SEARCH` | `city=Yaoundé`, `needs_places` |
| Je viens à Yaoundé pendant 3 jours. | `ITINERARY` | `duration_days=3`, `needs_planner` |
| Nous sommes 4 avec 150000 FCFA pour 3 jours à Yaoundé. | `BUDGET_TRIP` | people/budget/days/city |
| Quels plats camerounais dois-je goûter ? | `FOOD` | |
| Je veux découvrir la culture Sawa. | `CULTURE` | `interests∋culture` |
| Propose-moi une activité nature au Cameroun. | `NATURE` | `needs_places`, `city=null` |
| Parle-moi du Mont Cameroun. | `PLACE_DETAILS` | |
| Je veux réserver un hôtel à Yaoundé. | `BOOKING` | `needs_booking` |
| Je veux quelque chose de bien au Cameroun. | `CLARIFICATION` | `confidence<0.60`, no invented city |

---

## 7. Latence moyenne du Router

From `docs/phase2-agent1-router-latency.json` (voice mode, rules-only, 50 samples):

| Metric | Value |
|--------|-------|
| Strategy | hybrid rules-first / voice rules-only |
| Mean | **0.058 ms** |
| Median | **0.058 ms** |
| p95 | **0.078 ms** |
| Max | **0.115 ms** |
| Soft voice budget | 50 ms |

Negligible vs TTFA warm ≈ 1.1 s. No measurable voice regression when observe flag is off (default).

---

## 8. Résultats des tests

```text
pytest -q
106 passed
```

Including 17 Agent 1 tests (`tests/test_intent_router.py`) covering the 10 mandatory scenarios + matrix / bridge / voice latency.

---

## 9. Risques éventuels

1. **Rule coverage gaps** — uncommon phrasings / English-only variants may fall to `CLARIFICATION` or weak `TOURISM_INFO`. Mitigate later with optional LLM classifier (flag already reserved).
2. **City list incomplete** — unknown towns stay `city=null` (correct: no invention). Extend `_CITIES` as needed.
3. **BUDGET vs ITINERARY boundary** — budget+duration → `BUDGET_TRIP`; duration alone → `ITINERARY`. Acceptable overlap documented in tests.
4. **Observe flag misuse** — if `INTENT_ROUTER_ENABLED` is flipped on without wiring a safe consumer, do nothing yet (flag present but unused for control plane).
5. **False BOOKING** — “réserver” in non-booking contexts. Keywords are strong; monitor false positives.

---

## 10. Proposition d’intégration progressive

| Step | Action | Voice impact |
|------|--------|--------------|
| **Now (2.1)** | Agent 1 isolated + tests + bench; `INTENT_ROUTER_OBSERVE=false` | None |
| **2.1b** | Enable observe in staging; compare Agent 1 vs `route_query` via logs | +≪1 ms if observe on |
| **2.2** | Use `needs_*` flags to skip unused tools (planner/web) while keeping legacy skip_kb | Neutral / faster |
| **2.3+** | Agents 2–4 consume `IntentResult`; Agent 1 still does not answer | — |
| **Later** | Optional LLM fallback for `confidence < 0.60` on **text** only | Voice stays rules-only |

Do **not** replace `route_query` until dual-run agreement metrics are validated.

### Feature flags

```bash
INTENT_ROUTER_OBSERVE=false   # dual classify, metrics only
INTENT_ROUTER_ENABLED=false   # reserved — no control-plane switch yet
```

### API entry point

```python
from app.services.agents.intent import classify_intent, IntentResult

result: IntentResult = classify_intent(
    "Je viens à Yaoundé pendant 3 jours.",
    mode="voice",  # rules only
)
```

---

## Out of scope (confirmed)

Agents 2 / 3 / 4, Tourism Planner implementation, booking execution, vision pipeline changes, RAG/Qwen/Fish/Whisper/frontend voice changes.
