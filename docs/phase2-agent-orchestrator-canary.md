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

**HF token:** rotated locally after previous key returned HTTP 402. Secrets stay in
`.env` only (not committed).

**Re-measure (post-rotation):**
- Greeting warm n=5 both arms: legacy TTFA med **2090.7 ms**, orchestrator med **550.9 ms**
  (no regression; orch faster — deterministic Agent 4, 0 LLM).
- Places: orchestrator n=5 med **493.3 ms**; legacy only 1 valid sample (**1415 ms**) —
  new key hit 402 again on heavier grounded LLM turns after greeting burn.
- Historical baseline ≈1100 ms; orchestrator remains below baseline on both scenarios.

### Greeting — Bonjour

| Metric | Legacy | Orchestrator |
|--------|--------|--------------|
| STT | 0 (text turn) | 0 (text turn) |
| Orchestrator | — | med 0.3 / avg 0.3 (min 0.3, max 0.3, n=5) |
| First text chunk | med 1504.6 / avg 1500.6 (min 1481.6, max 1512.1, n=5) | med 2.5 / avg 2.5 (min 2.4, max 2.6, n=5) |
| TTS gap (text→audio) | med 584.3 / avg 599.4 (min 448.9, max 767.9, n=5) | med 548.4 / avg 593.0 (min 494.5, max 740.4, n=5) |
| TTFA | med 2090.7 / avg 2100.0 (min 1953.5, max 2266.0, n=5) | med 550.9 / avg 595.4 (min 496.9, max 742.9, n=5) |
| Total | med 10715.4 / avg 10901.2 (min 10369.2, max 11548.5, n=5) | med 2329.6 / avg 2354.7 (min 2215.3, max 2549.0, n=5) |

### Places — Yaoundé

| Metric | Legacy | Orchestrator |
|--------|--------|--------------|
| STT | 0 (text turn) | 0 (text turn) |
| Orchestrator | — | med 4.2 / avg 4.4 (min 3.5, max 5.6, n=5) |
| First text chunk | med 796.3 / avg 796.3 (min 796.3, max 796.3, n=1) | med 7.4 / avg 8.0 (min 7.1, max 9.9, n=5) |
| TTS gap (text→audio) | med 618.7 / avg 618.7 (min 618.7, max 618.7, n=1) | med 485.9 / avg 549.9 (min 480.6, max 664.5, n=5) |
| TTFA | med 1415.0 / avg 1415.0 (min 1415.0, max 1415.0, n=1) | med 493.3 / avg 558.0 (min 487.7, max 674.4, n=5) |
| Total | med 15717.3 / avg 15717.3 (min 15717.3, max 15717.3, n=1) | med 12336.9 / avg 12812.2 (min 11893.8, max 14450.1, n=5) |

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
