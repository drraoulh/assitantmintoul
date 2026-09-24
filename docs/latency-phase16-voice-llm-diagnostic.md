# Phase 1.6 — Diagnostic délai réel avant premier token

Instrumentation du chemin **production** `voice_ws → HuggingFaceAIService.stream_response`.
Modèle inchangé : `Qwen/Qwen3.5-9B:fastest`.

- Runs demandés : 5
- Valid : 3 / Failed : 2

## Tableau récapitulatif

| Run | Prepare | Store | Provider | Parse | App TTFT | First phrase | Total | Retry | Fallback |
|----:|--------:|------:|---------:|------:|---------:|-------------:|------:|------:|:--------:|
| `voice-20260924-food-00` | 2436.8 | 2395.8 | 292.1 | 0.3 | 2729.2 | 2877.2 | 7077.4 | 0 | no |
| `voice-20260924-yaounde-01` | 2360.8 | 2354.0 | 248.0 | 0.3 | 2609.1 | 2767.1 | 6806.6 | 0 | no |
| `voice-20260924-nature-02` | 2362.9 | 2359.5 | 778.6 | 0.2 | 3141.8 | 3282.3 | 6959.3 | 0 | no |
| `voice-20260924-trip3-03` | — | 2380.1 | — | — | — | — | — | 1 | FAILED FAILED_HTTP_402 |
| `voice-20260924-food-04` | — | 2368.5 | — | — | — | — | — | 1 | FAILED FAILED_HTTP_402 |

## Timelines (runs valides)

### `voice-20260924-food-00` — food cold=True
```
llm_start                    +     0.0 ms  (Δ 0.0 ms)
conversation_store_start_done +  1314.1 ms  (Δ 1314.1 ms)
conversation_history_loaded  +  2395.8 ms  (Δ 1081.7 ms)
routing_done                 +  2396.1 ms  (Δ 0.3 ms)
prompt_ready                 +  2398.9 ms  (Δ 2.8 ms)
request_object_created       +  2398.9 ms  (Δ 0.0 ms)
stream_body_ready            +  2399.4 ms  (Δ 0.5 ms)
headers_ready                +  2399.4 ms  (Δ 0.0 ms)
http_client_selected         +  2399.4 ms  (Δ 0.0 ms)
provider_call_started        +  2436.8 ms  (Δ 37.4 ms)
http_request_dispatched      +  2436.8 ms  (Δ 0.0 ms)
provider_response_headers    +  2728.9 ms  (Δ 292.1 ms)
stream_iterator_created      +  2729.0 ms  (Δ 0.1 ms)
first_stream_event           +  2729.1 ms  (Δ 0.1 ms)
first_token                  +  2729.2 ms  (Δ 0.1 ms)
first_useful_text            +  2729.2 ms  (Δ 0.0 ms)
first_phrase_ready           +  2877.2 ms  (Δ 148.0 ms)
llm_end                      +  7077.4 ms  (Δ 4200.2 ms)
```
- store_total=2395.8 ms (start=1314.1 + history=1081.7); routing=0.3 ms; grounding=2.8 ms; attempts=1

### `voice-20260924-yaounde-01` — yaounde cold=False
```
llm_start                    +     0.0 ms  (Δ 0.0 ms)
conversation_store_start_done +  1292.7 ms  (Δ 1292.7 ms)
conversation_history_loaded  +  2354.0 ms  (Δ 1061.3 ms)
routing_done                 +  2354.1 ms  (Δ 0.1 ms)
prompt_ready                 +  2360.7 ms  (Δ 6.6 ms)
request_object_created       +  2360.7 ms  (Δ 0.0 ms)
stream_body_ready            +  2360.8 ms  (Δ 0.1 ms)
headers_ready                +  2360.8 ms  (Δ 0.0 ms)
http_client_selected         +  2360.8 ms  (Δ 0.0 ms)
provider_call_started        +  2360.8 ms  (Δ 0.0 ms)
http_request_dispatched      +  2360.8 ms  (Δ 0.0 ms)
provider_response_headers    +  2608.8 ms  (Δ 248.0 ms)
stream_iterator_created      +  2608.9 ms  (Δ 0.1 ms)
first_stream_event           +  2609.0 ms  (Δ 0.1 ms)
first_token                  +  2609.1 ms  (Δ 0.1 ms)
first_useful_text            +  2609.1 ms  (Δ 0.0 ms)
first_phrase_ready           +  2767.1 ms  (Δ 158.0 ms)
llm_end                      +  6806.6 ms  (Δ 4039.5 ms)
```
- store_total=2354.0 ms (start=1292.7 + history=1061.3); routing=0.1 ms; grounding=6.6 ms; attempts=1

### `voice-20260924-nature-02` — nature cold=False
```
llm_start                    +     0.0 ms  (Δ 0.0 ms)
conversation_store_start_done +  1275.0 ms  (Δ 1275.0 ms)
conversation_history_loaded  +  2359.5 ms  (Δ 1084.5 ms)
routing_done                 +  2359.6 ms  (Δ 0.1 ms)
prompt_ready                 +  2362.8 ms  (Δ 3.2 ms)
request_object_created       +  2362.8 ms  (Δ 0.0 ms)
stream_body_ready            +  2362.9 ms  (Δ 0.1 ms)
headers_ready                +  2362.9 ms  (Δ 0.0 ms)
http_client_selected         +  2362.9 ms  (Δ 0.0 ms)
provider_call_started        +  2362.9 ms  (Δ 0.0 ms)
http_request_dispatched      +  2362.9 ms  (Δ 0.0 ms)
provider_response_headers    +  3141.5 ms  (Δ 778.6 ms)
stream_iterator_created      +  3141.6 ms  (Δ 0.1 ms)
first_stream_event           +  3141.7 ms  (Δ 0.1 ms)
first_token                  +  3141.8 ms  (Δ 0.1 ms)
first_useful_text            +  3141.8 ms  (Δ 0.0 ms)
first_phrase_ready           +  3282.3 ms  (Δ 140.5 ms)
llm_end                      +  6959.3 ms  (Δ 3677.0 ms)
```
- store_total=2359.5 ms (start=1275.0 + history=1084.5); routing=0.1 ms; grounding=3.2 ms; attempts=1

