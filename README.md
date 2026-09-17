# Cameroon AI Tour Guide

Intelligent tourist assistant dedicated to Cameroon.

Phase 3 adds a **local tourism knowledge base** and lightweight RAG.
Retrieved excerpts are injected into the system prompt before Ollama generates an answer.

```
React Native → FastAPI /api/chat → AIService → RAG (local data) → Ollama → Qwen → FastAPI → React Native
```

## Default model

**`qwen3:4b`** (Qwen 3, 4 billion parameters, Hugging Face family, served by Ollama).

Why not `qwen3:8b` by default? This project is aimed at a student laptop. The current development machine has about 16 GB of RAM and Intel UHD Graphics 620, so inference is CPU-only. `qwen3:8b` (~5.2 GB) can run, but it is slow and leaves little RAM for Windows, Expo, and FastAPI. `qwen3:4b` (~2.5 GB) is still a current Qwen 3 instruction model, handles French and English, and is a better MVP default.

To use the larger model later:

```env
LLM_MODEL=qwen3:8b
```

The model name is only in environment variables, not hard-coded in routes.

## What this phase includes

- Conversational Expo chat UI
- `POST /api/chat` unchanged from the mobile side
- `AIService` abstraction with a real Ollama implementation
- In-memory multi-turn conversation history (replaceable later with PostgreSQL)
- Curated Cameroon tourism knowledge base under `data/`
- Local lexical RAG (`LocalRAGService`) that grounds answers in those files
- System prompt that prefers retrieved excerpts and stays honest about missing live data
- HTTP errors when Ollama is down, the model is missing, or generation times out
- Backend tests for chat success, empty messages, AI failures, and RAG retrieval

## What this phase does not include

Dense embeddings / FAISS, Whisper, TTS playback, computer vision, GPS, maps, authentication, payments, and cloud deployment. Microphone and camera buttons remain placeholders.

## Folder structure

```text
.
├── mobile/                 Expo application
├── backend/                FastAPI application
│   ├── app/services/ai/    AIService, Ollama adapter, prompts
│   ├── app/services/rag/   Local knowledge retrieval (lexical TF-IDF)
│   ├── app/services/tourism/
│   ├── app/services/conversation/   in-memory history
│   └── tests/
├── data/
│   ├── documents/          Markdown tourism guides
│   └── tourist_sites/      Curated site JSON by region
├── docs/
├── docker-compose.yml
├── .env.example
└── README.md
```

## Prerequisites

