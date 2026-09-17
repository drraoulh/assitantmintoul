# Architecture — Cameroon AI Tour Guide

## Current flow (Hugging Face + knowledge base + web)

```
React Native (Expo)
        ↓  POST /api/chat
FastAPI
        ↓  AIService.generate_response()
HuggingFaceAIService
        ├─ LocalRAGService  ←  data/tourist_sites + data/documents
        ├─ CompositeWebSearchService  ←  Wikipedia + DuckDuckGo
        ↓  grounded system prompt
        ↓  POST https://router.huggingface.co/v1/chat/completions
Hugging Face Inference Providers  →  Qwen (HF_MODEL_ID)
        ↓
FastAPI  →  mobile chat bubble
```

The mobile app never calls Hugging Face directly. Only FastAPI holds the token.

## Provider independence

Routes depend only on `AIService`.

Default:

```env
LLM_PROVIDER=huggingface
HF_MODEL_ID=Qwen/Qwen2.5-7B-Instruct
HF_API_BASE_URL=https://router.huggingface.co/v1
HUGGINGFACE_HUB_TOKEN=hf_xxx
```

`LLM_PROVIDER=ollama` remains available as an optional local fallback.

## Knowledge base / RAG

`RAGService` loads curated JSON sites and Markdown documents from `data/`.

`LocalRAGService` scores passages with lightweight TF-IDF (no embedding download).
A later upgrade can call Hugging Face embeddings for dense retrieval.

```env
RAG_ENABLED=true
RAG_TOP_K=6
```

## Live web search

`WebSearchService` enriches answers with public web snippets:

- French / English Wikipedia extracts
- DuckDuckGo Instant Answer API

```env
WEB_SEARCH_ENABLED=true
WEB_SEARCH_MAX_RESULTS=4
```

Curated KB excerpts are preferred over web snippets when both cover the same place.

## Conversation memory

`InMemoryConversationStore` (lost on restart). PostgreSQL persistence comes later.

## Later phases

| Capability | Planned tool |
| --- | --- |
| Dense RAG | HF embedding endpoint + FAISS / pgvector |
| STT | Whisper (HF) |
| TTS | Piper / HF TTS |
| Vision | HF vision model |
| Maps | OpenStreetMap |
