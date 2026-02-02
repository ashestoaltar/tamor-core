# Tamor

Personal AI workspace for research, knowledge management, and assisted creation. Local-first, privacy-respecting.

## Stack

- **Frontend:** React + Vite (`ui/`)
- **Backend:** Flask/Gunicorn (`api/`)
- **Database:** SQLite (`api/memory/tamor.db`)
- **Config:** YAML files in `config/`

## Key Documentation

- `docs/INDEX.md` — documentation hub
- `docs/architecture.md` — system design
- `docs/BOUNDARIES.md` — what Tamor will/won't do
- `docs/Features.md` — feature reference
- `Roadmap/Roadmap.md` — authoritative development plan (separate from docs by design)

## Key Concepts

### Multi-Agent Routing
Requests are routed to specialized agents based on intent:
- **Researcher** — source gathering, analysis
- **Writer** — prose synthesis
- **Engineer** — code generation
- **Archivist** — memory management

### Epistemic System
Tamor surfaces uncertainty and contested topics. Responses are classified:
- Deterministic (computed/exact)
- Grounded-Direct (restating text)
- Grounded-Contested (interpretive)
- Ungrounded (inferential)

Configured in `config/epistemic_rules.yml`.

## Configuration Files

| File | Purpose |
|------|---------|
| `config/modes.yml` | Assistant mode definitions |
| `config/personality.yml` | Tamor's identity and tone |
| `config/epistemic_rules.yml` | Truth signaling rules |
| `.env` | Environment variables, API keys |

## Conventions

- UI does not invent state — all truth comes from API
- Tasks require explicit user approval before execution
- Epistemic honesty: surface uncertainty, name interpretive lenses
- SQLite by design (single-user, zero config)

## Running

```bash
make dev        # start both API and UI
make api        # API only
make ui         # UI only
```

## Debugging

Add `?debug=1` to URL or `X-Tamor-Debug: 1` header to see routing decisions in API responses.

## Local LLM (Ollama)

Ollama is installed and integrated as a local LLM provider.

**Installed models:**
- `llama3.1:8b` (4.9 GB) — General purpose, good instruction following
- `mistral:latest` (4.4 GB) — Fast, good for coding and general tasks

**Usage in code:**
```python
from services.llm_service import get_local_llm_client

client = get_local_llm_client()
if client:
    response = client.chat_completion([
        {"role": "user", "content": "Summarize this text..."}
    ])
```

**Environment variables** (in `.env`):
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

**Performance:** ~5 tokens/sec on CPU (Ryzen 5 5500U). Suitable for:
- Background summarization
- Entity extraction
- Routing/classification
- Offline fallback

## Session Notes

### 2026-02-01 (Local AI Integration - Major Feature)

**Ollama Installation & Models**
- Installed Ollama v0.15.4 for local LLM inference
- Models downloaded:
  - `phi3:mini` (2.2GB) — Fast classification model
  - `mistral:latest` (4.4GB) — General purpose
  - `llama3.1:8b` (4.9GB) — Complex reasoning
- Performance: ~5 tokens/sec on CPU (Ryzen 5 5500U)

**LLM Service Integration** (`api/services/llm_service.py`)
- Added `OllamaProvider` class with `chat_completion()` and `generate()` methods
- New functions:
  - `get_local_llm_client()` — Get Ollama provider
  - `local_llm_is_configured()` — Check if Ollama is running
  - `get_best_available_client(prefer_local=False)` — Smart provider selection
