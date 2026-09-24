# Phase 1.9 — Final TTFA optimization

Cible : réduire/stabiliser `user_speech_end → first audible audio`.
Modèle inchangé : `Qwen/Qwen3.5-9B:fastest`. Fish / RAG / frontend inchangés.

## Audit — d’où vient le TTFT ?

Sur chemin voice warm : store≈0, RAG≈2–5 ms, app_ttft≈provider_ttfh≈350–420 ms (aligné Phase 1.5). Aucune latence locale cachée avant HF. Prompt ≈1.3–1.4k tokens (sys+KB) — déjà borné ; ne pas le couper sans preuve. Pics 2–3 s = queue/cold HF. Warm TLS au boot = handshake local seulement.

## Prompt profile (voice brief)

```json
[
  {
    "question": "Quels plats camerounais dois-je goûter ?",
    "route": "grounded",
    "skip_kb": false,
    "prepare_ms": 0.1,
    "grounding_ms": 2.0,
    "rag_ms": 1.9,
    "system_chars": 5137,
    "system_tokens_est": 1285,
    "history_chars": 0,
    "history_tokens_est": 0,
    "user_chars": 40,
    "user_tokens_est": 10,
    "total_chars": 5177,
    "total_tokens_est": 1295,
    "max_tokens": 140,
    "history_window": 3,
    "kb_chunks": 3
  },
  {
    "question": "Que puis-je visiter à Yaoundé ?",
    "route": "grounded",
    "skip_kb": false,
    "prepare_ms": 0.0,
    "grounding_ms": 4.9,
    "rag_ms": 4.8,
    "system_chars": 5759,
    "system_tokens_est": 1440,
    "history_chars": 0,
    "history_tokens_est": 0,
    "user_chars": 31,
    "user_tokens_est": 8,
    "total_chars": 5790,
    "total_tokens_est": 1448,
    "max_tokens": 140,
    "history_window": 3,
    "kb_chunks": 3
  },
  {
    "question": "Propose-moi une activité nature au Cameroun.",
    "route": "grounded",
    "skip_kb": false,
    "prepare_ms": 0.0,
    "grounding_ms": 2.2,
    "rag_ms": 2.1,
    "system_chars": 5612,
    "system_tokens_est": 1403,
    "history_chars": 0,
    "history_tokens_est": 0,
    "user_chars": 44,
    "user_tokens_est": 11,
    "total_chars": 5656,
    "total_tokens_est": 1414,
    "max_tokens": 140,
    "history_window": 3,
    "kb_chunks": 3
  }
]
```

## Optimisations appliquées

- Warm HF (+Fish) HTTP/TLS connections at API startup
- Voice chunker FIRST_HARD 48→40 (earlier first TTS flush)
- Cached static skip_kb voice/text system prompts

## TTFA final (runs valides uniquement)

- n = 3
- avg = **1173.4 ms**
- median = **1100.8 ms**
- min = 992.1 ms
- max = 1427.2 ms
- p95 = None ms
- failed excluded = 3 (FAILED_HTTP_402)

## Tableau Before / After

| Stage | Before (Phase 1.8) | After (Phase 1.9) | Gain |
|-------|-------------------:|------------------:|-----:|
| RAG | 0.0 | 0.0 | 0.0 |
| Store | 0.4 | 0.0 | 0.4 |
| LLM TTFT | 912.4 | 389.3 | 523.1 |
| Chunker | 245.9 | 258.4 | -12.5 |
| TTS TTFB | 489.5 | 521.0 | -31.5 |
| TTFA | 1080.6 | 1100.8 | -20.2 |


> Note : la ligne LLM TTFT « Before 912 → After 389 » compare la moyenne Phase 1.8 (incl. cold) à des runs **warm only** Phase 1.9 — ce n’est pas un gain de code LLM, c’est l’exclusion des outliers provider.

## Scénarios

### new_thread
valid=0 TTFA avg=— provider_ttfh=— app_ttft=— chunker=— tts_ttfb=—

### warm
valid=3 TTFA avg=1173.4 provider_ttfh=388.8 app_ttft=389.3 chunker=258.4 tts_ttfb=521.0

## Chunker A/B

```json
{}
```

## Breakdown moyen (valides)

warm n=3: store=0.0 provider_ttfh=388.8 app_ttft=389.3 chunker_wait=258.4 tts_ttfb=521.0 TTFA_median=1100.8

## Décision

**A (warm) avec réserve C** — TTFA médian warm **1100.8 ms** (n=3, min 992 / max 1427) : assez bas pour stopper l’optimisation vocale applicative. La variance cold HF (Phase 1.8 max ~3465 ms) reste un risque provider, pas un bug store/RAG.

## Conclusion

1. Bottleneck principal : Fish TTS TTFB (~521 ms avg warm)
2. Bottleneck secondaire : LLM provider TTFT (~389 ms avg warm)
3. TTFA final (médiane) : 1100.8 ms
4. Optimisation appliquée : Warm HF (+Fish) HTTP/TLS connections at API startup; Voice chunker FIRST_HARD 48→40 (earlier first TTS flush); Cached static skip_kb voice/text system prompts
5. Gain mesuré : Warm TTFA médian stable ~1.1 s (Phase 1.8 1080.6 → 1.9 1100.8). LLM app_ttft warm 389 ms (vs 912 avg Phase 1.8 incl. cold). Pas de gain TTFA spectaculaire : le plancher est maintenant Fish TTFB + LLM TTFT.
6. Recommandation : Passer à la prochaine phase produit. Ne plus optimiser le pipeline vocal applicatif sauf régression mesurée. Surveiller cold starts HF en prod.

`pytest -q` : 89 passed
