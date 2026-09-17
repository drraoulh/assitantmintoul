# Architecture — Cameroon AI Tour Guide

## Current flow

```
React Native (Expo)
        ↓  POST /api/chat | /speech/* | POST /api/vision/identify
FastAPI
        ↓  Local RAG (lexical) + optional web search
AIService (Hugging Face / Ollama / placeholder)
        ↓
Mobile chat (+ voice + photo)
```

## Chat / knowledge

- Default LLM: Hugging Face Inference Providers (`LLM_PROVIDER=huggingface`)
- Local RAG: curated files under `data/tourist_sites/` and `data/documents/`
- Live web enrichment: organic open-web results first (tourism sites, blogs,
  news, TripAdvisor, Facebook/Instagram pages that appear in search…), then
  Wikipedia + DuckDuckGo Instant Answer (`WEB_SEARCH_ENABLED=true`)

## Voice

- STT: Whisper via Hugging Face (`SPEECH_PROVIDER=huggingface`, `openai/whisper-large-v3-turbo`)
  or local faster-whisper (`SPEECH_PROVIDER=whisper`)
- TTS: Fish Audio (`TTS_PROVIDER=fish`, `s2.1-pro-free`) with `expo-speech` fallback
- Conversation screen: press-to-talk. Entering the mode only warms up the mic;
  recording starts on the first tap. The "Mains libres" pill chains the next
  turn automatically after the answer.
- Latency budget per voice turn: `mode=voice` on `POST /api/chat` caps the answer
  at `LLM_VOICE_MAX_TOKENS`, time-boxes web search
  (`VOICE_WEB_SEARCH_TIMEOUT_SECONDS`), and the mobile client synthesizes the
  reply sentence by sentence so playback starts before the whole text is ready.

## Vision

- Camera/gallery → `POST /api/vision/identify` → Google Gemini (`gemini-3.6-flash`)
- Description is then enriched by the chat/RAG guide reply

## Conversation history

- Port: `ConversationStore` (`start`, `get_messages`, `add_message`, `get_turns`,
  `list_conversations`, `delete`)
- `InMemoryConversationStore`: default, process-local, lost on restart
- `SqlConversationStore`: Supabase / Postgres via SQLAlchemy async, selected by
  `DATABASE_ENABLED=true`. Every call degrades to the in-memory store on
  `SQLAlchemyError`, so a database outage never breaks the chat.
- Tables: `conversations` (id, title, created_at, updated_at) and `messages`
  (conversation_id, role, content, created_at), created on startup
- HTTP: `GET /api/conversations`, `GET /api/conversations/{id}`,
  `DELETE /api/conversations/{id}`
- Mobile: last thread id in AsyncStorage, reopened on launch; the header clock
  opens the history sheet

## Knowledge base / RAG (Supabase + files + web)

- Curated tourism schema in Supabase: `places` (162+), `regions`, `cities`,
  `categories`, `cultural_topics`, `phrases`, `sources`, `place_images`
- Sync into `knowledge_chunks` with:
  `python -m scripts.sync_knowledge_base` (from `backend/`)
- RAG loads Supabase chunks first, then merges local `data/tourist_sites/**`
- Live web search stays enabled as a complement: organic open-web results
  (sites, blogs, news, TripAdvisor, Facebook/Instagram pages that appear in
  search…), plus Wikipedia / Instant Answer
- Prompt rule: prefer the curated KB, use the web for missing / recent context
- Site catalog (`GET /api/tourist-sites`) reads published Supabase places when
  `DATABASE_ENABLED=true`

## Design

- Palette from the Cameroon flag: green `#007A5E` for surfaces, yellow `#FCD116`
  for highlights, red `#CE1126` as accent (errors, quit, flag stripe)
- `mobile/constants/theme.ts` is the single source; `flagStripes` draws the
  three-colour rule under headers
