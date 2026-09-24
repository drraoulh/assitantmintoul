# Phase 2.5C — Orchestrator + Qwen real voice-path validation

PHASE 2.5C — RESULT

Status: **PASS WITH ISSUES**

Pipeline:
STT (text-turn proxy) → Agent 1 → Agent 2 → Agent 3 → Agent 4 → Qwen → TTS

Qwen: **PASS**

LLM calls: **1**

Qwen TTFT: **466.0 ms**

Qwen total: **2049.1 ms**

TTS TTFB: **927.2 ms**

TTFA: **3027.6 ms**

First audio before audio_done: **YES**

Fallback: **PASS**

Quota: **OK**

## Checklist

- [x] Agent 1 exécuté
- [x] Agent 2 exécuté
- [x] Agent 3 exécuté
- [x] Agent 4 exécuté
- [x] Qwen réellement appelé
- [x] exactement ≤1 appel LLM
- [x] TTS réellement appelé
- [x] premier chunk audio avant audio_done

## Measures

- STT total: 0.0 ms (text_turn_proxy — STT skipped once to preserve HF quota for Qwen)
- Agent 1: 0.8 ms
- Agent 2: 14.8 ms
- Agent 3: 0.7 ms
- Agent 4: 2049.5 ms
- Orchestrator total: 2065.9 ms
- Qwen TTFT: 466.0 ms
- Qwen total: 2049.1 ms
- TTS TTFB: 927.2 ms
- TTFA: 3027.6 ms
- HF HTTP status: 200
- HF authentication: OK
- Model: `Qwen/Qwen3.5-9B:fastest`
- Intent: `BUDGET_TRIP`
- Agents: `['intent', 'knowledge', 'planner', 'response']`

## Answers

- A. Full path works: **YES**
- B. Qwen called: **YES**
- C. TTS after first tokens/chunks: **YES**
- D. First audio before audio_done: **YES**
- E. Obvious latency regression: **YES**
- F. HF calls consumed: **1**

Note on E: TTFA ≈ 3028 ms includes the **full** Agent 4 Qwen generation before
TTS fake-stream. Legacy warm baseline ≈ 1100 ms streams LLM tokens into TTS
earlier. This is expected for `USE_LLM=true` complete-then-speak on the current
orchestrator wiring — not a model/TTS change in 2.5C.

## Conclusion

Chemin complet validé : Agent1→2→3→4→Qwen→TTS avec TTFA=3027.6 ms, LLM calls=1, first audio before audio_done=True.

## Safety

- Default flags remain `AGENT_ORCHESTRATOR_ENABLED=false`, `AGENT_ORCHESTRATOR_USE_LLM=false`.
- No HF token / secrets printed.
