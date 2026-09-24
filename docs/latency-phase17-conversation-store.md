# Phase 1.7 — Optimisation SqlConversationStore

Bottleneck Phase 1.6 : ~2.7 s dans `SqlConversationStore` avant HF (deux sessions NullPool séquentielles vers Supabase pooler).

Modèle inchangé : `Qwen/Qwen3.5-9B:fastest`. RAG / TTS / frontend inchangés.

## Cause racine (mesurée)

Sur Supabase pooler, SQLAlchemy utilise `NullPool` → **chaque** `async with session` ouvre une nouvelle connexion TLS.

Avant Phase 1.7, le chemin voice faisait :

1. `start()` → session #1 (get/create conversation + commit) ≈ 1.2–1.3 s
2. `get_messages()` → session #2 (SELECT messages) ≈ 1.0–1.1 s

Même historique vide coûtait ~2.3 s. Dominant : **`db_connection_acquire`** (2×),
pas le SQL métier.

Cas mesuré (legacy bench) :
- total avg **2348.1 ms**
- acquire sum avg **1434.7 ms**
- history_load avg **211.4 ms**
- commit avg **350.9 ms**

→ **Cas D** (pool/TLS acquire) + **Cas C** (2 round-trips), pas une seule query de 2.5 s.

## Optimisations appliquées

1. **Lazy start** : nouveau thread (`conversation_id is None`) → **0 DB** avant LLM
2. **`prepare_for_generation`** : un seul round-trip pour un id existant (cold)
3. **SQL `LIMIT`** : `ORDER BY created_at DESC LIMIT n`
4. **Cache process-local** : multi-turn voice sur le même worker → **0 DB**
5. **`add_messages`** : user+assistant en **un** commit après le stream

## A. Timeline BEFORE (legacy, 2 sessions)

```
prepare_start                 +0 ms
session#1 connection_acquire  ~700–900 ms
conversation_get/create+commit  (reste du RTT #1)
session#2 connection_acquire  ~700–900 ms
messages_get_full             (reste du RTT #2)
TOTAL store before LLM        ~2348.1 ms
```

## B. Timeline AFTER (optimized)

### Nouveau thread (voice turn 1)

```
prepare_skip_db_new_thread    ~0 ms
TOTAL                        ~0.1 ms
```

### Thread existant cold (cache miss / autre worker)

```
session connection_acquire    ~1 RTT
messages_get LIMIT n
TOTAL                        ~1072.0 ms
```

### Thread existant cached (multi-turn même worker)

```
history_cache_hit             ~0 ms
TOTAL                        ~0.1 ms
```

## C. Tableau par opération

| Operation | Before | After new | After existing cold | After cached |
|-----------|-------:|----------:|--------------------:|-------------:|
| connection acquire | 1434.7 | — | 719.9 | — |
| conversation load | 210.7 | — | — | — |
| history load | 211.4 | — | 211.8 | — |
| commit (prepare) | 350.9 | — | — | — |
| **TOTAL before LLM** | **2348.1** | **0.1** | **1072.0** | **0.1** |

Persist batch (user+assistant, after stream) avg = 1489.9 ms (hors chemin critique TTFT).

## D. Voice end-to-end

| Metric | Before (Phase 1.6) | After (Phase 1.7) |
|--------|-------------------:|------------------:|
| store before LLM (new) | ~2369.8 | 0.0 |
| app TTFT (valid avg) | ~2826.7 | 796.5 |

### Voice runs

- `p17-1790247643` store=0.0 ms mode=prepare_no_db app_ttft=338.3 provider=308.0
- `p17-1790247646` store=0.0 ms mode=prepare_cache_hit app_ttft=1790.3 provider=279.6
- `p17-1790247650` store=0.0 ms mode=prepare_cache_hit app_ttft=261.0 provider=253.2

## E. Tests

`pytest -q` : 88 passed

## Verdict

BEFORE legacy avg=2348.1 ms. AFTER new-thread avg=0.1 ms ; existing-cold avg=1072.0 ms ; existing-cached avg=0.1 ms. Objectif <150 ms ATTEINT pour voice turn-1 (new thread). Objectif <150 ms ATTEINT pour multi-turn cached (même worker). Cold existing encore ~1× NullPool TLS — pool/infra P6 si besoin sans cache. Cause des ~2.7 s : 2× connection acquire NullPool, pas le SQL métier. Pas de changement Qwen/RAG/TTS.

## Index / pool notes

- Pool : `NullPool` sur `pooler.supabase.com` (pgbouncer) — inchangé volontairement.
- Index messages : `conversation_id` déjà indexé ; index composite `(conversation_id, created_at DESC)` possible en P6 pour cold path long (non créé ici sans preuve Sequential Scan).
