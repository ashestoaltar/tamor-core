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

## Next Steps

- [ ] **Install Ollama + local LLM** — Add as fallback/offline provider
  ```bash
  # Install Ollama
  curl -fsSL https://ollama.com/install.sh | sh

  # Pull recommended model
  ollama pull llama3.1:8b
  ```
  Then wire into `api/services/llm_service.py` as secondary provider.

## Session Notes

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
