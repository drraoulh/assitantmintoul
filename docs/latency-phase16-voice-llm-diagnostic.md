# Phase 1.6 — Diagnostic délai réel avant premier token

Instrumentation du chemin **production** `voice_ws → HuggingFaceAIService.stream_response`.
Modèle inchangé : `Qwen/Qwen3.5-9B:fastest`.

- Runs demandés : 3
- Valid : 3 / Failed : 0

## Tableau récapitulatif

| Run | Prepare | Provider | Parse | App TTFT | First phrase | Total | Retry | Fallback |
|----:|--------:|---------:|------:|---------:|-------------:|------:|------:|:--------:|
| `voice-20260924-food-00` | 2392.5 | 311.1 | 0.3 | 2703.9 | 2760.1 | 6656.7 | 0 | no |
| `voice-20260924-yaounde-01` | 2358.0 | 357.9 | 0.2 | 2716.1 | 2832.6 | 6780.4 | 0 | no |
| `voice-20260924-nature-02` | 2351.8 | 668.2 | 0.2 | 3020.2 | 3086.5 | 6531.3 | 0 | no |

## Timelines (runs valides)

### `voice-20260924-food-00` — food cold=True
```
llm_start                    +     0.0 ms  (Δ 0.0 ms)
conversation_store_start_done +  1283.8 ms  (Δ 1283.8 ms)
conversation_history_loaded  +  2358.5 ms  (Δ 1074.7 ms)
routing_done                 +  2358.8 ms  (Δ 0.3 ms)
prompt_ready                 +  2361.6 ms  (Δ 2.8 ms)
request_object_created       +  2361.6 ms  (Δ 0.0 ms)
stream_body_ready            +  2362.0 ms  (Δ 0.4 ms)
headers_ready                +  2362.1 ms  (Δ 0.1 ms)
http_client_selected         +  2362.1 ms  (Δ 0.0 ms)
provider_call_started        +  2392.5 ms  (Δ 30.4 ms)
http_request_dispatched      +  2392.5 ms  (Δ 0.0 ms)
provider_response_headers    +  2703.6 ms  (Δ 311.1 ms)
stream_iterator_created      +  2703.6 ms  (Δ 0.0 ms)
first_stream_event           +  2703.8 ms  (Δ 0.2 ms)
first_token                  +  2703.9 ms  (Δ 0.1 ms)
first_useful_text            +  2703.9 ms  (Δ 0.0 ms)
first_phrase_ready           +  2760.1 ms  (Δ 56.2 ms)
llm_end                      +  6656.7 ms  (Δ 3896.6 ms)
```

### `voice-20260924-yaounde-01` — yaounde cold=False
```
llm_start                    +     0.0 ms  (Δ 0.0 ms)
conversation_store_start_done +  1278.1 ms  (Δ 1278.1 ms)
conversation_history_loaded  +  2351.7 ms  (Δ 1073.6 ms)
routing_done                 +  2351.8 ms  (Δ 0.1 ms)
prompt_ready                 +  2357.9 ms  (Δ 6.1 ms)
request_object_created       +  2357.9 ms  (Δ 0.0 ms)
stream_body_ready            +  2358.0 ms  (Δ 0.1 ms)
headers_ready                +  2358.0 ms  (Δ 0.0 ms)
http_client_selected         +  2358.0 ms  (Δ 0.0 ms)
provider_call_started        +  2358.0 ms  (Δ 0.0 ms)
http_request_dispatched      +  2358.0 ms  (Δ 0.0 ms)
provider_response_headers    +  2715.9 ms  (Δ 357.9 ms)
stream_iterator_created      +  2715.9 ms  (Δ 0.0 ms)
first_stream_event           +  2716.1 ms  (Δ 0.2 ms)
first_token                  +  2716.1 ms  (Δ 0.0 ms)
first_useful_text            +  2716.1 ms  (Δ 0.0 ms)
first_phrase_ready           +  2832.6 ms  (Δ 116.5 ms)
llm_end                      +  6780.4 ms  (Δ 3947.8 ms)
```

