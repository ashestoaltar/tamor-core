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
| `llm_service` | Multi-provider LLM abstraction (xAI, Anthropic, Ollama) |
| `router` | Intent-based agent routing with provider selection |
| `embedding_service` | Local sentence-transformers |
| `epistemic/pipeline` | Truth signaling system |

### Library Services

| Service | Purpose |
|---------|---------|
| `library_service` | File CRUD and deduplication |
| `library_search_service` | Semantic search across 27K+ chunks |
| `library_context_service` | Chat context injection |

### Library Integration with Agents

The library is the primary knowledge source for research queries. The integration flow:

```
User question
    ↓
Router classifies intent (research/write/summarize/explain)
    ↓
Router calls _run_retrieval():
  • Search project files (if project_id exists)
  • Search global library via LibrarySearchService
  • Merge results (project first, deduplicated)
    ↓
Researcher agent receives ctx.retrieved_chunks
    ↓
For scholarly questions (no project):
  • Uses Scholar mode persona from modes.json
  • Injects library sources into prompt
  • Calls xAI/Grok with sources
    ↓
Response with citations
```

**Key principle:** The library is the corrective mechanism, not the LLM choice. All LLMs have training biases; library-based retrieval provides grounded context regardless of which provider generates the response.

### Reference Services

| Service | Purpose |
|---------|---------|
| `sword_client` | Local Bible modules |
| `sefaria_client` | Jewish text API with caching |
| `reference_service` | Unified reference interface |

---

## LLM Provider Architecture

Tamor uses a multi-provider LLM architecture, routing requests to different providers based on the task type.

### Provider Assignments

| Agent Mode | Provider | Model | Rationale |
|------------|----------|-------|-----------|
| **Scholar** | xAI | `grok-4-fast-reasoning` | Best textual analysis for theological research, 2M context window, lowest cost for library-heavy context injection |
| **Engineer** | Anthropic | `claude-sonnet-4-5` | Top coding benchmarks, best instruction-following for niche languages (AutoLISP, VBA, iLogic) |
| **Classification/Routing** | Ollama (local) | `phi3:mini` | Zero-cost, data sovereignty, fast heuristic + LLM fallback |

### Provider Selection Flow

```
User message
    ↓
Router classifies intent (Ollama local)
    ↓
Agent mode determined (Scholar/Engineer/Writer/Archivist)
    ↓
Provider selected based on mode:
  • Scholar → xAI (Grok)
  • Engineer → Anthropic (Claude)
  • Writer → xAI (Grok)
  • Archivist → Anthropic (Claude)
    ↓
Context injection (library, references, memory)
    ↓
LLM call to selected provider
    ↓
Epistemic processing (provider-agnostic)
```

### API Format Differences

**xAI (OpenAI-compatible):**
```python
# Endpoint: https://api.x.ai/v1/chat/completions
# Auth: Bearer token
# Messages: [{"role": "system|user|assistant", "content": "..."}]
# Response: choices[0].message.content
```

**Anthropic:**
```python
# Endpoint: https://api.anthropic.com/v1/messages
# Auth: x-api-key header + anthropic-version header
# Messages: NO system role in messages array (system prompt separate)
# Response: content is a LIST of blocks
#   Extract: "".join(b["text"] for b in content if b["type"] == "text")
```

### Design Rationale

The provider swap was driven by empirical testing (see [LLM Provider Decision](/tamor-llm-provider-decision.md)):

1. **Theological research** — Grok demonstrated stronger textual analysis and willingness to follow minority interpretive positions on textual merits without hedging toward consensus
2. **Coding tasks** — Claude leads coding benchmarks and excels at instruction-following for niche languages
3. **Cost optimization** — Grok at $0.20/M input tokens is 10-15x cheaper than alternatives for library-heavy context injection
4. **The library is the corrective** — All models have training biases; the library-based retrieval system provides the corrective mechanism regardless of which LLM generates the response

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
| xAI API (Grok) | LLM for Scholar mode (theological research) | Remote |
| Anthropic API (Claude) | LLM for Engineer mode (coding tasks) | Remote |
| Ollama | LLM for classification/routing | Local |
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

### Environment Variables (LLM)

| Variable | Purpose |
|----------|---------|
| `XAI_API_KEY` | xAI API key for Grok (Scholar mode) |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude (Engineer mode) |
| `OLLAMA_BASE_URL` | Ollama endpoint (default: `http://localhost:11434`) |
| `OLLAMA_MODEL` | Default Ollama model for classification (default: `phi3:mini`) |

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

*Last updated: v1.48 (LLM Provider Architecture)*
