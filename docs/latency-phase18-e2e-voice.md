# Phase 1.8 — End-to-end voice latency (TTFA)

Mesure uniquement — **aucun changement** LLM / RAG / store / STT / TTS / frontend / WS.

KPI principal :

```
TTFA = frontend_playback_start − user_speech_end
```

Avec early-play (Phase 1.4) : `frontend_playback_start ≈ first audio_chunk receive` (+0 ms).
Tours WS en `type=text` → STT = 0 ms sur le chemin critique (STT isolé mesuré à part : avg=269.0 ms).

- Runs demandés / scénario : 3
- Runs valides totaux : 5 / failed : 7
- Base URL : `http://127.0.0.1:8000`

## Tableau final (moyennes, ms)

| Scenario | STT | Store | RAG | LLM TTFT | First phrase | TTS TTFB | Audio network | Playback | TTFA |
|----------|----:|------:|----:|---------:|-------------:|---------:|--------------:|---------:|-----:|
| New thread | 0.0 | 0.6 | — | 1106.1 | 1323.0 | 479.5 | 0.6 | 0.0 | **1809.2** |
| Multi-turn | — | — | — | — | — | — | — | — | **—** |
| Existing cold | — | — | — | — | — | — | — | — | **—** |
| Warm | 0.0 | 0.0 | — | 621.7 | 911.2 | 504.4 | 0.7 | 0.0 | **1417.3** |

## TTFA global (tous scénarios valides)

- n = 5
- avg = **1652.5 ms**
- median = **1080.6 ms**
- min = 966.1 ms
- max = 3465.3 ms
- p95 = 3465.3 ms

## Timelines exemples

### Scenario A — nouveau thread
Turn `Propose-moi une activité nature au Cameroun.` — TTFA=966.1 ms
```
user_speech_end              +     0.0 ms
stt_start                    +     0.1 ms
stt_end                      +     0.1 ms
rag_start                    +     4.4 ms
llm_first_token              +   417.5 ms
llm_generating_status        +   417.6 ms
tts_first_audio              +   966.1 ms
websocket_audio_sent         +   966.1 ms
frontend_audio_received      +   966.1 ms
frontend_playback_start      +   966.1 ms
audio_done                   +  2625.6 ms
turn_complete                + 12787.4 ms
```
store=0.0 mode=prepare_no_db llm_ttft=416.2 tts_ttfb=454.0 network=0.6

### Scenario B — multi-turn
Aucun run valide (FAILED_HTTP_402).

### Scenario C — existing cold
Aucun run valide (FAILED_HTTP_402).

### Scenario D — warm
Turn `Propose-moi une activité nature au Cameroun.` — TTFA=1080.6 ms
```
user_speech_end              +     0.0 ms
stt_start                    +     0.1 ms
stt_end                      +     0.1 ms
rag_start                    +     1.2 ms
llm_first_token              +   303.1 ms
llm_generating_status        +   303.1 ms
tts_first_audio              +  1080.6 ms
websocket_audio_sent         +  1080.6 ms
frontend_audio_received      +  1080.6 ms
frontend_playback_start      +  1080.6 ms
audio_done                   +  2041.8 ms
turn_complete                +  6941.6 ms
```
store=0.0 mode=prepare_no_db llm_ttft=302.1 tts_ttfb=540.4 network=0.8

## Lecture des résultats

- **Médiane TTFA ≈ 1081 ms** (plus représentative que la moyenne tirée par le 1er run froid LLM à 3465 ms).
- Store Phase 1.7 confirmé : **~0 ms** sur new/warm (`prepare_no_db`).
- STT hors chemin text : avg isolé **269 ms** (cold 589 / warm ~100) → TTFA voix mic estimé ≈ TTFA_text + STT.
- Multi-turn / cold : `FAILED_HTTP_402` ou Fish unreachable — **non inventés**.

## Breakdown — contribution au TTFA

Contributions moyennes estimées (ms, segments non strictement additifs) :
- LLM_TTFT: 912.4 ms
- TTS_TTFB: 489.5 ms
- chunking: 245.9 ms
- network: 0.6 ms
- conversation_store: 0.4 ms
- STT: 0.0 ms
- RAG: 0.0 ms
- frontend_playback: 0.0 ms

## Comparaison historique

| Phase | First audio / TTFA | Total turn | Note |
|-------|-------------------:|-----------:|------|
| Initial | ~15–17 s (séquentiel) | ~15–17 s | avant optimisations |
| Phase 1 | grounding ↓ ; TTS encore séquentiel | ~15–17 s | RAG/web |
| Phase 1.2 | TTFA rapporté ~6.5 s (artéfact) | ~8.3 s | overlap LLM→TTS |
| Phase 1.3 | backend first audio ~3552 ms ; play gate ~4625 | — | diagnostic |
| Phase 1.4 early-play | receive→play **808 → 0** ms | TTFA −~0.8 s | play on audio_chunk |
| Phase 1.6 | app_ttft ~2827 (store ~2370) | — | store bottleneck |
| Phase 1.7 | store ~0.1 (new/cached) ; app_ttft ~338 | — | store fix |
| **Phase 1.8** | **TTFA avg 1652.5 ms** | see runs | E2E mesuré |

## Nouveau bottleneck

**LLM_TTFT** est le plus grand contributeur mesuré au TTFA (~912 ms avg sur n=5). Ne pas optimiser autre chose avant confirmation sur plus de runs.

## STT isolé (référence)

```json
{
  "avg": 269.0,
  "median": 121.1,
  "min": 97.2,
  "max": 588.7,
  "p95": null,
  "n": 3
}
```

## Tests

`pytest -q` : 88 passed

## Méthode

- Pas de modification production.
- Scénarios A/B/D : WebSocket live `/api/voice/session`.
- Scénario C : in-process avec `_cache_invalidate` (cold miss SqlConversationStore).
- `FAILED_HTTP_402` reporté tel quel, jamais inventé.