- Windows 10/11
- Python 3.11+
- Node.js 20+
- Git
- PowerShell
- [Ollama](https://ollama.com/download/windows)
- Expo Go on a phone, an Android emulator, or Expo web

## 1. Environment files

```powershell
cd "C:\Users\hp\git\assitant mintoul"
Copy-Item .env.example .env
Copy-Item .env.example backend\.env
Copy-Item mobile\.env.example mobile\.env
```

Keep `LLM_PROVIDER=ollama` and `DATABASE_ENABLED=false`.

## 2. Install Ollama and pull the model

Download and install: https://ollama.com/download/windows

Then in PowerShell:

```powershell
ollama --version
ollama pull qwen3:4b
```

Ollama usually starts in the background on Windows. Verify:

```powershell
curl http://127.0.0.1:11434/api/tags
```

### Test Ollama by itself (before FastAPI)

```powershell
ollama run qwen3:4b "En une phrase, présente le Cameroun à un voyageur."
```

Or:

```powershell
curl http://127.0.0.1:11434/api/chat -Method POST -ContentType "application/json" -Body '{"model":"qwen3:4b","messages":[{"role":"user","content":"Bonjour"}],"stream":false,"think":false}'
```

You should see a JSON payload with `message.content`. If this fails, do not start the mobile app yet.

## 3. Install backend dependencies

```powershell
cd "C:\Users\hp\git\assitant mintoul\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks script activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Run tests:

```powershell
pytest
```

## 4. Start the backend

```powershell
cd "C:\Users\hp\git\assitant mintoul\backend"
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` is required so a physical phone on the same Wi-Fi can reach the PC.

Health:

```powershell
curl http://127.0.0.1:8000/api/health
```

Chat through FastAPI (not Ollama directly from the phone):

```powershell
curl http://127.0.0.1:8000/api/chat -Method POST -ContentType "application/json" -Body '{"message":"Bonjour"}'
```

Docs: http://127.0.0.1:8000/docs

## 5. Start the mobile app

Second PowerShell window:

```powershell
cd "C:\Users\hp\git\assitant mintoul\mobile"
npm install
npm start
```

Then press `w` (web), `a` (Android emulator), or scan the QR code with Expo Go.

## Networking: phone vs localhost

`http://localhost:8000` on a physical phone is the **phone**, not the Windows PC.

The app reads `EXPO_PUBLIC_API_URL` from `mobile/.env`. If that is empty, it tries the Expo LAN IP automatically.

| Client | `EXPO_PUBLIC_API_URL` |
| --- | --- |
| Expo web / Windows | `http://127.0.0.1:8000` |
| Android emulator | `http://10.0.2.2:8000` |
| Physical phone | `http://YOUR_PC_LAN_IP:8000` |

Find the PC address:

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.PrefixOrigin -ne "WellKnown" } | Select-Object IPAddress, InterfaceAlias
```

Example (do not copy this IP; use yours):

```env
EXPO_PUBLIC_API_URL=http://192.168.1.24:8000
```

Restart Expo after changing `mobile/.env`. Allow inbound TCP **8000** in Windows Firewall. Do **not** open Ollama port **11434** to the network.

## How to test the full chat

1. Ollama is running and `qwen3:4b` is pulled.
2. FastAPI is running on port 8000.
3. Open the app. Header shows **Connecté**.
4. Type `Bonjour` and send.
5. You should see **Cameroon Guide is thinking...**, then a real Qwen reply.
6. Send `Je suis à Yaoundé.` then `Que puis-je visiter ?` — the second answer should use Yaoundé from context.

## Troubleshooting Ollama

| Symptom | What to do |
| --- | --- |
| `Ollama is not running or cannot be reached` | Start Ollama from the Start menu, then `curl http://127.0.0.1:11434/api/tags` |
| `The model 'qwen3:4b' is not installed` | `ollama pull qwen3:4b` |
| `took too long to respond` | Wait for first-load (model loads into RAM). Try `LLM_MODEL=qwen3:4b`. Increase `OLLAMA_TIMEOUT_SECONDS`. Close other heavy apps. |
| Phone header **Hors ligne** | Wrong API URL. Use the PC LAN IP, not `localhost`. |
| Reply invents precise prices | Knowledge base has no live prices. The prompt forbids presenting guesses as facts. |
| Very slow answers | CPU-only Intel graphics. Stay on `qwen3:4b`, or use a machine with a discrete GPU for `qwen3:8b`. |
| Answers ignore local sites | Confirm `RAG_ENABLED=true` and that `data/tourist_sites` / `data/documents` are present. |

## Knowledge base (RAG)

Curated files live in:

- `data/tourist_sites/*.json` — sites with FR/EN summaries and tips
- `data/documents/*.md` — regional overview, practical tips, food & culture

At chat time, `LocalRAGService` retrieves the top `RAG_TOP_K` passages (lexical TF-IDF, bilingual aliases) and `OllamaAIService` appends them to the system prompt. No embedding model download is required for this MVP.

Toggle:

```env
RAG_ENABLED=true
RAG_TOP_K=4
RAG_DATA_DIR=
```

To enrich the assistant later, add JSON sites or Markdown sections under `data/` — they are picked up on the next backend process start (RAG service is cached at import/startup).

## Optional PostgreSQL

```powershell
docker compose up -d
```

Then set `DATABASE_ENABLED=true`. Chat history is still in-memory in this phase.

## Files to inspect first

1. `backend/app/api/chat.py` — HTTP route (no Ollama calls)
2. `backend/app/services/ai/base.py` — `AIService`
3. `backend/app/services/ai/ollama.py` — Ollama adapter + RAG grounding
4. `backend/app/services/ai/factory.py` — provider switch
5. `backend/app/services/ai/prompts.py` — system prompt
6. `backend/app/services/rag/local.py` — lexical knowledge retrieval
7. `backend/app/services/conversation/memory.py` — in-memory threads
8. `data/tourist_sites/` / `data/documents/` — curated knowledge base
9. `mobile/services/api.ts` — FastAPI client
10. `mobile/constants/config.ts` — API base URL
11. `.env.example` — `LLM_PROVIDER` / `LLM_MODEL` / `RAG_*`
