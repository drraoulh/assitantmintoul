# Architecture — Cameroon AI Tour Guide

## Current flow (phase 2)

```
React Native (Expo)
        ↓  POST /api/chat
FastAPI
        ↓  AIService.generate_response()
OllamaAIService
        ↓  POST http://localhost:11434/api/chat
Ollama  →  Qwen (LLM_MODEL)
        ↓
FastAPI  →  mobile chat bubble
```

The mobile app never calls Ollama. Ollama stays on the developer machine.

## Provider independence

Routes depend only on `AIService`.

Switch models with environment variables, not code changes:

```env
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:4b
OLLAMA_BASE_URL=http://localhost:11434
```

`LLM_PROVIDER` also accepts the older alias `AI_PROVIDER`.
`LLM_MODEL` also accepts the older alias `OLLAMA_MODEL`.

## Conversation memory

`ConversationStore` is an interface.

Phase 2 uses `InMemoryConversationStore` (lost on restart, no login).
A later phase can persist the same `{role, content}` turns in PostgreSQL.

## Default model

`qwen3:4b` is the default because this project is developed on a 16 GB RAM
laptop with Intel UHD Graphics 620 (CPU inference only). `qwen3:8b` is a
valid upgrade when more RAM / a discrete GPU is available.

## Later phases (not implemented)

| Capability | Planned tool |
| --- | --- |
| RAG | FAISS and/or pgvector |
| STT | Whisper |
| TTS | Piper |
| Vision | Hugging Face vision model |
| Maps | OpenStreetMap |
