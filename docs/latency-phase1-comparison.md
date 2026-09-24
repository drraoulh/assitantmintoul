# Phase 1 — Performance comparison

## Method

- Script: `backend/scripts/measure_voice_latency.py`
- Microbench (no LLM): `docs/latency-phase1-micro-after.json`
- Full pipeline BEFORE: `docs/latency-phase1-before.json`
- Full pipeline AFTER (successful HF window): `docs/latency-phase1-after.json`

> Note: a later AFTER re-run hit Hugging Face **402 credits depleted**;
> RAG/web/routing numbers below remain valid. LLM/TTS rows use the last
> successful AFTER capture plus BEFORE baseline.

## Summary table (ms)

| Métrique | Avant | Après | Gain |
|----------|------:|------:|-----:|
| Routing | ~0 | ~0 | — (déjà <1 ms) |
| RAG (hydrated) | (inclus dans grounding ~5285) | **~3–7** | **≫10×** |
| Grounding (KB hit, web skipped) | **~5285** | **~3–7** | **~99%** |
| Grounding (with web) | ~3338–5285 | **~414–754** | **~75–90%** |
| LLM TTFT | ~279–710 | ~276–1030 | variable (HF) |
| LLM total | ~1027–3859 | ~1023–3951 | variable (HF) |
| TTS TTFB | ~227–1284 | ~518–1174 | similar (Fish) |
| Voice total (grounded probe) | ~15788–17517 | ~14880–17044* | modest end-to-end* |

\* End-to-end still dominated by LLM + TTS cloud RTT. Phase 1 removed the
**grounding / web stall** that previously added 3–5 s before the LLM started.

## Probe detail (successful AFTER)

| Probe | RAG | Web | Grounding | LLM TTFT | LLM | TTS TTFB | Total |
|-------|----:|----:|----------:|---------:|----:|---------:|------:|
| Bonjour (simple) | 0 | 0 | 0 | 383 | 1023 | — | 11738† |
| Plats camerounais | 3.7 | 0 | 4.1 | 276 | 3005 | — | 15808† |
| Que visiter à Yaoundé | 6.4 | 0 | 6.6 | 747 | 3951 | — | 17044† |
| Circuit nature | 3.3 | 0 | 3.5 | — | timeout | — | err |
| Voice « que puis-je visiter » | 6.2 | 747 | 754 | 1030 | 1957 | — | 14880† |

† Totals include sequential TTS measurement after the full reply (not WS overlap).

## What improved most

1. **Startup RAG hydrate** — first user turn no longer pays ~3–5 s Supabase merge.
2. **Web timeout 4→2.5 s (1.5 s voice)** + parallel providers with early cancel.
3. **Tighter KB context** in voice (360 chars / 3 chunks) + history 8/4 → 6/3.
4. **Retrieval cache** normalized keys + in-memory cap; TF-IDF norms precomputed.
5. **PERF logs** with turn id for continuous monitoring.

## Still slow (out of Phase 1 scope / external)

- Hugging Face Inference Providers TTFT & throughput
- Fish Audio TTS TTFB
- Render Free cold start
- HTTP voice fallback (3 sequential RTT) on web
