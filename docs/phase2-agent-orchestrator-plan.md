# Phase 2.5 — Technical plan: Agent Orchestrator

## Goal

Coordinate Agents 1–4 behind a single `AgentOrchestrator` with **conditional**
capability-based routing. Do not invent facts. Do not add LLM calls beyond
Agent 4’s single presentation generation (default: deterministic renderer).

## Public interfaces (existing)

| Agent | Entry | Inputs | Output |
|-------|--------|--------|--------|
| 1 | `classify_intent(message, locale=, mode=)` | query | `IntentResult` |
| 2 | `await retrieve_knowledge(query, intent)` / `KnowledgeAgent` | query + intent | `KnowledgeResult` |
| 3 | `build_tourism_plan(query, intent, knowledge)` | query + intent + knowledge | `TourismPlan` |
| 4 | `await generate_response(query, intent, knowledge, plan, response_mode=)` | structured | `FinalResponse` |

Current production paths:

- `POST /api/chat` → `AIService.generate_response` (HF + RAG grounding)
- `WS /api/voice/session` → `AIService.stream_response` → token stream → TTS

## Orchestration rules

1. Always run Agent 1.
2. Skip Agent 2 unless `needs_knowledge` or `needs_places` (and not pure CLARIFICATION / empty greeting).
3. Skip Agent 3 unless `needs_planner` **and** Agent 2 returned usable places.
4. Always run Agent 4 last with whatever context was collected.
5. Max **one** LLM generation for the user answer (Agent 4); Agents 1–3 stay deterministic.
6. Default Agent 4 path: `prefer_deterministic=True` (no LLM) until `RESPONSE_AGENT_ENABLED` / explicit LLM injection.

## Feature flags

```
AGENT_ORCHESTRATOR_ENABLED=false   # use old chat/voice pipeline
AGENT_ORCHESTRATOR_OBSERVE=false   # log orchestrator metrics without replacing answer
```

When `ENABLED=false`: zero behavior change (voice TTFA preserved).

## Integration points

1. **Chat**: if enabled → orchestrator → map `FinalResponse` → `ChatResponse`; on error → existing `generate_response`.
2. **Voice stream**: if enabled → orchestrator (deterministic Agent 4) → emit text as streamed tokens for existing chunker/TTS; on error → existing `stream_response`.
3. **Observe**: if observe and not enabled → run orchestrator after routing for metrics only (no LLM); do not double production LLM.

## Timings

`OrchestrationTimings`: `intent_ms`, `knowledge_ms`, `planner_ms`, `response_ms`, `vision_ms`, `web_ms`, `total_ms` — use `None` when step skipped.

## Out of scope

Changing Qwen / Whisper / Fish / Gemini / RAG / pgvector / voice chunker internals.
