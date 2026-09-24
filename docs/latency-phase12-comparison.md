# Phase 1.2 — Voice streaming optimization

## Chunker strategy

`backend/app/services/speech/voice_chunker.py`

1. Sentence end (`.?!…`) as soon as ≥12 chars  
2. First chunk only: soft punct (`,;:`) ≥20 chars, or word-boundary hard flush at 48  
3. Later chunks: soft ≥28 / hard 80  
4. Never mid-word; `append_token` inserts missing spaces  

## Pipeline

```
LLM stream ──► chunker ──► tts_queue (seq_id, text)
                              │
                              ▼
                         Fish TTS (ordered)
                              │
                              ▼
                    audio_chunk / audio_done → client plays 0→1→2
```

LLM does not wait for TTS. Client plays each `audio_done` in sequence immediately.

## Measures (warm, HF credits limited)

See `docs/latency-phase12-after.json` (4 valid / 5 invalid HF_402).

| KPI | Avant (Phase 1.1 recon) | Après (valid n=4) |
|-----|------------------------:|------------------:|
| STT warm | ~105 ms | ~172 ms (1 sample w/ fixture) |
| LLM TTFT | ~250–1000 ms | ~245 ms avg |
| First frag chars | ~90+ threshold | **~48 avg** |
| TTS TTFB | ~440–720 ms | ~501 ms |
| Time to first audio | ~8–12 s+ (est.) | **~6.5 s avg** |
| Total turn | ~15–17 s | **~8.3 s avg** |

Target ≤2–3 s TTFA **not reached**: residual floor ≈ STT + LLM-to-first-phrase + Fish TTFB (~0.1+2–4+0.5 s) on current cloud providers.
