# Architecture — Cameroon AI Tour Guide

## Current flow (phase 3)

```
React Native (Expo)
        ↓  POST /api/chat
FastAPI
        ↓  AIService.generate_response()
OllamaAIService
        ↓  RAGService.retrieve_chunks(query)
LocalRAGService  ←  data/tourist_sites + data/documents
        ↓  grounded system prompt
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

## Knowledge base / RAG

`RAGService` is an interface.

Phase 3 uses `LocalRAGService`:

- Loads curated JSON sites and Markdown documents from `data/`
- Scores passages with lightweight TF-IDF (no embedding download)
- Injects the top `RAG_TOP_K` excerpts into the system prompt

```env
RAG_ENABLED=true
RAG_TOP_K=4
RAG_DATA_DIR=
```

`LocalTourismService` reads the same site JSON for structured city lookups / simple itineraries.

A later phase can replace lexical retrieval with open-source embeddings + FAISS or pgvector without changing the chat route.

## Conversation memory

`ConversationStore` is an interface.

Phase 2/3 uses `InMemoryConversationStore` (lost on restart, no login).
A later phase can persist the same `{role, content}` turns in PostgreSQL.

## Default model

`qwen3:4b` is the default because this project is developed on a 16 GB RAM
laptop with Intel UHD Graphics 620 (CPU inference only). `qwen3:8b` is a
valid upgrade when more RAM / a discrete GPU is available.

## Later phases (not implemented)

| Capability | Planned tool |
| --- | --- |
| Dense RAG | sentence-transformers + FAISS and/or pgvector |
| STT | Whisper |
| TTS | Piper |
| Vision | Hugging Face vision model |
| Maps | OpenStreetMap |
