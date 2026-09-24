# Phase 2.7 — Grounding enforcement

PHASE 2.7 — RESULT

Status: **PASS**

Grounding: **PASS**
Place whitelist: **PASS**
Restaurant grounding: **PASS**
Hotel grounding: **PASS**
Price grounding: **PASS**
Opening hours grounding: **PASS**
Activity grounding: **PASS**
Distance grounding: **PASS**
Itinerary grounding: **PASS**
Web evidence grounding: **PASS**
Africa in miniature protection: **PASS**
Fallback: **PASS**
Streaming preserved: **PASS**

LLM calls (voice): **1**
TTFT: **516.7 ms**
TTFA: **1197.8 ms**
Grounding validation: **1.683 ms**
Tests: **205 passed / 0 failed**
Regression: **PASS**

## Current flows (pre-change summary)

- **Grounding flow:** Agent 2 validates published places; Agent 3 keeps plan IDs ⊆ knowledge; Agent 4 mostly prompt-only (validate.py unused in prod).
- **Response flow:** Deterministic default; optional one Qwen call via Agent 4.
- **Streaming flow (2.6):** `prepare` → `build_messages` → live Qwen tokens → TTS overlap.
- **Evidence:** `PlaceEvidence` / plan items / sources; web as labeled knowledge chunks.
- **Risks:** true-stream bypassed Agent 4 `generate()`; empty FOOD could let Qwen invent restaurants.

## Architecture after

1. `allowed_evidence` whitelist in structured context (IDs + names + costs + activities + URLs)
2. Stricter Agent 4 system prompt (Qwen is NOT a knowledge source)
3. Pre-LLM skip when fact-heavy / foodish query has empty verified evidence
4. Deterministic post-check (`validate_grounding`) — replaces complete-path replies on critical violations
5. Streaming: validation is **non-blocking** after tokens (does not delay TTFA)

## Real scenario proofs

- Fish / no invented restaurants: **PASS** (pre-gate skip_llm=True, **llm_calls=0**)
  - preview: `Could you tell me a bit more about what you are looking for?`
  - injected hallucination `African Food By Emy` blocked by validator
- Foumban / no Kimbi–Mbingo: **PASS** (LLM invented them → replaced with grounded plan)
  - plan places only: Palais des Rois Bamoun, Palais du Sultan (Foumban)
- Streaming regression: first audio before Qwen finished = **YES**; TTFA **1197.8 ms** vs Phase 2.6 ~1091 ms

## Feature flags

| Flag | Default |
|------|---------|
| `GROUNDING_ENFORCEMENT_ENABLED` | **false** |
| `AGENT_ORCHESTRATOR_ENABLED` | false |
| `AGENT_ORCHESTRATOR_USE_LLM` | false |
| `VOICE_LLM_STREAMING_ENABLED` | false |

## Conclusion

Grounding enforcement blocks invented restaurants/places without a second LLM and without waiting for full Qwen before TTS. Voice TTFA stays near the Phase 2.6 baseline (~1.2 s vs ~1.1 s).
