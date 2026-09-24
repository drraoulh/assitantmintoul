# Phase 2.6 — True Qwen → TTS streaming

PHASE 2.6 — RESULT

Status: **PASS**

Architecture:
Qwen STREAM → Text Queue (voice_chunker) → TTS → Audio Queue → WebSocket

Qwen TTFT: **371.1 ms**

First text chunk: **419.0 ms**

First TTS start: **482.6 ms**

TTS TTFB: **607.3 ms**

TTFA: **1091.0 ms**

Previous TTFA: ~3028 ms

Historical legacy warm TTFA: ~1100 ms

Qwen total: **11330.6 ms**

Audio done: **24719.2 ms**

Text token events: **140**

TTS requests (text chunks): **11**

Audio chunk events: **161**

LLM calls: **1**

First audio before Qwen finished: **YES**
(server marks: audio_first_chunk_sent 1090.2 ms < llm_end 12896.0 ms)

First audio before audio_done: **YES**

Fallback: **PASS** (unit: 402 / timeout → deterministic Agent 4, max 1 LLM call)

Cancellation: **PASS** (unit-covered interrupt + queue cleanup; not exercised live)

Tests: **184 passed, 1 warning in 1.11s**

Feature flag:
VOICE_LLM_STREAMING_ENABLED = true (canary only; **default false**)

## Before vs after

| Path | Behaviour | TTFA |
|------|-----------|------|
| Phase 2.5C | Qwen complete → fake-stream → TTS | ~3028 ms |
| Phase 2.6 | Qwen stream → first text chunk → TTS | **1091 ms** |
| Legacy warm | (historical baseline) | ~1100 ms |

## Architecture notes

- Agents 1–3 via `AgentOrchestrator.prepare` (unchanged models / RAG / KB)
- Agent 4 builds messages then streams Qwen tokens live (`_stream_via_orchestrator_true_stream`)
- Existing `voice_chunker` + sequential TTS worker consume tokens while Qwen continues
- Bounded TTS queue (`VOICE_TTS_QUEUE_MAXSIZE`, default 4) for backpressure
- Text mode (`brief=False`) never enters the true-stream branch

## Conclusion

True streaming Qwen → TTS is validated. TTS starts while Qwen is still generating.
TTFA dropped from ~3028 ms to **1091 ms**, matching the historical legacy warm baseline,
without changing models. Defaults remain off for safe rollback.

## Safety

- Defaults remain false: `AGENT_ORCHESTRATOR_ENABLED` / `AGENT_ORCHESTRATOR_USE_LLM` / `VOICE_LLM_STREAMING_ENABLED`
- No secrets logged
- Maximum 1 LLM call per user turn
