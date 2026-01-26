# Tamor Architecture Overview

This document explains how Tamor is structured and the key design decisions.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        UI (React)                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │LeftPanel │  │ChatPanel │  │RightPanel│  │FocusMode │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP/JSON
┌─────────────────────────▼───────────────────────────────────┐
│                    API (Flask/Gunicorn)                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │  Chat   │  │ Library │  │  Refs   │  │ Memory  │       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      Services Layer                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │  LLM    │  │Epistemic│  │ Router  │  │Embedding│       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    Data Layer (SQLite)                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ conversations │ messages │ library_files │ memories │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## UI Layer (React + Vite)

### Core Components

| Component | Purpose |
|-----------|---------|
| `LeftPanel` | Project/conversation navigation |
| `ChatPanel` | Main chat interface |
| `RightPanel` | Tabbed tools (Library, References, Memory, etc.) |
| `FocusMode` | Distraction-free voice-first interface |
| `Settings` | User preferences |

### Key Principles

- **UI does not invent state** — all truth comes from API
- **Responsive by design** — Mobile, Tablet, Desktop breakpoints
- **Developer mode** — Advanced panels hidden by default

---

## API Layer (Flask)

### Route Organization

| Blueprint | Endpoints | Purpose |
|-----------|-----------|---------|
| `chat_api` | `/api/chat` | Main conversation endpoint |
| `projects_api` | `/api/projects/*` | Project CRUD |
| `files_api` | `/api/files/*` | File management |
| `library_api` | `/api/library/*` | Global library system |
| `references_api` | `/api/references/*` | Scripture references |
| `memory_api` | `/api/memory/*` | Long-term memory |
| `system_api` | `/api/status`, `/api/health` | System diagnostics |

### Request Flow

```
User message
    ↓
Router (intent classification)
    ↓
Agent selection (Researcher/Writer/Engineer/Archivist)
    ↓
Context injection (memory, library, references)
    ↓
LLM call
    ↓
Epistemic processing (classify, lint, anchor, repair)
    ↓
Response with metadata
```

---

## Services Layer

### Core Services

| Service | Purpose |
|---------|---------|
| `llm_service` | LLM provider abstraction (OpenAI) |
| `router` | Intent-based agent routing |
| `embedding_service` | Local sentence-transformers |
| `epistemic/pipeline` | Truth signaling system |

### Library Services

| Service | Purpose |
|---------|---------|
| `library_service` | File CRUD and deduplication |
| `library_search_service` | Semantic search |
| `library_context_service` | Chat context injection |

### Reference Services

| Service | Purpose |
|---------|---------|
| `sword_client` | Local Bible modules |
| `sefaria_client` | Jewish text API with caching |
| `reference_service` | Unified reference interface |

---

## Data Layer (SQLite)

### Core Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts |
| `projects` | Project containers |
| `project_files` | Files within projects |
| `conversations` | Chat sessions |
| `messages` | Individual messages |
| `memories` | Long-term memory entries |
| `detected_tasks` | Task/reminder tracking |

### Library Tables

| Table | Purpose |
|-------|---------|
| `library_files` | Global document store |
| `library_chunks` | Embedded text segments |
| `project_library_refs` | Project-to-library links |

### Location

Single database at: `api/memory/tamor.db`

---

## External Dependencies

| Dependency | Purpose | Local/Remote |
|------------|---------|--------------|
| OpenAI API | LLM responses | Remote |
| sentence-transformers | Embeddings | Local |
| SWORD modules | Bible texts | Local |
| Sefaria API | Jewish texts | Remote (cached) |
| faster-whisper | Transcription | Local |

---

## Configuration

| File | Purpose |
|------|---------|
| `.env` | Environment variables, API keys |
| `config/modes.yml` | Assistant mode definitions |
| `config/personality.yml` | Tamor's identity |
| `config/epistemic_rules.yml` | Truth signaling rules |

---

## Deployment

- **Server**: Gunicorn with Flask
- **Frontend**: Vite dev server or static build
- **Access**: Cloudflare Tunnel for HTTPS
- **Storage**: Local SQLite + optional NAS mount for library

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| SQLite over Postgres | Single-user, zero config, file-based |
| Local embeddings | No API cost, works offline |
| Flask over FastAPI | Simplicity, sufficient for workload |
| Cloudflare Tunnel | Secure access without port exposure |

---

*Last updated: Phase 8.6 (v1.32)*
