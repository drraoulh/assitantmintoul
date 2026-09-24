# Voice early play (frontend only)

## Avant

```
first audio received
        ↓
wait audio_done   (~0.8–1.2 s Fish body)
        ↓
play
```

## Après

```
first audio_chunk (seq=0)
        ↓
OrderedVoiceScheduler → ProgressiveMp3Player (MSE)
        ↓
play immediately
        ↓
append later parts / play seq 1 → 2 → …
        ↓
audio_done = generation complete only
```

## KPI (mesures réelles)

Probe : LLM → chunker → Fish stream parts fed into `OrderedVoiceScheduler` (même règle que le frontend).  
3 tours valides (food×2, nature×1) avant HF_402. Voir `docs/latency-voice-early-play.json`.

| KPI | Avant | Après |
|-----|------:|------:|
| First audio received | ~3.5–6.7 s (backend) | inchangé |
| Playback start | = audio_done | = first chunk |
| Audio done | démarrait le player | génération seule |
| Receive → playback | **808.7 ms avg** (min 650 / max 1025) | **0.0 ms** |
| Play → audio_done | n/a (play après) | **808.7 ms** (player déjà lancé) |
| Total turn | — | TTFA audible −~0.8 s |

`started_before_done = true` sur les 3 tours valides.

## Comportement

- Ordre strict `seq 0 → 1 → 2` (buffer si désordre)
- `hasStartedPlayback` / early start dès ≥2048 bytes (1er chunk Fish)
- Web : MediaSource progressive append
- Native / sans MSE : play à `audio_done` de la séquence (toujours ordonné)
- Interrupt / nouvelle question : `resetVoiceStream()`

## Tests

- `pytest` : 79 passed (dont `test_voice_early_playback.py`)
- `tsc --noEmit` : OK
