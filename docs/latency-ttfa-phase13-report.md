# Phase 1.3 — TTFA chronology diagnostic

**Status:** instrumentation shipped; live HF E2E blocked by **HF_402** (credits depleted).  
**No architecture / model / RAG / chunker / planner changes.**

## Constraint

Hugging Face returned `402` on all non-greeting Qwen turns. Per instructions, **no invented LLM metrics**. Live Fish Audio measurements are real. Pre-TTFT wall times cited from Phase 1.2 non-greeting marks are labeled as such.

## What was instrumented

| Layer | Events |
|-------|--------|
| Backend `TurnChronology` | `llm_start`, `llm_first_token`, `chunker_first_text/flush`, `tts_queue_put`, `tts_worker_start` (+`queue_wait_ms`), Fish `tts_request_start` / `connection` / `ttfb` / `complete`, `audio_chunk_created/sent_ws`, `audio_done_sent` |
| Fish `synthesize_stream(trace=)` | `connection_latency_ms`, `ttfb_ms`, `total_tts_ms` |
| WebSocket | `backend_send_timestamp` on `audio_chunk` |
| Frontend | `ws_audio_received`, decode, queue, `first_audio_play_command`, `first_audio_actually_played` |

Script: `backend/scripts/diagnose_ttfa_phase13.py`  
Artifacts: `docs/latency-ttfa-phase13.json` (HF_402), `docs/latency-ttfa-phase13-fish.json`, `docs/latency-ttfa-phase13-synth.json`

---

## 1. Chronology (production overlap + real Fish)

Method: Phase 1.2 real non-greeting `llm_first_token` delay (~2768 ms) injected, then synthetic token stream through the **same** chunker → queue → Fish path as `voice_ws` (overlapped). Fish numbers are live.

Example turn (`food[0]`):

```
llm_start                    +0.000 s
llm_first_token              +2.771 s   (Δ 2771 ms)  ← from P1.2 wall mark
chunker_first_flush          +2.970 s   (Δ 199 ms)
tts_queue_put                +2.970 s   (Δ 0 ms)
tts_worker_start             +2.970 s   (Δ 0 ms)     queue_wait=0.1 ms
tts_request_start            +3.018 s   (Δ 48 ms)
tts_connection_established   +3.555 s   (Δ 537 ms)   ≈ Fish TTFB
tts_first_audio_byte         +3.556 s   (Δ 1 ms)
audio_chunk_sent_ws          +3.556 s
audio_done_sent              +4.355 s   (Δ 799 ms)   ← current frontend play gate
```

---

## 2. Averages (min / max)

### A. Live Fish only (n=9, real) — `latency-ttfa-phase13-fish.json`

| Metric | avg | min | max |
|--------|----:|----:|----:|
| connection_latency_ms | 488.6 | 424.7 | 636.4 |
| TTS TTFB | 490.8 | 424.7 | 636.4 |
| total first-request TTS | 1730.8 | 1449.2 | 2242.9 |
| TTFB → complete (play-gate body) | 1240.0 | 1014.8 | 1676.4 |

`connection_latency ≈ TTFB` → first audio byte arrives with response headers; remaining ~1.2 s is stream body.

### B. Overlapped synth+Fish (n=9) — `latency-ttfa-phase13-synth.json`

| Metric | avg | min | max |
|--------|----:|----:|----:|
| wall to llm_first_token (injected P1.2) | 2771 | 2771 | 2771 |
| chunker after TTFT | 172 | 121 | 199 |
| queue_wait_ms | 0.1 | 0.1 | 0.1 |
| TTFT → TTS request | 178 | 122 | 247 |
| TTS TTFB | 603 | 425 | 1021 |
| **backend first audio byte** | **3552** | 3331 | 3989 |
| audio_done (play gate) | 4625 | 3927 | 5950 |
| first_byte → audio_done | 1073 | 568 | 1961 |

### C. Phase 1.2 reported “TTFA ~6.5 s” (measurement artifact)

`measure_voice_stream_opt.py` marked `tts_first_fragment` early, then **waited for full LLM** before Fish:

| Run | llm_first_token | first_frag | tts_start | TTFA | frag→tts_start |
|-----|----------------:|-----------:|----------:|-----:|---------------:|
| food_r0 | 2710 | 2769 | 6412 | 6887 | **+3643 ms** |
| nature_r0 | 2825 | 2901 | 5999 | 6463 | **+3099 ms** |

That +3–3.6 s is **not** production `voice_ws` (which overlaps). KPI “LLM TTFT ≈ 245 ms” is only the HF stream phase after RAG — not wall time from turn start (~2.7 s).

### D. Backend → frontend / player

WS E2E with live LLM: **not measured (HF_402)**.  
Code: `useContinuousVoiceSession` buffers `audio_chunk` and calls `playBase64Mp3` only on `audio_done` → earliest audible ≥ first_byte + Fish body (~+1.0–1.2 s) + decode/play.

---

## 3. BIGGEST LATENCY GAP

```
BIGGEST LATENCY GAP:
llm_start → llm_first_token = 2771 ms
```

(Source: Phase 1.2 non-greeting wall marks; RAG + routing + HF time-to-first-token. Not the 245 ms phase KPI.)

Runner-up (audible path): `tts_first_audio_byte → audio_done_sent` ≈ **1073 ms avg** (frontend play gate).

---

## 4. Why TTFA looked ~6.5 s while LLM TTFT ≈ 245 ms and TTS TTFB ≈ 501 ms?

Three stacked effects:

1. **KPI mismatch** — 245 ms is post-RAG HF TTFT; wall clock to first token ≈ **2.7 s**.
2. **Phase 1.2 measure script did not overlap TTS** — added **~3.0–3.6 s** after the first phrase was ready.
3. **Frontend play gate** — player starts on `audio_done`, not first byte (**~+1.0–1.2 s** for audible).

Production overlapped backend first audio is closer to **~3.5 s** (not 6.5 s). Audible with current player ≈ **~4.6 s**.

---

## 5. Hypotheses

| ID | Verdict | Evidence |
|----|---------|----------|
| A LLM slow to usable phrase | **Partial** | Wall to first token ~2.7 s; after TTFT, phrase ready in ~120–200 ms |
| B Chunker waits too long | **No** | ~172 ms after TTFT; queue 0.1 ms |
| C TTS request starts late | **No** in production overlap; **Yes** in P1.2 measure script (+3 s artifact) |
| D Fish slower than TTFB | **Partial** | TTFB ~490–600 ms real; full first request ~1.7 s |
| E WebSocket | **Unmeasured** (HF_402) | Likely small on localhost |
| F Frontend player late | **Yes** for audible | Plays on `audio_done`, not first chunk |
| G Several factors | **Yes** | pre-TTFT + Fish TTFB + play gate (+ measure artifact in P1.2) |

---

## 6. Recommendation (diagnostic only — no change applied)

When HF credits return, re-run `diagnose_ttfa_phase13.py` for live Qwen chronology.

Clear next levers (do **not** change models/RAG/chunker yet):

1. **Confirm production VOICE PERF / TTFA TRACE** on a real jury turn (instrumentation is in place).
2. If audible TTFA is the KPI: **start playback on first `audio_chunk`** (or progressive MSE), not `audio_done` — measurements show ~1 s on the table.
3. If backend first-byte is the KPI: attack **pre-first-token** (RAG/routing/HF wall ~2.7 s), not the chunker.

Stop after this report — Phase 2 not started.
