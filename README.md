# Cameroon AI Tour Guide

Intelligent tourist assistant dedicated to Cameroon.

The stack is **Hugging Face first**: FastAPI calls Hugging Face Inference Providers for chat,
grounds answers in a **rich local Cameroon knowledge base**, and can enrich them with
**live web search** (Wikipedia + DuckDuckGo).

```
React Native → FastAPI /api/chat → HuggingFaceAIService
                 ├─ LocalRAG (data/)
                 ├─ Web search (Wikipedia / DuckDuckGo)
                 └─ HF Inference Providers → Qwen → mobile
```

## Default model

**`Qwen/Qwen2.5-7B-Instruct`** via Hugging Face Inference Providers
(`https://router.huggingface.co/v1/chat/completions`).

Set your token (Inference Providers permission):

```env
LLM_PROVIDER=huggingface
HF_MODEL_ID=Qwen/Qwen2.5-7B-Instruct
HUGGINGFACE_HUB_TOKEN=hf_your_token
```

Optional local fallback: `LLM_PROVIDER=ollama` with a pulled Ollama model.

## What this phase includes

- Conversational Expo chat UI
- `POST /api/chat` unchanged from the mobile side
- **Hugging Face** chat adapter (primary) + optional Ollama adapter
- Rich curated Cameroon tourism knowledge base under `data/`
- Local lexical RAG + live web search injected into the system prompt
- In-memory multi-turn conversation history
- Backend tests for chat, HF errors, RAG, and web-search merging

## What this phase does not include

Dense embeddings / FAISS, Whisper, TTS playback, computer vision, GPS, maps, authentication, payments, and cloud deployment. Microphone and camera buttons remain placeholders.

## Folder structure

```text
.
├── mobile/                 Expo application
├── backend/                FastAPI application
│   ├── app/services/ai/    Hugging Face + grounding + prompts
│   ├── app/services/rag/   Local knowledge retrieval
│   ├── app/services/search/  Wikipedia + DuckDuckGo
│   ├── app/services/firebase/ Firestore knowledge store + seed
│   ├── app/services/tourism/
│   ├── app/services/conversation/
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

- Windows 10/11 (or Linux/macOS)
- Python 3.11+
- Node.js 20+
- Git
- A Hugging Face account + access token with **Inference Providers** permission
- Expo Go on a phone, an Android emulator, or Expo web

## 1. Environment files

```powershell
cd "C:\Users\hp\git\assitant mintoul"
Copy-Item .env.example .env
Copy-Item .env.example backend\.env
Copy-Item mobile\.env.example mobile\.env
```

Keep `LLM_PROVIDER=huggingface`, set `HUGGINGFACE_HUB_TOKEN`, and `DATABASE_ENABLED=false`.

## 2. Hugging Face token

1. Create a token: https://huggingface.co/settings/tokens
2. Enable **Inference Providers** / make inference calls permission
3. Put it in `.env`:

```env
HUGGINGFACE_HUB_TOKEN=hf_...
```

### Optional: test the router directly

```powershell
curl https://router.huggingface.co/v1/chat/completions -Method POST -Headers @{Authorization="Bearer $env:HUGGINGFACE_HUB_TOKEN"; "Content-Type"="application/json"} -Body '{"model":"Qwen/Qwen2.5-7B-Instruct","messages":[{"role":"user","content":"Bonjour"}],"stream":false}'
```

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

Chat through FastAPI:

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

1. `HUGGINGFACE_HUB_TOKEN` is set and Inference Providers work.
2. FastAPI is running on port 8000.
3. Open the app. Header shows **Connecté**.
4. Type `Bonjour` and send.
5. Ask `Que voir à Kribi ?` — answer should use local KB (and optionally web) context.
6. Send `Je suis à Yaoundé.` then `Que puis-je visiter ?` — the second answer should use Yaoundé from context.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| `Hugging Face token missing or invalid` | Set `HUGGINGFACE_HUB_TOKEN` with Inference Providers permission |
| HF 503 / busy | Retry; or try another `HF_MODEL_ID` available on the router |
| Phone header **Hors ligne** | Wrong API URL. Use the PC LAN IP, not `localhost`. |
| Reply invents precise prices | KB/web have no live prices. Prompt forbids presenting guesses as facts. |
| Answers ignore local sites | Confirm `RAG_ENABLED=true` and `data/` files are present. |
| No web enrichment | Confirm `WEB_SEARCH_ENABLED=true` and network access to Wikipedia / DuckDuckGo. |

## Knowledge base (RAG) + web search

Curated files live in:

- `data/tourist_sites/*.json` — sites with FR/EN summaries and tips (all regions, parks, culture)
- `data/documents/*.md` — history, transport, parks, climate, safety, food, crafts, etiquette

At chat time:

1. `LocalRAGService` retrieves top `RAG_TOP_K` local passages
2. `CompositeWebSearchService` fetches up to `WEB_SEARCH_MAX_RESULTS` public web hits
3. `HuggingFaceAIService` appends both to the system prompt

```env
RAG_ENABLED=true
RAG_TOP_K=6
WEB_SEARCH_ENABLED=true
WEB_SEARCH_MAX_RESULTS=4
```

To enrich the assistant, add JSON sites or Markdown sections under `data/` and restart the backend.

## Firebase (base cloud)

La base cloud prévue est **Firebase Firestore**. Les fichiers `data/` restent la graine locale.

```env
FIREBASE_ENABLED=false
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CREDENTIALS_FILE=C:\path\to\serviceAccount.json
```

Quand le projet Firebase est prêt :

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
$env:FIREBASE_ENABLED="true"
$env:FIREBASE_PROJECT_ID="your-project-id"
$env:FIREBASE_CREDENTIALS_FILE="C:\path\to\serviceAccount.json"
python -m app.services.firebase.cli_seed
```

Modèle de collections : `data/documents/firebase_data_model.md`.

## Optional PostgreSQL

```powershell
docker compose up -d
```

Then set `DATABASE_ENABLED=true`. Chat history is still in-memory in this phase.

## Files to inspect first

1. `backend/app/api/chat.py` — HTTP route
2. `backend/app/services/ai/huggingface.py` — Hugging Face Inference Providers adapter
3. `backend/app/services/ai/grounding.py` — RAG + web prompt assembly
4. `backend/app/services/rag/local.py` — lexical knowledge retrieval
5. `backend/app/services/search/` — Wikipedia + DuckDuckGo
6. `data/tourist_sites/` / `data/documents/` — curated knowledge base
7. `mobile/services/api.ts` — FastAPI client
8. `.env.example` — `LLM_PROVIDER` / `HF_*` / `RAG_*` / `WEB_SEARCH_*`
