# Voice pipeline audit — Smartmboa Tour

## Before (baseline architecture)

Sequential **HTTP** turns only:

1. `POST /api/speech/transcribe` (HF Whisper cloud)
2. `POST /api/chat` (RAG + optional web + Qwen, **non-streaming**)
3. `POST /api/speech/synthesize` (Fish Audio, full MP3 buffered)

Observed bottlenecks from code review:

| Phase | Issue |
|-------|--------|
| STT | Service recreated each request (`get_speech_service` uncached); local Whisper would reload the model every time |
| Routing | Every turn ran RAG + possible web search, including « Bonjour » |
| LLM | `stream: false` — first audio waited for the full answer |
| TTS | Full body buffered server-side before any bytes reached the client |
| Transport | Three round-trips; no interrupt channel |
| Vision | Gemini only on `/api/vision/identify` (OK) — not on voice |

Gemini was **not** used for standard voice turns (already correct).

## Target (implemented)

```
mic → STT → route → (Top-K retrieval + cache)? → Qwen stream → Fish stream → speaker
                 ↘ interrupt via WebSocket
```

### Delivered

- **WebSocket** `WS /api/voice/session` with events: `ready`, `status`, `transcript`, `route`, `token`, `assistant_text`, `audio_chunk`, `audio_done`, `turn_done`, `interrupted`, `error`
- **Query router**: simple greetings skip KB/web
- **Qwen streaming** (`stream: true`) with sentence-level TTS handoff
- **Fish Audio streaming** (`synthesize_stream`) — first chunk as soon as TTFB
- **STT/TTS singleton** (no per-request recreate / Whisper reload)
- **RAG cache** in-memory TTL + optional `REDIS_URL`
- **Optional HF remote embeddings** (`RAG_VECTOR_ENABLED=true`) merged with lexical via RRF
- **Interrupt** during assistant speech (client orb + `interrupt` event)
- **Gemini** remains image-only (`/api/vision/identify`)
- Mobile prefers WebSocket voice path; HTTP fallback kept
- Latency helper: `backend/scripts/measure_voice_latency.py`

### Config knobs

```env
RAG_VECTOR_ENABLED=false   # set true to warm HF embeddings in background
RAG_CACHE_TTL_SECONDS=300
REDIS_URL=                 # optional
```

### Measure before / after

```bash
# With backend + secrets loaded:
python backend/scripts/measure_voice_latency.py --label after --out docs/latency-after.json
```

Latest live after snapshot (`docs/latency-after.json`):

| Probe | grounding | llm_ttft | tts_ttfb | notes |
|-------|-----------|----------|---------|-------|
| simple « Bonjour » | **0 ms** (KB skipped) | ~420 ms | ~260 ms | No RAG/web |
| grounded Yaoundé | ~3.3 s (web+KB) | ~710 ms | ~230 ms | Streamed LLM+TTS |

Before (sequential non-streaming): greetings still paid RAG; no TTFT; TTS waited for full MP3 (~2.5–3.5 s) after the full LLM reply.