## Stats

```json
{
  "llm_prepare_ms": {
    "avg": 2386.8,
    "median": 2362.9,
    "min": 2360.8,
    "max": 2436.8,
    "n": 3
  },
  "store_start_ms": {
    "avg": 1293.9,
    "median": 1292.7,
    "min": 1275.0,
    "max": 1314.1,
    "n": 3
  },
  "store_history_ms": {
    "avg": 1075.8,
    "median": 1081.7,
    "min": 1061.3,
    "max": 1084.5,
    "n": 3
  },
  "store_total_ms": {
    "avg": 2369.8,
    "median": 2359.5,
    "min": 2354.0,
    "max": 2395.8,
    "n": 3
  },
  "routing_only_ms": {
    "avg": 0.2,
    "median": 0.1,
    "min": 0.1,
    "max": 0.3,
    "n": 3
  },
  "grounding_ms": {
    "avg": 4.2,
    "median": 3.2,
    "min": 2.8,
    "max": 6.6,
    "n": 3
  },
  "provider_ttfh_ms": {
    "avg": 439.6,
    "median": 292.1,
    "min": 248.0,
    "max": 778.6,
    "n": 3
  },
  "stream_parse_ms": {
    "avg": 0.3,
    "median": 0.3,
    "min": 0.2,
    "max": 0.3,
    "n": 3
  },
  "app_ttft_ms": {
    "avg": 2826.7,
    "median": 2729.2,
    "min": 2609.1,
    "max": 3141.8,
    "n": 3
  },
  "first_useful_text_ms": {
    "avg": 2826.7,
    "median": 2729.2,
    "min": 2609.1,
    "max": 3141.8,
    "n": 3
  },
  "first_phrase_ready_ms": {
    "avg": 2975.5,
    "median": 2877.2,
    "min": 2767.1,
    "max": 3282.3,
    "n": 3
  },
  "generation_ms": {
    "avg": 6947.8,
    "median": 6959.3,
    "min": 6806.6,
    "max": 7077.4,
    "n": 3
  },
  "fallback_rate": 0.0
}
```

## Phase 1.5 vs Phase 1.6

Phase 1.5 chronométrait `_stream_tokens` (messages déjà construits) → TTFT warm ≈ 245–280 ms. Phase 1.6 chronomètre `stream_response` voice complet. app_ttft avg=2826.7 ms dont store_total avg=2369.8 ms (start=1293.9 + history=1075.8), provider_ttfh avg=439.6 ms, parse avg=0.3 ms. Écart 2.7s vs 250ms = surtout SqlConversationStore (Supabase), pas Qwen.

## Analyse des hypothèses

Sur n=3 runs valides (+2 FAILED, non inventés) : prepare_avg=2386.8ms, store_total_avg=2369.8ms, provider_ttfh_avg=439.6ms, parse_avg=0.3ms, app_ttft_avg=2826.7ms, fallback_rate=0%, retry_sum=0. Contribution dominante mesurée : **prepare/store (B)**. **A rejetée** : provider_ttfh avg=439.6ms (dans la bande Phase 1.5 ~250–780ms), pas 2–3s. **B CONFIRMÉE** : ~2369.8ms dans SqlConversationStore (start+get_messages) AVANT provider_call_started. **C rejetée** : gap http_client→dispatch avg=12.5ms (connexion/TLS négligeable vs store). **D rejetée** : sur les runs valides, fallback_used=false et retry_count=0 (le code fallback stream→non-stream existe, mais n’a pas tiré ici). **E rejetée** : stream_parse avg=0.3ms (first_token ≈ first_stream_event). **F CONFIRMÉE** : Phase 1.5 mesurait `_stream_tokens` (après store/RAG) → TTFT≈250–280ms ; Phase 1.6 mesure `stream_response` voice → app_ttft≈2826.7ms. Chemins différents, même modèle. **G secondaire** : cold app_ttft=2729.2ms vs warm=2875.4ms (Δ=146.2ms) — pas l’explication des ~2.7s (store domine à froid et à chaud).

## Conclusion

OÙ SONT LES ~2.7 s ? Mesure n=3 : app_ttft≈2826.7ms = SqlConversationStore≈2369.8ms (start≈1293.9 + get_messages≈1075.8) + provider_ttfh≈439.6ms + parse≈0.3ms. Hypothèse B + F confirmées. A/C/D/E rejetées sur ces mesures. Phase 1.5 ne voyait que le provider (~250ms) car elle bypassait le store. Ne pas changer Qwen pour ce symptôme. Runs 4–5: FAILED_HTTP_402 (crédits HF épuisés) — non inventés.

## Code finding (retry/fallback, mesure seulement)

huggingface._iter_sse_tokens: if stream HTTP status >= 400, falls back to non-stream POST and yields the full text as a single token. That alone can turn ~250ms TTFT into multi-second 'first_token'.
