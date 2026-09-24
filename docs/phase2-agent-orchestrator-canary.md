# Phase 2.5B — Orchestrator canary (real path)

## Environment

- Base URL legacy: `http://127.0.0.1:8010` (`AGENT_ORCHESTRATOR_ENABLED=false`)
- Base URL orchestrator: `http://127.0.0.1:8011` (`AGENT_ORCHESTRATOR_ENABLED=true`)
- Fallback probe: `http://127.0.0.1:8012` (`AGENT_ORCHESTRATOR_FORCE_FAIL=true`)
- Orchestrator enabled (canary): **true**
- Rollback: set `AGENT_ORCHESTRATOR_ENABLED=false` (no code change)
- Model / stack unchanged: Qwen / Whisper / Fish / Gemini / RAG / chunker / WS

## Chat (real `POST /api/chat` + WS observability companion)

| Scenario | Agents called | Result | Latency |
|----------|---------------|--------|---------|
| greeting | `intent,response` | PASS | 1563.7 ms |
| places | `intent,knowledge,response` | PASS | 1502.8 ms |
| place_details | `intent,knowledge,response` | PASS | 1531.1 ms |
| itinerary | `intent,knowledge,planner,response` | PASS | 1522.3 ms |
| budget | `intent,knowledge,planner,response` | PASS | 1530.5 ms |
| clarification | `intent,response` | PASS | 1517.1 ms |
| no_invention | `intent,response` | PASS | 1510.0 ms |
| insufficient | `response,intent,knowledge` | PASS | 1505.4 ms |

### Clarification / insufficient / no-invention notes

- Clarification agents: see table row `clarification`
- Insufficient: planner_skipped=True honest=True
- No-invention preview: `Pouvez-vous préciser un peu ce que vous recherchez ?`

## Web

- needs_web query: PASS agents=`['response', 'intent', 'web']`
- no-web greeting: PASS agents=`['response', 'intent']`

## Voice (real `WS /api/voice/session`, warm text turns)

Baseline historique warm TTFA ≈ **1100 ms** (Phase 1.9, legacy LLM path).

**Legacy arm note:** 9/10 legacy voice turns failed with Hugging Face Inference
credit depletion (402) / busy / timeout. Only 1 legacy places sample succeeded
(TTFA 3349 ms). Comparison vs live legacy is therefore incomplete; orchestrator
arm is complete (n=5 warm per scenario). vs historical baseline ≈1100 ms,
orchestrator warm TTFA medians are **~499 ms (greeting)** and **~507 ms (places)**
— no regression observed on the canary path.

Orchestrator path uses deterministic Agent 4 (0 LLM). First text chunk is ~2–7 ms;
TTFA is dominated by Fish TTS TTFB (~480–500 ms).


### Greeting — Bonjour

| Metric | Legacy | Orchestrator |
|--------|--------|--------------|
| STT | 0 (text turn) | 0 (text turn) |
| Orchestrator | — | med 0.3 / avg 0.3 (min 0.3, max 0.3, n=5) |
| First text chunk | — | med 2.4 / avg 2.4 (min 2.2, max 2.5, n=5) |
| TTS gap (text→audio) | — | med 496.3 / avg 518.4 (min 480.3, max 617.6, n=5) |
| TTFA | — | med 498.8 / avg 520.8 (min 482.8, max 620.0, n=5) |
| Total | — | med 2344.7 / avg 2323.2 (min 2239.5, max 2398.0, n=5) |

### Places — Yaoundé

| Metric | Legacy | Orchestrator |
|--------|--------|--------------|
| STT | 0 (text turn) | 0 (text turn) |
| Orchestrator | — | med 3.7 / avg 3.7 (min 3.6, max 3.9, n=5) |
| First text chunk | med 2789.4 / avg 2789.4 (min 2789.4, max 2789.4, n=1) | med 7.1 / avg 7.0 (min 6.8, max 7.3, n=5) |
| TTS gap (text→audio) | med 559.9 / avg 559.9 (min 559.9, max 559.9, n=1) | med 499.9 / avg 495.6 (min 457.6, max 526.3, n=5) |
| TTFA | med 3349.3 / avg 3349.3 (min 3349.3, max 3349.3, n=1) | med 507.0 / avg 502.6 (min 464.4, max 533.4, n=5) |
| Total | med 15571.2 / avg 15571.2 (min 15571.2, max 15571.2, n=1) | med 11735.9 / avg 12111.4 (min 10949.4, max 13529.5, n=5) |

- Streaming before `audio_done` (orch places): 5/5

## LLM

- Maximum calls per request (orchestrator canary): **0**
- Agents 1–3: deterministic (no LLM)
- Agent 4: deterministic renderer (no LLM on canary)
- Legacy path LLM calls: 1
- Note: Canary validates production default orchestrator wiring. LLM injection remains available later; default protects TTFA.

## Fallback

- Result: **PASS**
- Raw exception leaked: False
- Preview: `Bienvenue au Cameroun, une véritable « Afrique en miniature » où côtoient plages, forêts, hauts plateaux et savanes.

*   **Besoin de directions ?** Donnez-moi votre ville de départ et destination pour un itinéraire préc`

## Tests

- pytest: **170 passed, 1 warning in 0.78s**

## Conclusion

**PASS WITH ISSUES**

Legacy voice arm incomplete: Hugging Face Inference credits/provider errors (402/busy/timeout). Orchestrator voice arm measured successfully.

## Artifacts

- `docs/phase2-agent-orchestrator-canary.json`
- `docs/phase2-agent-orchestrator-canary.md`
