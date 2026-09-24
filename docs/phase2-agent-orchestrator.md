# Phase 2.5 — Agent Orchestrator

## 1. Architecture

```
USER QUERY
    │
    ▼
┌─────────────────────┐
│  AgentOrchestrator  │  coordinator only
└─────────┬───────────┘
          │
          ▼
   Agent 1 — Intent & Router
          │ IntentResult
          ├── needs_vision? ──► VisionService (Gemini, existing)
          ├── needs_knowledge / needs_places? ──► Agent 2
          │         │ KnowledgeResult
          ├── needs_web? ──► WebSearchService (existing, evidence only)
          ├── needs_planner AND usable places? ──► Agent 3
          │         │ TourismPlan
          ▼
   Agent 4 — Response Generator
          │ FinalResponse
          ▼
     TEXT / VOICE (existing stream → chunker → TTS)
```

**Principle:** GROUNDING > FLUIDITY. The orchestrator does **not** invent places,
prices, bookings, or knowledge. It does **not** call the LLM for answering
(Agent 4 may do at most one generation; default path is deterministic).

---

## 2. Flux

1. Always run **Agent 1**.
2. Conditionally run Vision / Agent 2 / Web / Agent 3 based on capability flags
   and data sufficiency.
3. Always run **Agent 4** last with structured inputs only.
4. Emit `OrchestrationResult` with timings (`None` = step skipped).

### Conditional routing examples

| Intent | Path |
|--------|------|
| Greeting / CLARIFICATION | 1 → 4 |
| PLACE_SEARCH / PLACE_DETAILS / TOURISM_INFO | 1 → 2 → 4 |
| ITINERARY / BUDGET_TRIP | 1 → 2 → 3 → 4 |
| BOOKING (no live provider) | 1 → 4 (honest availability message) |
| Agent 2 empty + needs_planner | 1 → 2 → 4 (skip 3) |
| Agent 3 NOT_FEASIBLE | 1 → 2 → 3 → 4 (feasibility preserved) |

---

## 3. Conditions d’appel

```python
if intent.intent == "CLARIFICATION":
    skip Agent 2 / 3
elif intent.intent == "BOOKING" and not booking_available:
    skip Agent 2 / 3
elif intent.needs_knowledge or intent.needs_places:
    run Agent 2

if intent.needs_planner and knowledge.places and knowledge.source != "empty":
    run Agent 3
else:
    skip Agent 3  # Agent 4 gets insufficient / clarification path

# Agent 4 always
```

Web search runs **only** when `needs_web=true`, reusing the existing
`WebSearchService`. Hits are attached as **unverified evidence**, never as truth.

---

## 4. Fallback

Feature flags (default **false**):

| Flag | Effect |
|------|--------|
| `AGENT_ORCHESTRATOR_ENABLED=false` | Existing Phase-1 chat/voice pipeline |
| `AGENT_ORCHESTRATOR_ENABLED=true` | Orchestrator serves the answer |
| `AGENT_ORCHESTRATOR_OBSERVE=true` | Metrics only (deterministic Agent 4, no extra production LLM) |

If the orchestrator raises while enabled, `stream_response` logs
`orchestrator_failed_fallback` with `request_id` and continues on the
legacy HF + RAG path. Users never see a raw exception.

---

## 5. Gestion des erreurs

- Vision / web failures are logged and skipped (do not abort the turn).
- Agent 4 deterministic renderer covers insufficient / not-feasible / booking.
- Structured logs: `orchestration_started`, `intent_completed`,
  `knowledge_*`, `planner_*`, `response_*`, `orchestration_completed`.
- Never log passwords, tokens, or API keys.

---

## 6. Voice

```
WebSocket → STT → stream_response
                 ├─ ENABLED=false → legacy LLM stream (unchanged)
                 └─ ENABLED=true  → Orchestrator → word tokens → chunker → TTS
```

- Default Agent 4 path: **`prefer_deterministic=True`** (0 LLM) to protect TTFA.
- Tokens are emitted progressively (word chunks) so early-play MSE keeps working.
- No wait on `audio_done` before playback (unchanged client contract).
- Warm TTFA baseline from Phase 1.9 remains ≈ **1.1 s** when the flag is off.

---

## 7. Performance

Deterministic bench (`scripts/benchmark_orchestrator.py`, fixture catalog):

| Path | Agents | total_ms median |
|------|--------|-----------------|
| Greeting | 1 → 4 | ~0.07 ms |
| Tourism / places | 1 → 2 → 4 | ~0.75 ms |
| Itinerary | 1 → 2 → 3 → 4 | ~0.95 ms |

Agents 1–3 stay rules/data-first (not three LLM calls). Max **one** LLM
generation for the user answer when Agent 4 LLM injection is enabled later.

---

## 8. Tests

- `backend/tests/test_agent_orchestrator.py` — integration cases 1–10 + booking + timings + voice stream shape + HF flag path.
- Full suite: **170 passed** (155 baseline + 15 new).
- Soft bench assertion: deterministic paths < 500 ms median.

---

## 9. Feature flags

```bash
AGENT_ORCHESTRATOR_ENABLED=false   # default — rollback / production safe
AGENT_ORCHESTRATOR_OBSERVE=false   # metrics without replacing the answer
```

Configured in `backend/app/core/config.py`.

---

## 10. Exemples de parcours

**Greeting**

```
"Bonjour"
 → Agent1 CLARIFICATION/low-confidence
 → Agent4 clarification / short reply
 (no Supabase / RAG / planner)
```

**Place search**

```
"Quels sont les lieux touristiques à Yaoundé ?"
 → Agent1 PLACE_SEARCH
 → Agent2 PlaceEvidence[]
 → Agent4 PLACE_LIST (names ⊆ knowledge)
```

**Itinerary**

```
"Fais-moi un programme de 3 jours à Yaoundé."
 → Agent1 ITINERARY
 → Agent2 places
 → Agent3 TourismPlan (selected_places ⊆ Agent2)
 → Agent4 ITINERARY prose
```

**Booking without provider**

```
"Réserve-moi un hôtel à Yaoundé."
 → Agent1 BOOKING
 → Agent4: information OK, live availability / booking not confirmed
 (no invented room / price / confirmation number)
```

---

## Fichiers

| Path | Role |
|------|------|
| `backend/app/services/agents/orchestrator/` | Orchestrator + models |
| `backend/app/core/config.py` | Feature flags |
| `backend/app/services/ai/huggingface.py` | Enabled path + observe + fallback |
| `backend/app/services/agents/response/fallback.py` | Booking / NOT_FEASIBLE honesty |
| `backend/tests/test_agent_orchestrator.py` | Integration tests |
| `backend/scripts/benchmark_orchestrator.py` | Latency bench |
| `docs/phase2-agent-orchestrator-plan.md` | Pre-implementation plan |
| `docs/phase2-agent-orchestrator-latency.json` | Bench output |

**Not modified:** Qwen model id, Whisper STT, Fish TTS, Gemini Vision internals,
Supabase schema, RAG / pgvector strategy, voice chunker algorithm.