- Environment variables: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`

**Agent Router Integration** (`api/services/router.py`)
- Intent classification now uses 3-tier system:
  1. **Heuristics** (regex patterns) — 0ms
  2. **Cache hit** (LRU, 500 entries) — 0ms
  3. **Local LLM** (phi3:mini) — 5-15s on CPU
- New methods:
  - `_classify_intent_heuristic()` — Fast regex matching
  - `_classify_intent_local_llm()` — Nuanced classification with caching
- Optimizations:
  - `ClassificationCache` — LRU cache for repeated queries
  - Uses phi3:mini instead of larger models (2x faster)
  - Pre-warms model in background thread on startup
- Trace includes `intent_source`: "heuristic" | "local_llm" | "local_llm_cache" | "none"
- Fixed: Research/write queries without project context now fall through to Claude

**System Status Updates**
- `/api/system-status` now reports:
  - `local_llm_available`: boolean
  - `local_llm_models`: list of installed models

**Documentation**
- Added Section K "Local AI Vision" to `Roadmap/Roadmap-extensions.md`
- Comprehensive plan for local-first AI capabilities
- Hardware evaluation and upgrade path documented

### 2026-02-01 (Reader & Library Improvements)

**View Original Feature**
- New endpoint: `GET /api/library/<file_id>/download?inline=true`
- "View Original" button in Reader header (external link icon)
- Opens PDF in browser's native viewer — useful for scanned documents

**PDF Text Cleanup** (`api/services/file_parsing.py`)
- New `clean_extracted_text()` function:
  - Removes standalone page numbers (various formats)
  - Merges broken lines (hyphenated, mid-sentence)
  - Collapses multiple blank lines
- Applied at extraction time and retrieval time

**Marker PDF Evaluation**
- Tested `marker-pdf` library for advanced extraction
- Results: Better for scanned PDFs but 4 min vs 0.1s for pypdf
- Decision: Keep pypdf as Tier 1, Marker as future Tier 2 for scanned docs

**Reader Audio Fixes**
- Fixed auto-advance: continues through all chunks
- Fixed speed control: uses browser `playbackRate`
- Improved preloading: 5 chunks ahead, starts after 100ms

**Library Search Fixes**
- Fixed 405 error (POST→GET)
- Added search mode toggle: Content (semantic) vs Title (filename)

**Library Indexing Fix**
- `last_indexed_at` now properly updates after processing
- All 1,934 library files properly indexed
- **Decision:** Keep pypdf as Tier 1 (fast, handles most clean PDFs)
- **Future consideration:** Marker as optional Tier 2 for scanned/complex PDFs
  - User-triggered re-extraction when quality is poor
  - Batch processing overnight for archive collection

### 2026-02-01 (Phase 5.5 Integrated Reader)
- **Integrated Reader Complete** — Unified reading interface with local TTS
  - TTS Service (`api/services/tts_service.py`): Piper wrapper with chunking and caching
  - Reader Service (`api/services/reader_service.py`): Content retrieval, sessions, bookmarks
  - 18 API endpoints under `/api/reader` Blueprint
  - ReaderView and ReaderControls React components
  - Expandable right panel mode (55% width, chat stays visible)
  - "Read" buttons added to Library and Files tabs
- **Piper TTS Setup Script** (`scripts/setup_piper.py`)
  - CLI for installing Piper and downloading voice models
  - 13 voices available (American, British, German, Spanish, French)
  - Voices stored at `/mnt/library/piper_voices/`
- **UI Integration**
  - ReaderContext for global reader state management
  - CSS :has() selector for parent-based panel expansion
  - Reader.css updated for panel context (height: 100% vs 100vh)

### 2026-02-01 (WildBranch Ministries Ingest + Transcription)
- **Bulk Ingest Workflow** — Added 629 files to NAS library
  - Created `/mnt/library/religious/wildbranch ministries/` with subfolders
  - Organized: audio/, articles/, hebrew-mind-greek-mind/, lessons/, powerpoint/, word-studies/
  - 608 PDFs + 21 MP3s ingested into library system
- **Transcription Queue System** — First real test of MP3 transcription
  - Created migration 011 for `transcription_queue` table (was missing)
  - Fixed worker to save transcripts alongside source audio files
  - All 21 MP3s transcribed with Whisper base model
  - Added `api/scripts/run_transcriptions.py` CLI with progress display
- **Bulk Ingest + Transcription Workflow** (for future use):
  ```bash
  # 1. Copy files to NAS folder, then ingest
  curl -b /tmp/tamor-cookies.txt -X POST http://localhost:5055/api/library/ingest \
    -H "Content-Type: application/json" \
    -d '{"path": "/mnt/library/your/folder", "auto_index": false}'

  # 2. Queue all audio for transcription
  curl -b /tmp/tamor-cookies.txt -X POST http://localhost:5055/api/library/transcription/queue-all

  # 3. Run transcriptions (with progress)
  cd ~/tamor-core/api && source venv/bin/activate
  python3 scripts/run_transcriptions.py
  ```

### 2026-02-01 (Library Collections)
- **Library Collections System** — Organize library files into named groups
  - Flat collections design (files can belong to multiple collections)
  - Full CRUD: create, edit, delete collections with name, description, color
  - Many-to-many relationship via junction table
  - New database tables: `library_collections`, `library_collection_files`
  - 9 API endpoints for collection management and file membership
  - UI: Collections tab in Library, collection cards, add-to-collection dropdown
  - Color picker with 10 preset colors for visual organization

### 2026-02-01 (Internet Archive Integration)
- **Internet Archive Harvester** — CLI tool for searching/downloading public domain materials
  - Downloads to NAS at `/mnt/library/internet_archive/`
  - Clean filename renaming: `{Author} - {Title}.pdf`
  - Provenance tracking in `ia_items` table
- **IA Import Service** — Bridge to library system
  - API endpoints: `/api/library/ia/{stats,pending,import,import-all,search}`
  - Full metadata preservation from IA to library
  - OCR integration for scanned PDFs
- Tested with founding era documents (Federalist Papers, Constitutional Convention, American Revolution)
- 6 test items harvested, imported to library with embeddings

### 2026-01-30 (Moltbook Research)
- **Created ~/moltbook-research/** — Side project for archiving AI agent social network posts
- Analyzed 100 posts for memory management strategies
- Added **Section J: Memory System Research Extensions** to Roadmap-extensions.md
  - Memory aging & decay, automated compression, token budget awareness, memory stats dashboard
  - All parked until after Phase 8
- Research artifacts: `~/moltbook-research/research/outputs/`

### 2026-01-29 (Phase 6.4 Complete)
- **Phase 6.4 Plugin Framework Expansion** — all 5 items complete:
  - Markdown export (plugin + API + UI menu)
  - PDF export (WeasyPrint, styled output)
  - Plugin config persistence (per-project settings in DB)
  - Reference caching with version tracking
  - Zotero integration (reads local SQLite, API ready)
- Backend-first approach: APIs ready, UI when friction demands it
- Zotero will be set up alongside NAS library system

### 2026-01-29 (Earlier)
- Created CLAUDE.md for session context
- Cleaned up roadmap inconsistencies (Focus Mode, completed extensions)
- Prioritized Phase 6.4 plugin items (Markdown/PDF export, Zotero, etc.)
- System maintenance: disabled ethernet (wifi only), removed Cardano (freed 316GB)
- Installed all SWORD modules (KJV, ASV, YLT, OSHB, LXX, SBLGNT, TR)
- Downloaded Whisper models (base, small, large-v2)
