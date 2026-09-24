# Phase 3.1 — Structured ChatResponse

## Goal

Attach deterministic tourism UI payloads to HTTP `ChatResponse` for the Next.js
client, without adding Agent 5 or a second LLM call.

## Flow

```
Agents 1–3 → Agent 4 FinalResponse
                 ↓
         build_structured_ui()   (< 50 ms, no LLM)
                 ↓
         ChatResponse (+ places/map/itinerary/…)
                 ↓
         frontend-web ResponseRenderer
```

## Compatibility

- Expo / legacy clients keep reading `message` + `sources`.
- New field `text` mirrors `message`.
- Optional structured fields default to empty / null.

## Voice

UI metadata is attached to WebSocket `turn_done` **after** audio streaming —
TTFA path unchanged.