### `voice-20260924-nature-02` — nature cold=False
```
llm_start                    +     0.0 ms  (Δ 0.0 ms)
conversation_store_start_done +  1284.7 ms  (Δ 1284.7 ms)
conversation_history_loaded  +  2348.4 ms  (Δ 1063.7 ms)
routing_done                 +  2348.5 ms  (Δ 0.1 ms)
prompt_ready                 +  2351.7 ms  (Δ 3.2 ms)
request_object_created       +  2351.7 ms  (Δ 0.0 ms)
stream_body_ready            +  2351.7 ms  (Δ 0.0 ms)
headers_ready                +  2351.8 ms  (Δ 0.1 ms)
http_client_selected         +  2351.8 ms  (Δ 0.0 ms)
provider_call_started        +  2351.8 ms  (Δ 0.0 ms)
http_request_dispatched      +  2351.8 ms  (Δ 0.0 ms)
provider_response_headers    +  3020.0 ms  (Δ 668.2 ms)
stream_iterator_created      +  3020.0 ms  (Δ 0.0 ms)
first_stream_event           +  3020.2 ms  (Δ 0.2 ms)
first_token                  +  3020.2 ms  (Δ 0.0 ms)
first_useful_text            +  3020.2 ms  (Δ 0.0 ms)
first_phrase_ready           +  3086.5 ms  (Δ 66.3 ms)
llm_end                      +  6531.3 ms  (Δ 3444.8 ms)
```

## Stats

```json
{
  "llm_prepare_ms": {
    "avg": 2367.4,
    "median": 2358.0,
    "min": 2351.8,
    "max": 2392.5,
    "n": 3
  },
  "provider_ttfh_ms": {
    "avg": 445.7,
    "median": 357.9,
    "min": 311.1,
    "max": 668.2,
    "n": 3
  },
  "stream_parse_ms": {
    "avg": 0.2,
    "median": 0.2,
    "min": 0.2,
    "max": 0.3,
    "n": 3
  },
  "app_ttft_ms": {
    "avg": 2813.4,
    "median": 2716.1,
    "min": 2703.9,
    "max": 3020.2,
    "n": 3
  },
  "first_useful_text_ms": {
    "avg": 2813.4,
    "median": 2716.1,
    "min": 2703.9,
    "max": 3020.2,
    "n": 3
  },
  "first_phrase_ready_ms": {
    "avg": 2893.1,
    "median": 2832.6,
    "min": 2760.1,
    "max": 3086.5,
    "n": 3
  },
  "generation_ms": {
    "avg": 6656.1,
    "median": 6656.7,
    "min": 6531.3,
    "max": 6780.4,
    "n": 3
  },
  "fallback_rate": 0.0
}
```

## Phase 1.5 vs Phase 1.6

Phase 1.5 (direct `_stream_tokens` / warm) : TTFT ≈ 245–280 ms, avg opportuniste ≈ 440 ms. Phase 1.6 mesure le chemin `stream_response` voice (routing+RAG+prompt+HTTP+SSE) avec métriques séparées prepare / provider_ttfh / parse / app_ttft. app_ttft avg ici = 2813.4 ms ; provider_ttfh avg = 445.7 ms ; prepare avg = 2367.4 ms ; fallback_rate = 0.0.

## Analyse des hypothèses

Sur n=3 runs valides : prepare_avg=2367.4ms, provider_ttfh_avg=445.7ms, parse_avg=0.2ms, app_ttft_avg=2813.4ms, fallback_rate=0%. Contribution dominante estimée : **prepare (B)**. **Hypothèse B** : délai important AVANT l’appel HF (préparation app). Cold app_ttft avg=2703.9ms (n=1) vs warm avg=2868.1ms (n=2) → **Hypothèse G** possible (cold TLS/provider). **Hypothèse F** : Phase 1.5 chronométrait surtout `_stream_tokens` (après grounding), alors que le `llm_start` voice_ws/Phase1.2 englobait routing+grounding+LLM — et un fallback non-stream transforme TTFT en durée totale.

## Conclusion

Les ~2.7 s historiques llm_start→first_token ne sont pas un mystère de « Qwen lent à 250 ms ». Selon les métriques séparées ci-dessus, localiser le budget dans prepare vs provider_ttfh vs fallback non-stream. Pas de fallback sur les runs valides de cette session.
