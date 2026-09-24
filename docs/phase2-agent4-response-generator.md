# Phase 2.4 — Agent 4 : Response Generator

## 1. Architecture

```
USER
 ↓
Agent 1 → IntentResult
 ↓
Agent 2 → KnowledgeResult
 ↓
Agent 3 → TourismPlan
 ↓
Agent 4 → FinalResponse   ← this phase
 ↓
TEXT / VOICE (TTS)
```

Agent 4 is a **presentation layer** only. The LLM (when enabled later) is an interpreter/writer — not a database or planner.

Default path today: **deterministic renderer** (no LLM call) to protect TTFA and enable offline tests. Optional `llm_complete` injection supports one LLM generation with strict grounding prompt + deterministic fallback on failure.

---

## 2. Fichiers créés / modifiés

### Créés
| Path | Role |
|------|------|
| `backend/app/services/agents/response/__init__.py` | Public API |
| `…/models.py` | `FinalResponse`, `SourceReference` |
| `…/prompts.py` | Strict FR/EN system prompts + voice/text rules |
| `…/context.py` | Compact structured context serialization |
| `…/fallback.py` | Deterministic itinerary / place / knowledge renderer |
| `…/validate.py` | Soft voice/road-distance/place checks |
| `…/agent.py` | `ResponseGenerator` |
| `…/compare.py` | OLD vs Agent 4 diagnostic |
| `backend/tests/test_response_generator.py` | Mandatory tests |
| `backend/scripts/benchmark_response_generator.py` | Latency bench (deterministic) |
| `docs/phase2-agent4-response-generator-latency.json` | Bench output |
| `docs/phase2-agent4-response-generator.md` | This report |

### Modifiés
| Path | Change |
|------|--------|
| `backend/app/core/config.py` | `RESPONSE_AGENT_OBSERVE` / `ENABLED` (default false) |
| `backend/app/services/ai/huggingface.py` | Observe-only Agent 4 (deterministic, no extra LLM) |
| `backend/app/services/agents/__init__.py` | Export Agent 4 |

**Not modified:** Agents 1–3 logic, Qwen model id, Fish/Whisper, RAG, pgvector, voice chunker.

---

## 3. `FinalResponse`

```python
class FinalResponse(BaseModel):
    text: str
    language: str                 # fr | en
    response_type: str            # SIMPLE_ANSWER, ITINERARY, …
    response_mode: str            # text | voice
    sources: list[SourceReference]
    warnings: list[str]
    confidence: float
    fallback_used: bool
    prompt_build_ms / llm_ttft_ms / llm_generation_ms / total_agent4_ms
```

---

## 4. Prompt utilisé

`agent4_system_prompt(language, response_mode)`:

- Explicit **presentation-only** contract (FR + EN variants)
- Forbidden inventions listed (places, prices, hours, road distances, activities, hotels, transport, sources, bookings)
- Voice rules: short, no markdown/URLs/emoji
- Text rules: concise, optional light headings/bullets

User message = compact JSON context + original question.

---

## 5. Anti-hallucination strategy

1. Structured context only from Intent / Knowledge / Plan  
2. Strict system prompt (GROUNDING > FLUIDITY)  
3. Deterministic renderer uses only plan/evidence fields  
4. Sources copied from KnowledgeResult — never invented  
5. Soft validators for tests (`contains_invented_place`, `claims_road_distance`)  
6. LLM path (optional): one call max; on failure → deterministic fallback  

---

## 6. Voice / text strategy

| Mode | Behavior |
|------|----------|
| `text` | Headings/bullets allowed when data exists |
| `voice` | Flat short sentences; markdown stripped; no URLs |

Language from `IntentResult.language`, else locale, else **fr**.

---

## 7. Deterministic fallback

`render_deterministic(...)` covers:

- Clarification questions  
- Insufficient data  
- Day-by-day itinerary from `TourismPlan`  
- Place details / place lists  
- Knowledge chunks (e.g. food / capital facts)  
- Budget WITHIN / PARTIAL / OVER wording  
- Missing-info sentences  
- Distances as **à vol d’oiseau / as the crow flies** only  

---

## 8. Streaming

Production voice/text streaming remains the existing HuggingFace path.  
Agent 4 observe does **not** inject a second LLM stream.  
When `RESPONSE_AGENT_ENABLED` is later turned on, integration should replace system prompt/context with Agent 4’s compact context while reusing the same streaming client (one generation).

---

## 9. Sources

`FinalResponse.sources` = KnowledgeResult sources only (`source_id`, `name`, `url` as provided). No fabricated MINTOUL/URLs.

---

## 10. Missing information

`missing_information` / plan warnings are phrased naturally (“non renseigné…”, “total cannot be confirmed”) without inventing values.

---

## 11. Tests

```text
pytest -q
155 passed
```

= **136** prior + **19** Agent 4 tests (mandatory scenarios including voice, FR/EN, budget, distance, LLM-failure fallback).

---

## 12. Performances

Deterministic Agent 4 path (from latency JSON after bench):

| Metric | Typical |
|--------|---------|
| Median total Agent 4 | **≪ 5 ms** (renderer only) |
| Prompt build | sub-ms |
| Extra LLM on observe | **none** |

Voice hot path unchanged while `RESPONSE_AGENT_OBSERVE=false` (default). Observe uses deterministic rendering only — no DB before first production token beyond existing pipeline.

Warm TTFA target remains ≈ **1.1 s** (Phase 1) — no intentional regression.

---

## 13. Comparaison OLD vs AGENT 4

`compare_response(query, intent, knowledge, plan, legacy_text=...)` returns Agent 4 observability + invent-suspect flag.

Enable staging: `RESPONSE_AGENT_OBSERVE=true`.

---

## 14. Régressions

None expected: Agent 4 is isolated; production answer path unchanged.  
Observe adds work only when flag is true (still no second LLM).

---

## 15. Recommandation d’intégration finale

1. Keep observe on in staging; compare Agent 4 text vs current HF grounded replies.  
2. When enabling: feed Agent 4 compact context into existing `stream_response` as system prompt (replace/augment grounding), **one** LLM generation.  
3. Keep deterministic renderer as always-on fallback.  
4. Do not enable pgvector / change Qwen / Fish / Whisper in that step.  
5. Gate with `RESPONSE_AGENT_ENABLED` after dual-run agreement.

### Flags

```bash
RESPONSE_AGENT_OBSERVE=false
RESPONSE_AGENT_ENABLED=false
```

### API

```python
from app.services.agents.response import generate_response

final = await generate_response(
    user_query, intent, knowledge, tourism_plan,
    response_mode="voice",  # or "text"
    prefer_deterministic=True,  # default — safe
)
print(final.text)
```

---

## Out of scope (confirmed)

Changing Qwen/Fish/Whisper, Agents 1–3, RAG rewrite, pgvector, booking, second LLM critique loop.
