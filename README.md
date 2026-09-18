# Smartmboa Tour

Intelligent tourist assistant dedicated to Cameroon.

Phase 3 adds a **curated Cameroon tourism knowledge base** and **RAG** (embeddings + FAISS).
The LLM is no longer the primary source of site facts.

```
React Native → FastAPI /api/chat → RAG (FAISS) → AIService → Ollama/Qwen or placeholder → Mobile
```

## How to launch the app and see the UI

You need **two PowerShell windows**. The chat screen is the main interface.

**1. Backend**

```powershell
cd "C:\Users\hp\git\assitant mintoul\backend"
.\.venv\Scripts\Activate.ps1
python -m scripts.build_knowledge_base
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs (interface backend): http://127.0.0.1:8000/docs

**2. Mobile UI**

```powershell
cd "C:\Users\hp\git\assitant mintoul\mobile"
npm start
```

Then:

- press **`w`** to open the chat in the **browser**
- or scan the QR code with **Expo Go** on your phone
- or press **`a`** for Android emulator

The screen you should see: header **Smartmboa Tour**, welcome card, suggested prompts, text field, mic, camera, send.

Without Ollama, set `LLM_PROVIDER=placeholder` in `backend/.env` so answers quote the knowledge base instead of returning 503.

On a phone, `localhost` is the phone. Use `EXPO_PUBLIC_API_URL=http://YOUR_PC_LAN_IP:8000` in `mobile/.env`.

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
- System prompt for Cameroon tourism, with explicit “no RAG yet” honesty
- HTTP errors when Ollama is down, the model is missing, or generation times out
- Backend tests for chat success, empty messages, and AI failures
- Curated tourism JSON (20 sites), FAISS/NumPy RAG, `GET /api/tourist-sites`

## What this phase does not include

TTS uses **Fish Audio** (`s2.1-pro-free`) via `POST /api/speech/synthesize` when `TTS_PROVIDER=fish` and `FISH_AUDIO_API_KEY` are set; otherwise the app falls back to on-device `expo-speech`. Photo recognition uses **Google Gemini** (`gemini-3.6-flash`) via `POST /api/vision/identify` when `VISION_PROVIDER=gemini` and `GEMINI_API_KEY` are set. GPS maps, authentication, payments, and cloud deployment remain later phases. Microphone STT uses Whisper on Hugging Face Inference (`openai/whisper-large-v3-turbo` with `SPEECH_PROVIDER=huggingface` + `HUGGINGFACE_HUB_TOKEN`), or local `faster-whisper` with `SPEECH_PROVIDER=whisper`.

## Folder structure

```text
.
├── mobile/                 Expo application
├── backend/                FastAPI application
│   ├── app/services/ai/    AIService, Ollama adapter, prompts
│   ├── app/services/conversation/   in-memory history
│   └── tests/
├── data/
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

Voice conversation is press-to-talk: opening the mode only prepares the microphone, and recording starts when you tap the orb. Tap again to send, or enable the “Mains libres” pill to chain turns automatically. Voice turns post `mode=voice` to `/api/chat`, which caps the answer length (`LLM_VOICE_MAX_TOKENS`) and time-boxes web search (`VOICE_WEB_SEARCH_TIMEOUT_SECONDS`) to keep replies fast.

For natural voice replies, set `FISH_AUDIO_API_KEY` (free key at https://fish.audio/app/api-keys/) with `TTS_PROVIDER=fish`. Without it, the app keeps using on-device `expo-speech`. STT already uses `SPEECH_PROVIDER=huggingface` + `HUGGINGFACE_HUB_TOKEN` and Whisper `openai/whisper-large-v3-turbo`.

For photo recognition, set `GEMINI_API_KEY` (https://aistudio.google.com/apikey) with `VISION_PROVIDER=gemini`.

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
5. You should see **Smartmboa Tour réfléchit...**, then a real Qwen reply.
6. Send `Je suis à Yaoundé.` then `Que puis-je visiter ?` — the second answer should use Yaoundé from context.

## Troubleshooting Ollama

| Symptom | What to do |
| --- | --- |
| `Ollama is not running or cannot be reached` | Start Ollama from the Start menu, then `curl http://127.0.0.1:11434/api/tags` |
| `The model 'qwen3:4b' is not installed` | `ollama pull qwen3:4b` |
| `took too long to respond` | Wait for first-load (model loads into RAM). Try `LLM_MODEL=qwen3:4b`. Increase `OLLAMA_TIMEOUT_SECONDS`. Close other heavy apps. |
| Phone header **Hors ligne** | Wrong API URL. Use the PC LAN IP, not `localhost`. |
| Reply invents precise prices | Those fields are `null` in the knowledge base. Rebuild RAG if the model ignores context. |
| Very slow answers | CPU-only Intel graphics. Stay on `qwen3:4b`, or use a machine with a discrete GPU for `qwen3:8b`. |

## Conversation history (Supabase or local Postgres)

Without a database the app still works: threads live in memory and vanish when the backend restarts. To keep them, point `DATABASE_URL` at a Postgres instance and set `DATABASE_ENABLED=true`. Tables (`conversations`, `messages`) are created on the first boot.

**Supabase** (recommended, free tier):

1. Create a project on [supabase.com](https://supabase.com), then open **Project Settings → Database → Connection string → URI**.
2. Copy the URI, replace `postgresql://` with `postgresql+asyncpg://`, and paste your database password.
3. Put it in `.env` **and** `backend/.env`:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.YOUR_REF.supabase.co:5432/postgres
DATABASE_ENABLED=true
```

If your network blocks IPv6, use the pooler URI instead (port `6543`); the backend detects it and disables prepared statement caching, which pgbouncer rejects. TLS is enabled automatically for any non-local host.

**Local Postgres** instead:

```powershell
docker compose up -d
```

The mobile app remembers the open thread, reopens it on launch, and the clock icon in the header lists past conversations (open, or delete). Endpoints: `GET /api/conversations`, `GET /api/conversations/{id}`, `DELETE /api/conversations/{id}`. If the database becomes unreachable while running, the chat keeps answering and falls back to in-memory history instead of failing.

## Rebuild the knowledge base

Sync the curated Supabase tourism tables (`places`, culture, phrases…) into
`knowledge_chunks` and refresh the RAG index used by chat:

```powershell
cd "C:\Users\hp\git\assitant mintoul\backend"
.\.venv\Scripts\Activate.ps1
python -m scripts.sync_knowledge_base
```

Optional FAISS rebuild from local JSON only:

```powershell
python -m scripts.build_knowledge_base
```

The assistant always prefers this curated Cameroon knowledge, and still runs
Wikipedia + DuckDuckGo web search as a complement when useful.

How to add local JSON sites: `data/tourist_sites/README.md`

## Files to inspect first

1. `backend/app/api/chat.py` — HTTP route (no Ollama calls)
2. `backend/app/services/ai/base.py` — `AIService`
3. `backend/app/services/ai/ollama.py` — Ollama adapter
4. `backend/app/services/ai/factory.py` — provider switch
5. `backend/app/services/ai/prompts.py` — system prompt
6. `backend/app/services/conversation/memory.py` — in-memory threads
7. `mobile/services/api.ts` — FastAPI client
8. `mobile/constants/config.ts` — API base URL
9. `.env.example` — `LLM_PROVIDER` / `LLM_MODEL`
