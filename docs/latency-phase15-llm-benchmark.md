# Phase 1.5 — LLM latency benchmark

Isolated Hugging Face Inference Providers comparison. **Production model unchanged** (`Qwen/Qwen3.5-9B:fastest`).

## Setup

| Item | Value |
|------|-------|
| Provider | `https://router.huggingface.co/v1` |
| Script | `backend/scripts/benchmark_llm_latency.py` |
| Params | temperature=`0.45`, max_tokens=`140` (voice), `stream=True`, `brief` grounding |
| Fairness | Same system prompt + RAG chunks per question for every model (grounded once, reused) |
| Questions | food / nature / Yaoundé / culture / 3-day trip (no « Bonjour ») |
| Target | 3–5 valid runs per model×question |

### Models chosen (provider-real, not popularity)

From `GET /models` on this account + chat suitability (FR / multilingual / short context / streaming):

| Model | Why |
|-------|-----|
| `Qwen/Qwen3.5-9B:fastest` | Production baseline |
| `meta-llama/Llama-3.1-8B-Instruct:fastest` | Same router catalog; multilingual instruct; previously returned HTTP 200 |
| `google/gemma-3-4b-it:fastest` | Smaller instruct model on catalog (latency candidate) |
| `Qwen/Qwen3-4B-Instruct-2507:fastest` | Smaller Qwen instruct on catalog (latency candidate) |

Models returning « not supported by any provider » were excluded (e.g. Qwen2.5-7B, Phi-3.5, Gemma-2).

---

## Formal matrix (protocol run)

Credits depleted mid-session → most protocol cells are **FAILED — HTTP 402**. No invented TTFT.

| Model | Valid runs | TTFT avg | TTFT median | First phrase avg | Generation avg | Errors |
|-------|-----------:|---------:|------------:|-----------------:|---------------:|--------|
| `Qwen/Qwen3.5-9B:fastest` | 0* | — | — | — | — | FAILED — HTTP 402 |
| `meta-llama/Llama-3.1-8B-Instruct:fastest` | 0* | — | — | — | — | FAILED — HTTP 402 |
| `google/gemma-3-4b-it:fastest` | 0 | — | — | — | — | FAILED — HTTP 402 |
| `Qwen/Qwen3-4B-Instruct-2507:fastest` | 0 | — | — | — | — | FAILED — HTTP 402 |

\*See opportunistic valid runs below (credits flickered; not a full 3×5 matrix).

Artifacts: `docs/latency-phase15-llm-benchmark.json`

---

## Opportunistic valid streaming runs (real measurements)

When credits briefly returned, identical grounded prompts were streamed via production `HuggingFaceAIService._stream_tokens`.

Source: `docs/latency-phase15-opportunistic.json` + one earlier Yaoundé pair.

### Latency summary

| Model | Valid n | TTFT avg | TTFT median | TTFT min–max | First phrase avg | Generation avg |
|-------|--------:|---------:|------------:|-------------:|-----------------:|---------------:|
| `Qwen/Qwen3.5-9B:fastest` | **4** | **440** | 282 | 246–709 | **548** | **1423** |
| `meta-llama/Llama-3.1-8B-Instruct:fastest` | **2** | **768** | 769 | 734–803 | **854** | **1230** |
| `google/gemma-3-4b-it:fastest` | 0 | — | — | — | — | FAILED 402 |
| `Qwen/Qwen3-4B-Instruct-2507:fastest` | 0 | — | — | — | — | FAILED 402 |

Qwen n=4 = 3 Yaoundé opportunistic + 1 earlier Yaoundé sample (523 / 800 / 2313).  
Llama n=2 = 1 opportunistic + 1 earlier sample.

### Cold vs warm (Qwen only — enough samples)

| | n | TTFT avg |
|--|--:|---------:|
| Cold | 1 | 709 ms |
| Warm | 2 | **264 ms** |

Warm TTFT ≈ Phase 1.2 / 1.3 reported ~245 ms. The ~2.7 s `llm_start → first_token` wall clock in voice turns is **mostly pre-LLM** (RAG/routing already ~ms) + **provider queue / cold start**, not model decode alone.

### Qualitative (1–5 heuristic, same rules; valid replies only)

| Model | Groundedness | Relevance | Correctness | French | Voice brevity | Cameroon |
|-------|-------------:|----------:|------------:|-------:|--------------:|---------:|
| Qwen 3.5-9B | 4–5 | 4–5 | 3* | 5 | 4–5 | 5 |
| Llama 3.1-8B | 4–5 | 4–5 | 3* | 4–5 | 4–5 | 5 |
| Gemma 3-4B | — | — | — | — | — | no replies |
| Qwen 3-4B | — | — | — | — | — | no replies |

\*Correctness not independently fact-checked; neutral 3 unless off-topic.

Both Qwen and Llama cited Place de l’Indépendance / artisanat for Yaoundé (aligned with KB). Llama punctuation/capitalization slightly less natural (`Place De L'indépendance`).

---

## Errors observed

| Code | Meaning |
|------|---------|
| HTTP 402 | Credits depleted on Inference Providers (dominant blocker) |
| Probe 200 then stream 402 | Non-stream ping can succeed while streaming chat completions fail — benchmark uses **stream=True** like production |

---

## Conclusion (decision input for Phase 1.6 — no prod swap)

1. **No model change recommended yet.** Formal 3×5 matrix incomplete (402).
2. On the **real stream samples we do have**, `meta-llama/Llama-3.1-8B-Instruct:fastest` did **not** reduce TTFT vs Qwen:
   - Qwen warm TTFT ≈ **246–282 ms**
   - Llama samples ≈ **734–803 ms** (**slower** first token)
3. Llama sometimes finished the full short answer sooner (lower `total_generation_ms` on one sample) but that does **not** help voice TTFA, which is gated on first phrase / first audio.
4. Gemma-3-4B and Qwen3-4B-Instruct were **unavailable under credit limits** this session — re-test when credits restored.
5. Gain needed to justify a swap: clearly lower **warm + cold** `wall_to_first_token_ms` and `time_to_first_phrase_ms` with quality ≥ current Qwen. **Not demonstrated here.**

### Re-run when credits available

```bash
python backend/scripts/benchmark_llm_latency.py --runs 5
```

Production `HF_MODEL_ID` must stay `Qwen/Qwen3.5-9B:fastest` until Phase 1.6 explicitly decides otherwise.

---

## Notes

- Greeting cache bypassed (no « Bonjour »).
- Grounding/RAG computed once per question and reused.
- HTTP 402/404/429 recorded as FAILED — never estimated.
- `pytest -q` : 83 passed (includes `test_benchmark_llm_latency.py`).
