# Tamor Features Guide

This document provides a reference for Tamor's major features, their APIs, and usage patterns.

---

## Table of Contents

1. [Global Library System](#global-library-system)
2. [Reference Integration](#reference-integration)
3. [Multi-Agent System](#multi-agent-system)
4. [Memory System](#memory-system)
5. [Plugin Framework](#plugin-framework)
6. [Zotero Integration](#zotero-integration)
7. [Internet Archive Integration](#internet-archive-integration)
8. [Reference Cache](#reference-cache)
9. [Project Pipelines](#project-pipelines)
10. [Auto-Insights & Reasoning](#auto-insights--reasoning)
11. [Media & Transcription](#media--transcription)
12. [Epistemic Honesty System](#epistemic-honesty-system)
13. [Focus Mode](#focus-mode)
14. [Progressive Web App (PWA)](#progressive-web-app-pwa)
15. [Integrated Reader](#integrated-reader)

---

## Global Library System

The Library System provides a centralized, NAS-backed knowledge repository. Documents are stored once and referenced by projects without duplication.

### Core Concepts

- **Library Files**: Documents stored in the global library with hash-based deduplication
- **Library Chunks**: Text segments with embeddings for semantic search
- **Project References**: Links between projects and library files (no file duplication)
- **Context Injection**: Automatic injection of relevant library content into chat

### API Endpoints

#### Library Files

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/library` | GET | List library files (supports `limit`, `offset`, `source_type`, `mime_type`, `search`) |
| `/api/library/<id>` | GET | Get file details |
| `/api/library` | POST | Add file to library |
| `/api/library/<id>` | PATCH | Update file metadata |
| `/api/library/<id>` | DELETE | Delete file from library |
| `/api/library/<id>/download` | GET | Download/view original file (`?inline=true` for browser view) |
| `/api/library/stats` | GET | Library statistics |

#### Project References

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects/<id>/library` | GET | List project's library references |
| `/api/projects/<id>/library` | POST | Add library file reference to project |
| `/api/projects/<id>/library/<file_id>` | DELETE | Remove reference |
| `/api/projects/<id>/library/bulk` | POST | Bulk add references |

#### Scanning & Ingestion

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/library/scan/config` | GET | Get scan configuration |
| `/api/library/scan/config` | POST | Update scan configuration |
| `/api/library/scan/preview` | POST | Preview what would be scanned |
| `/api/library/scan/summary` | GET | Get scan summary |
| `/api/library/ingest` | POST | Ingest files from scan |
| `/api/library/sync` | POST | Full sync (add new, remove missing) |

#### Index Queue (Background Embedding)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/library/index/queue` | GET | List files needing indexing |
| `/api/library/index/next` | POST | Index next file in queue |
| `/api/library/index/all` | POST | Index all pending files |
| `/api/library/index/reindex/<id>` | POST | Mark file for re-indexing |
| `/api/library/index/stats` | GET | Indexing statistics |

#### Search

The UI provides two search modes via a toggle:
- **Content**: Semantic search using embeddings (finds conceptually related text)
- **Title**: Filename/metadata text filter (exact substring match)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/library/search` | GET | Semantic search across library |
| `/api/library/<id>/search` | GET | Search within specific file |
| `/api/library/<id>/similar` | GET | Find similar files |
| `/api/library` | GET | List files with `search` param for title/filename filter |

**Semantic Search Query Params:**
```
/api/library/search?q=search+text&scope=library&limit=10&min_score=0.4
```

**Title/Filename Filter:**
```
/api/library?search=hamilton&limit=50
```

#### Context Preview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/library/context/preview` | POST | Preview what context would be injected |

**Request:**
```json
{
  "message": "What does the research say about X?",
  "project_id": 13,
  "max_chunks": 5
}
```

#### Settings

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/library/settings` | GET | Get user's library settings |
| `/api/library/settings` | PATCH | Update settings |
| `/api/library/settings/reset` | POST | Reset to defaults |

**Available Settings:**
```json
{
  "context_injection_enabled": true,   // Enable/disable auto context
  "context_max_chunks": 5,             // Max chunks to inject
  "context_max_chars": 4000,           // Max characters
  "context_min_score": 0.4,            // Minimum relevance (0-1)
  "context_scope": "all",              // "library", "project", "all"
  "show_sources_in_response": true     // Show source citations
}
```

### How Context Injection Works

1. When you send a chat message, the system searches the library for relevant content
2. Chunks with relevance score >= `min_score` are selected (up to `max_chunks`)
3. Content is formatted and injected into the system prompt
4. The LLM receives instructions to cite sources when using library content

**Scope Behavior:**
- `library`: Search entire library
- `project`: Search only files referenced by current project
- `all`: Search both, with 10% relevance boost for project files

### Collections

Organize library files into named groups. Files can belong to multiple collections.

#### Collection API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/library/collections` | GET | List all collections with file counts |
| `/api/library/collections` | POST | Create collection `{name, description?, color?}` |
| `/api/library/collections/<id>` | GET | Get collection details |
| `/api/library/collections/<id>` | PATCH | Update collection |
| `/api/library/collections/<id>` | DELETE | Delete collection (files remain in library) |
| `/api/library/collections/<id>/files` | GET | List files in collection |
| `/api/library/collections/<id>/files` | POST | Add file(s) `{file_id}` or `{file_ids: [...]}` |
| `/api/library/collections/<id>/files/<file_id>` | DELETE | Remove file from collection |
| `/api/library/<file_id>/collections` | GET | Get collections a file belongs to |

#### Example: Create and Populate a Collection

```bash
# Create collection
curl -X POST http://localhost:5055/api/library/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "Founding Era", "description": "American founding documents", "color": "#6366f1"}'

# Add file to collection (returns collection_id in response)
curl -X POST http://localhost:5055/api/library/collections/1/files \
  -H "Content-Type: application/json" \
  -d '{"file_id": 42}'

# Add multiple files
curl -X POST http://localhost:5055/api/library/collections/1/files \
  -H "Content-Type: application/json" \
  -d '{"file_ids": [42, 43, 44]}'

# List collection files
curl http://localhost:5055/api/library/collections/1/files
```

#### Available Colors

Collections support 10 preset colors for visual organization:
- Indigo (#6366f1), Purple (#8b5cf6), Pink (#ec4899), Red (#ef4444), Orange (#f97316)
- Yellow (#eab308), Green (#22c55e), Teal (#14b8a6), Sky (#0ea5e9), Gray (#6b7280)

### Directory Scanning

Configure which directories to scan for library content:

```bash
# Set scan path
curl -X POST http://localhost:5055/api/library/scan/config \
  -H "Content-Type: application/json" \
  -d '{"mount_path": "/mnt/library"}'

# Preview scan results
curl -X POST http://localhost:5055/api/library/scan/preview \
  -H "Content-Type: application/json" \
  -d '{"include_patterns": ["*.pdf", "*.epub"], "exclude_patterns": ["*.tmp"]}'

# Ingest all new files
curl -X POST http://localhost:5055/api/library/ingest \
  -H "Content-Type: application/json" \
  -d '{"auto_index": true}'
```

---

## Reference Integration

Biblical and scholarly reference sources with local-first storage.

### Sources

- **SWORD Modules**: Local Bible translations (KJV, ASV, YLT, etc.)
- **Sefaria**: Jewish texts with local caching (Tanakh, Talmud, Midrash)

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/references/lookup` | POST | Look up a passage |
| `/api/references/compare` | POST | Compare translations |
| `/api/references/search` | POST | Search within texts |
| `/api/references/detect` | POST | Detect references in text |
| `/api/references/commentary` | POST | Get commentary |
| `/api/references/cross-references` | POST | Get cross-references |
| `/api/references/translations` | GET | List available translations |
| `/api/references/modules` | GET | List installed modules |
| `/api/references/modules/install` | POST | Install a module |

### Automatic Context Injection

Scripture references in chat messages are automatically detected and injected:

```
User: "What does Genesis 1:1 mean?"
→ System fetches actual text from SWORD
→ Injects: "[Scripture Context] Genesis 1:1 (KJV): 'In the beginning...'"
→ LLM responds with grounded analysis
```

---

## Multi-Agent System

Specialized agents handle different types of requests, with different LLM providers optimized for each task.

### Available Agents

| Agent | Purpose | Triggers | LLM Provider |
|-------|---------|----------|--------------|
| **Researcher** | Source gathering, structured analysis | "research", "analyze", "find", "compare" | xAI (Grok) |
| **Writer** | Prose synthesis from research | "write", "draft", "compose" | xAI (Grok) |
| **Engineer** | Code generation with project awareness | "implement", "fix", "create function" | Anthropic (Claude) |
| **Archivist** | Memory management | "remember", "forget", "I prefer" | Anthropic (Claude) |

### LLM Provider Assignments

| Mode | Provider | Model | Rationale |
|------|----------|-------|-----------|
| Scholar | xAI | `grok-4-fast-reasoning` | Best textual analysis for theological research, 2M context window, lowest cost |
| Engineer | Anthropic | `claude-sonnet-4-5` | Top coding benchmarks, best instruction-following |
| Classification | Ollama | `phi3:mini` | Local, zero-cost routing decisions |

### How Routing Works

1. Intent classified using heuristics (0ms) or local LLM (5-15s fallback)
2. Scholarly/theological questions detected via pattern matching
3. Agent sequence selected based on intent
4. LLM provider selected based on agent (researcher→xAI, engineer→Anthropic)
5. Library chunks retrieved and injected into context
6. Simple queries fall through to default LLM

### Library Integration

The Researcher agent queries the global library (27K+ indexed chunks) before calling the LLM:
- For project context: searches both project files and global library
- For unassigned scholarly questions: searches global library directly
- Library sources are injected into the prompt with attribution
- LLM is instructed to cite sources when using library content

### Debug Trace

Add `?debug=1` or header `X-Tamor-Debug: 1` to see routing decisions:

```json
{
  "router_trace": {
    "trace_id": "abc123",
    "route_type": "agent_pipeline",
    "provider_used": "xai",
    "model_used": "grok-4-fast-reasoning",
    "intents_detected": ["research", "summarize"],
    "intent_source": "heuristic",
    "agent_sequence": ["researcher", "writer"],
    "retrieval_used": true,
    "retrieval_count": 15,
    "timing_ms": {"classify": 1, "retrieval": 45, "researcher": 2500, "total": 2600}
  }
}
```

---

## Memory System

Long-term memory with explicit governance.

### Categories

- `fact`: Factual information about user
- `preference`: User preferences and style
- `context`: Background context
- `general`: Miscellaneous

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/memories` | GET | List memories (supports `category`, `search`) |
| `/api/memories` | POST | Create memory |
| `/api/memories/<id>` | PATCH | Update memory |
| `/api/memories/<id>` | DELETE | Delete memory |
| `/api/memories/<id>/pin` | POST | Pin memory (always included) |

### Natural Language Commands

In chat:
- "Remember that I prefer formal writing"
- "Forget my preference about X"
- "My name is John"

The Archivist agent handles these automatically.

---

## Plugin Framework

Extensible system for importers, exporters, and reference backends.

### Plugin Types

1. **Importers**: Bring content into projects
   - Local Folder, Audio Transcript, Bulk PDF

2. **Exporters**: Export project data
   - ZIP Download, JSON Export, Markdown Export, PDF Export

3. **References**: External content sources
   - Local Docs, Web Fetch

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/plugins/importers` | GET | List importers |
| `/api/plugins/importers/<id>/import` | POST | Run import |
| `/api/plugins/exporters` | GET | List exporters |
| `/api/plugins/exporters/<id>/export` | POST | Generate export |
| `/api/plugins/references` | GET | List reference plugins |
| `/api/plugins/references/<id>/list` | POST | List available items |
| `/api/plugins/references/<id>/fetch` | POST | Fetch item content |

### Project Export Endpoints

Direct export endpoints for common formats:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects/<id>/export/markdown` | GET | Export as Markdown file |
| `/api/projects/<id>/export/pdf` | GET | Export as styled PDF |

**Query Parameters:**
- `include_system=true` — Include system messages (default: false)
- `include_metadata=true` — Include timestamps and counts (default: true)
- `include_notes=true` — Include project notes (default: true)

### Plugin Configuration

Per-project plugin settings stored in database:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects/<id>/plugins` | GET | Get all plugin configs |
| `/api/projects/<id>/plugins/<plugin_id>` | GET | Get specific plugin config |
| `/api/projects/<id>/plugins/<plugin_id>` | PATCH | Update plugin config |
| `/api/projects/<id>/plugins/<plugin_id>` | DELETE | Remove plugin config |

### Example: Markdown Export

```bash
curl http://localhost:5055/api/projects/13/export/markdown \
  -o project_export.md
```

### Example: PDF Export

```bash
curl http://localhost:5055/api/projects/13/export/pdf \
  -o project_export.pdf
```

---

## Zotero Integration

Import references, PDFs, and citations from local Zotero library.

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/integrations/zotero/status` | GET | Check if Zotero available |
| `/api/integrations/zotero/collections` | GET | List Zotero collections |
| `/api/integrations/zotero/items` | GET | List items (filterable) |
| `/api/integrations/zotero/items/<key>` | GET | Get item details |
| `/api/integrations/zotero/items/<key>/citation` | GET | Get formatted citation |
| `/api/integrations/zotero/search?q=` | GET | Search items |

**Query Parameters for `/items`:**
- `collection_id` — Filter by collection
- `type` — Filter by item type (book, article, etc.)
- `limit` — Max items to return (default: 100)

### Example: Check Zotero Status

```bash
curl http://localhost:5055/api/integrations/zotero/status
# Returns: {"available": true, "db_path": "...", "storage_path": "..."}
```

### Example: Search Zotero

```bash
curl "http://localhost:5055/api/integrations/zotero/search?q=epistemology&limit=10"
```

### Setup Notes

Zotero data directory is auto-detected from:
- Linux: `~/.zotero/zotero/`
- macOS: `~/Library/Application Support/Zotero/`
- Custom: `~/Zotero/`

For NAS setup, point Zotero's data directory to NAS path.

---

## Internet Archive Integration

Search, download, and import public domain materials from the Internet Archive into Tamor's library.

### Features

- **Search**: Query IA's catalog with optional filters (mediatype, collection, date range)
- **Download**: Fetch items to NAS with preferred format selection (PDF, EPUB, etc.)
- **Clean Filenames**: Automatically rename verbose IA filenames to `{Author} - {Title}.pdf`
- **Provenance Tracking**: All downloads tracked in `ia_items` table with full metadata
- **Library Import**: Bridge service imports IA items into Tamor's library with OCR if needed
- **Metadata Preservation**: IA metadata (creator, date, subject, collection, etc.) preserved as library metadata

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/library/ia/stats` | GET | IA import statistics |
| `/api/library/ia/pending` | GET | Items downloaded but not imported |
| `/api/library/ia/import/<id>` | POST | Import single IA item to library |
| `/api/library/ia/import-all` | POST | Import all pending items |
| `/api/library/ia/search` | GET | Search IA items in database |

### CLI Tool

The harvester CLI is at `api/tools/ia_harvester.py`:

```bash
# Search IA catalog
python api/tools/ia_harvester.py search "federalist papers" --limit 5

# Download items (saves to /mnt/library/internet_archive/)
python api/tools/ia_harvester.py download <identifier>

# Download with clean filename disabled (keeps original IA filename)
python api/tools/ia_harvester.py download <identifier> --no-clean-filenames
```

### Example: Import to Library

```bash
# Check pending items
curl http://localhost:5055/api/library/ia/pending

# Import all pending with embeddings
curl -X POST http://localhost:5055/api/library/ia/import-all

# Check stats
curl http://localhost:5055/api/library/ia/stats
```

### Setup Notes

- Downloads stored at `/mnt/library/internet_archive/`
- Requires `internetarchive` Python package (included in requirements.txt)
- Downloaded items tracked in `ia_items` table for deduplication
- Import service uses standard ingest pipeline (OCR for scanned PDFs)

---

## Reference Cache

Cache external content (web, Sefaria, etc.) with version tracking.

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cache/stats` | GET | Cache statistics |
| `/api/cache/references` | GET | List cached URLs |
| `/api/cache/references/<url>` | GET | Get cache info for URL |
| `/api/cache/references/<url>/versions` | GET | Get version history |
| `/api/cache/cleanup` | POST | Remove expired entries |

### Features

- Content deduplication via SHA256 hash
- Automatic version increment when content changes
- TTL support with expiration tracking
- Version history for any URL

### Example: ZIP Export

```bash
curl -X POST http://localhost:5055/api/plugins/exporters/zip-download/export \
  -H "Content-Type: application/json" \
  -d '{"project_id": 13, "config": {"include_transcripts": true}}'
```

---

## Project Pipelines

Guided workflows for research, writing, and study.

### Available Templates

| Template | Steps |
|----------|-------|
| `research` | Define → Gather → Analyze → Synthesize → Review |
| `writing` | Outline → Draft → Revise → Polish → Publish |
| `study` | Survey → Focus → Absorb → Review → Apply |
| `long_form` | Concept → Research → Structure → Draft → Revise → Edit → Finalize |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/pipelines` | GET | List available templates |
| `/api/projects/<id>/pipeline` | GET | Get project's active pipeline |
| `/api/projects/<id>/pipeline/start` | POST | Start a pipeline |
| `/api/projects/<id>/pipeline/advance` | POST | Move to next step |
| `/api/projects/<id>/pipeline/guidance` | GET | Get step guidance |
| `/api/projects/<id>/pipeline/summary` | GET | Get LLM-generated summary |

---

## Auto-Insights & Reasoning

Automatic analysis of project content.

### File Insights

Generated on text extraction:
- **Themes**: Main topics
- **Contradictions**: Internal inconsistencies
- **Missing Info**: Gaps in content
- **Assumptions**: Implicit assumptions

```bash
# Get file insights
curl http://localhost:5055/api/files/123/insights

# Get project-wide insights
curl http://localhost:5055/api/projects/13/insights
```

### Multi-File Reasoning

Cross-document analysis:

```bash
# Relationship analysis
curl http://localhost:5055/api/projects/13/reasoning/relationships

# Contradiction detection
curl http://localhost:5055/api/projects/13/reasoning/contradictions

# Logic flow analysis
curl http://localhost:5055/api/projects/13/reasoning/logic-flow
```

---

## Media & Transcription

Audio/video transcription with timestamps and batch queue processing.

### API Endpoints

#### Direct Transcription

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects/<id>/transcribe-url` | POST | Transcribe from URL |
| `/api/files/<id>/transcribe` | POST | Transcribe uploaded file |
| `/api/transcripts` | GET | List transcripts |
| `/api/transcripts/<id>` | GET | Get transcript |
| `/api/transcripts/<id>` | DELETE | Delete transcript |
| `/api/transcripts/<id>/pdf` | GET | Export as PDF |

#### Transcription Queue (Library)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/library/transcription/models` | GET | List available Whisper models |
| `/api/library/transcription/queue` | GET | List queue items with stats |
| `/api/library/transcription/queue` | POST | Add file to queue `{library_file_id, model?}` |
| `/api/library/transcription/queue/<id>` | DELETE | Remove from queue |
| `/api/library/transcription/queue/<id>/retry` | POST | Retry failed item |
| `/api/library/transcription/candidates` | GET | Files that can be transcribed |
| `/api/library/transcription/queue-all` | POST | Queue all candidates |
| `/api/library/transcription/process` | POST | Process next or batch `{count?}` |
| `/api/library/<file_id>/transcript` | GET | Get transcript for library file |

**Note:** Transcripts are saved alongside source audio files (e.g., `audio/file.mp3` → `audio/file_transcript.json`).

### Whisper Models

| Model | Speed | Accuracy | Use Case |
|-------|-------|----------|----------|
| `tiny` | Fastest | Lower | Quick previews, testing |
| `base` | Fast | Good | General use (default) |
| `small` | Medium | Better | Important content |
| `medium` | Slower | High | High-quality needs |
| `large-v2` | Slowest | Highest | Critical accuracy |

### Example: YouTube Transcription

```bash
curl -X POST http://localhost:5055/api/projects/13/transcribe-url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=xxx", "model": "base"}'
```

### Example: Queue Library Files

```bash
# List files that can be transcribed
curl http://localhost:5055/api/library/transcription/candidates

# Queue all candidates with base model
curl -X POST http://localhost:5055/api/library/transcription/queue-all \
  -H "Content-Type: application/json" \
  -d '{"model": "base"}'

# Process next item in queue
curl -X POST http://localhost:5055/api/library/transcription/process
```

### Bulk Ingest + Transcription Workflow

Complete workflow for adding new audio files to the library and transcribing them:

```bash
# 1. Copy files to NAS folder (manually or via script)

# 2. Ingest folder into library
curl -b cookies.txt -X POST http://localhost:5055/api/library/ingest \
  -H "Content-Type: application/json" \
  -d '{"path": "/mnt/library/religious/your-folder", "auto_index": false}'

# 3. Queue all audio for transcription
curl -b cookies.txt -X POST http://localhost:5055/api/library/transcription/queue-all \
  -H "Content-Type: application/json" \
  -d '{"model": "base"}'

# 4. Run transcriptions with progress display
cd ~/tamor-core/api && source venv/bin/activate
python3 scripts/run_transcriptions.py
```

### CLI Transcription Script

Run transcriptions with progress display:

```bash
cd ~/tamor-core/api && source venv/bin/activate
python3 scripts/run_transcriptions.py
```

Output shows progress bar, time per file, and ETA for remaining files.

---

## Quick Reference: Common Tasks

### Add a PDF to the library and link to project

```bash
# 1. Add to library
curl -X POST http://localhost:5055/api/library \
  -F "file=@document.pdf" \
  -F "source_type=upload"

# 2. Link to project (use returned file_id)
curl -X POST http://localhost:5055/api/projects/13/library \
  -H "Content-Type: application/json" \
  -d '{"library_file_id": 42}'
```

### Search library and preview context

```bash
# Search
curl -X POST http://localhost:5055/api/library/search \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning", "limit": 5}'

# Preview what would be injected into chat
curl -X POST http://localhost:5055/api/library/context/preview \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain the key concepts"}'
```

### Disable library context injection

```bash
curl -X PATCH http://localhost:5055/api/library/settings \
  -H "Content-Type: application/json" \
  -d '{"context_injection_enabled": false}'
```

### Batch ingest from directory

```bash
# Configure path
curl -X POST http://localhost:5055/api/library/scan/config \
  -H "Content-Type: application/json" \
  -d '{"mount_path": "/path/to/docs"}'

# Preview
curl -X POST http://localhost:5055/api/library/scan/preview

# Ingest with auto-indexing
curl -X POST http://localhost:5055/api/library/ingest \
  -H "Content-Type: application/json" \
  -d '{"auto_index": true}'
```

---

## UI Components

### RightPanel Tab Structure

```
RightPanel
├── Essential Tabs (always visible)
│   ├── Workspace    - Project overview, pipeline controls
│   ├── Files        - Project files, library refs, keyword search
│   ├── Library      - Global library browser
│   ├── Memory       - Long-term memory management
│   └── References   - Scripture lookup (SWORD/Sefaria)
├── Research Group (collapsible on mobile)
│   ├── Search       - Semantic cross-file search
│   ├── Insights     - Auto-generated insights
│   ├── Reasoning    - Cross-document analysis
│   └── Knowledge    - Knowledge graph
└── Tools Group (collapsible on mobile)
    ├── Media        - Transcription controls
    ├── Viewer       - Document viewer
    ├── Plugins      - Import/export/reference plugins
    └── Playlists    - Media playlists
```

### Library Tab

```
Library Tab
├── Header
│   ├── Title
│   └── Navigation (Browse | Manage | ⚙️ Settings)
├── Browse View
│   ├── Stats bar (file count, size, indexed/pending)
│   ├── Search input with submit
│   └── File list
│       └── File item
│           ├── Type icon (📕 PDF, 📘 EPUB, 🎵 audio, etc.)
│           ├── Filename + size
│           └── [+] Add to project button
├── Search View
│   ├── Back button + result count
│   └── Results list
│       └── Result item
│           ├── File info
│           ├── Relevance score (% match)
│           └── Content excerpt
├── Manage View
│   ├── Storage section
│   │   ├── Mount path
│   │   └── Mount status (✓ Mounted / ✗ Not Mounted)
│   ├── Index queue section
│   │   ├── Queue stats (indexed / pending)
│   │   └── [Index Next 20] button
│   ├── Import section
│   │   └── [Import New Files] button
│   └── Transcription section
│       └── [Open Transcription Queue] button
├── Transcription Queue (overlay)
│   ├── Queue View
│   │   ├── Stats bar (pending / processing / completed / failed)
│   │   ├── Action buttons ([Process Next] [Add Files])
│   │   └── Queue item list with status icons
│   └── Add View
│       ├── Model selector dropdown
│       ├── [Queue All] button
│       └── Candidates list with individual [Queue] buttons
└── Settings View
    ├── Context Injection section
    │   ├── Enable toggle
    │   ├── Scope dropdown (library/project/all)
    │   ├── Max chunks input (1-10)
    │   └── Min score slider (0-1)
    ├── Display section
    │   └── Show sources toggle
    └── Save/Cancel buttons (when dirty)
```

### Files Tab

```
Files Tab
├── File List section
│   └── File items with summarize, structure, actions
├── Library References section (ProjectLibraryRefs)
│   ├── Header (📚 Library References + count)
│   ├── Collapsible list
│   │   └── Reference item
│   │       ├── Type icon
│   │       ├── Filename + notes
│   │       └── [×] Remove button
│   └── [+ Add from library] button
├── Keyword Search section
│   ├── Search input
│   └── Results with filename + snippet
└── Project Summary section
    ├── Prompt input
    ├── [Summarize] button
    └── Summary display with [Send to Chat]
```

### References Tab

```
References Tab
├── Lookup section
│   ├── Reference input (e.g., "Genesis 1:1-3")
│   ├── Translation dropdown
│   └── [Look Up] button
├── Citation display
│   └── CitationCard
│       ├── Reference header
│       ├── Verse text (RTL for Hebrew)
│       ├── Source badge (SWORD/Sefaria)
│       └── Actions (Copy, Compare, External link)
├── Compare Translations panel
│   ├── Translation checkboxes
│   └── Side-by-side display
├── Recent Lookups
│   └── Clickable reference list
└── Module Management
    ├── Installed modules
    └── Available modules with [Install] buttons
```

### Plugins Tab

```
Plugins Tab
├── Importers section
│   ├── Plugin selector dropdown
│   ├── Configuration form (from config_schema)
│   └── [Import] button
├── Exporters section
│   ├── Plugin selector dropdown
│   ├── Configuration form
│   ├── [Export] button
│   └── Download link (after export)
└── References section
    ├── Plugin selector dropdown
    ├── Configuration form
    ├── [Browse] / [Fetch] button
    └── Results display
```

### Memory Tab

```
Memory Tab
├── Search/Filter bar
│   ├── Search input
│   └── Category filter dropdown
├── Memory list
│   └── Memory item
│       ├── Content text
│       ├── Category badge
│       ├── Pinned indicator
│       └── Actions (Edit, Pin, Delete)
└── [Add Memory] form
    ├── Content textarea
    ├── Category selector
    └── [Save] button
```

### Library Settings Reference

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `context_injection_enabled` | boolean | true | Toggle auto-injection on/off |
| `context_scope` | enum | "all" | "library", "project", or "all" |
| `context_max_chunks` | number | 5 | Chunks to inject (1-10) |
| `context_min_score` | number | 0.4 | Minimum relevance (0-1) |
| `show_sources_in_response` | boolean | true | Display source citations |

---

## Architecture Notes

### Database Tables (Library)

- `library_files`: File metadata, hash, path
- `library_chunks`: Text chunks with embeddings
- `library_text_cache`: Extracted text cache
- `library_config`: Configuration and user settings
- `project_library_refs`: Project-to-library links

### Services

```
api/services/library/
├── storage_service.py       # Path resolution, deduplication
├── library_service.py       # CRUD operations
├── reference_service.py     # Project references
├── text_service.py          # Text extraction
├── chunk_service.py         # Chunking & embeddings
├── scanner_service.py       # Directory scanning
├── ingest_service.py        # Batch importing
├── index_queue_service.py   # Background indexing
├── search_service.py        # Semantic search
├── context_service.py       # Chat context injection
├── settings_service.py      # User preferences
├── transcription_service.py # Transcription queue management
└── transcription_worker.py  # Queue processing with faster-whisper
```

### Embedding Model

Uses sentence-transformers locally (no API costs):
- Model: `all-MiniLM-L6-v2` (384 dimensions)
- Stored as binary blobs in SQLite
- Cosine similarity for search

---

## Epistemic Honesty System

Phase 8.2 introduces a unified system for truth signaling — combining provenance transparency, confidence enforcement, and user-facing indicators into one coherent honesty layer.

### Pipeline Flow

```
User asks theological question
        ↓
LLM generates response
        ↓
Epistemic pipeline classifies:
  → Deterministic? ✔︎
  → Grounded direct? ●
  → Grounded contested? ◐ (+ popover with alternatives)
  → Ungrounded? (no badge, but lint for risky claims)
        ↓
If risky claims found:
  → Try to attach anchor (≤250ms)
  → Else minimal sentence rewrite
        ↓
Response displayed with badge
User can hover/tap for details
```

### Answer Classification (Four-Tier Model)

| Category | Badge | Definition | Example |
|----------|-------|------------|---------|
| **Deterministic** | ✔︎ (green) | Computed, exact, from trusted data | "There are 12 items." |
| **Grounded-Direct** | ● (blue) | Restating explicit text | "Paul says X in Romans 8." |
| **Grounded-Contested** | ◐ (orange) | Grounded but interpretive | "Romans 9 is about corporate election." |
| **Ungrounded** | (no badge) | Purely inferential | General reasoning |

### Contested Domains

Six domains where contestation detection is active:
1. **Theology** - election, predestination, atonement, etc.
2. **Eschatology** - rapture, millennium, tribulation views
3. **Ecclesiology** - baptism, communion, church governance
4. **Authorship** - Pauline debates, documentary hypothesis
5. **History** - historical Jesus, early church, councils
6. **Ethics** - "Christians must/should" claims

### Contestation Levels

| Level | Name | Meaning |
|-------|------|---------|
| **C1** | Intra-tradition | Nuance within same tradition |
| **C2** | Cross-tradition | Major traditions diverge |
| **C3** | Minority position | Legitimate but not widely held |

### API Response

Chat responses now include an `epistemic` object:

```json
{
  "tamor": "processed response text",
  "conversation_id": 123,
  "epistemic": {
    "badge": "contested",
    "answer_type": "grounded_contested",
    "is_contested": true,
    "contestation_level": "C2",
    "contested_domains": ["theology"],
    "alternative_positions": ["Reformed view", "Arminian view"],
    "has_sources": true,
    "sources": ["Romans 9:11"],
    "was_repaired": false
  }
}
```

### Repair Strategies

When risky claims are detected:

1. **Anchor Strategy** (preferred) - Attach supporting evidence
   - Searches session context, library cache, reference cache
   - Time budget: ≤250ms (fast) or ≤800ms (deep)

2. **Rewrite Strategy** - Minimal sentence softening
   - "This proves" → "This strongly suggests"
   - "Beyond doubt" → "With high confidence"

3. **Clarify Strategy** - Flag for manual improvement
   - Used when hedges obscure the thesis

### Configuration

Rules are configured in `api/config/epistemic_rules.yml`:

```yaml
risky_phrases:
  high_risk:
    - "this proves"
    - "without question"
  medium_risk:
    - "certainly"
    - "always"

contested_markers:
  theology:
    - "election"
    - "predestination"
    - "atonement"

topic_contestation:
  "Romans 9 election":
    level: "C2"
    positions:
      - "Corporate election (New Perspective)"
      - "Individual unconditional (Reformed)"
      - "Based on foreknowledge (Arminian)"

allowed_absolutes:
  - pattern: "there are \\d+ (files|items|tasks)"
    reason: "deterministic count"

hedge_tokens:
  - "maybe"
  - "possibly"
  - "perhaps"

max_hedges_per_sentence: 2

anchor_settings:
  fast_budget_ms: 250
  deep_budget_ms: 800
  sources:
    - "session_context"
    - "library_cache"
    - "reference_cache"
```

### UI Components

**EpistemicBadge** - Progressive disclosure:
1. **Badge only** (always visible) - Small icon indicating answer type
2. **Popover** (hover/tap) - Description + contestation info
3. **Expanded** (click "Why?") - Alternative positions listed

### Backend Services

```
api/services/epistemic/
├── __init__.py           # Module exports, main entry point
├── config_loader.py      # YAML rules loading with caching
├── classifier.py         # Four-tier answer classification
├── linter.py             # Confidence linting (certainty/clarity)
├── anchor_service.py     # Evidence search within time budget
├── repair_service.py     # Minimal claim fixes
└── pipeline.py           # Main orchestration
```

### Database

Messages table includes `epistemic_json` column for storing classification metadata with each assistant message.

---

## Focus Mode

Focus Mode provides a distraction-free, voice-first interface for interacting with Tamor. It's designed for situations where the full panel layout is unnecessary or overwhelming.

### Core Concepts

- **Voice-First**: Large microphone button as primary input method
- **Minimal Chrome**: Only project indicator and exit button visible
- **Full-Screen Overlay**: Replaces the entire app interface when active
- **Conversation Continuity**: Shares context with main app (same conversation, project)

### Entering Focus Mode

**From Header:**
- Click the ◉ button in the app header (visible on all screen sizes)

**From Settings:**
- Navigate to Settings → Focus Mode → "Enter" button

**Programmatically:**
```jsx
import { useFocusMode } from './contexts/FocusModeContext';

const { enterFocusMode, toggleFocusMode } = useFocusMode();
enterFocusMode();  // or toggleFocusMode();
```

### Exiting Focus Mode

- **Keyboard**: Press `Escape` key (if allowEscape setting is true)
- **Button**: Click the × button in the top-right corner
- **Programmatically**: Call `exitFocusMode()` from context

### Settings

Focus Mode settings are persisted to localStorage and accessible from the Settings panel:

| Setting | Default | Description |
|---------|---------|-------------|
| `voiceFirst` | `true` | Show large mic button as primary input |
| `autoEnterOnMobile` | `false` | Automatically enter Focus Mode on mobile devices |
| `showProjectIndicator` | `true` | Display current project name in header |
| `allowEscape` | `true` | Allow Escape key to exit Focus Mode |

### Using Focus Mode Settings

```jsx
import { useFocusMode } from './contexts/FocusModeContext';

function MyComponent() {
  const { focusSettings, updateFocusSettings } = useFocusMode();

  // Read settings
  console.log(focusSettings.voiceFirst);

  // Update settings
  updateFocusSettings({ voiceFirst: false });
}
```

### UI Components

#### FocusMode Component

The main Focus Mode interface (`ui/src/components/FocusMode/FocusMode.jsx`):

```jsx
<FocusMode
  projectName="My Project"           // Optional: displayed in header
  activeConversationId={123}         // Optional: loads existing conversation
  currentProjectId={456}             // Optional: project context for new messages
  activeMode="Auto"                  // Chat mode (Auto, Scholar, etc.)
  onConversationCreated={(id) => {}} // Callback when new conversation created
/>
```

#### Visual States

1. **Welcome**: "Ready" message with "Speak or type your question"
2. **Listening**: Mic button pulsing red, live transcript displayed
3. **Thinking**: Animated dots with "Thinking..." text
4. **Response**: Last assistant message displayed with read-aloud button

### Voice Integration

Focus Mode uses the existing voice hooks:

- **useVoiceInput**: Speech-to-text via Web Speech API
- **useVoiceOutput**: Text-to-speech for reading responses

When `voiceFirst` is enabled:
- Responses are automatically read aloud after receiving
- Mic button is prominently displayed
- Text input is available as fallback

### File Structure

```
ui/src/
├── contexts/
│   └── FocusModeContext.jsx    # State management, localStorage persistence
├── components/
│   └── FocusMode/
│       ├── FocusMode.jsx       # Main component
│       └── FocusMode.css       # Styling
```

### Mobile Considerations

Focus Mode is particularly useful on mobile where:
- Screen space is limited
- Voice input is natural
- Touch targets need to be large

The `autoEnterOnMobile` setting (when enabled) will automatically activate Focus Mode when the app loads on a mobile device.

---

## Progressive Web App (PWA)

Tamor is installable as a Progressive Web App on desktop and mobile devices, providing a native-like experience with offline capabilities.

### Installation

**Desktop (Chrome, Edge):**
1. Visit Tamor in browser
2. Click the install icon in the address bar, or
3. Wait for the install prompt (appears after 3 seconds for first-time users)
4. Click "Install"

**Android:**
1. Visit Tamor in Chrome
2. Tap "Add to Home Screen" when prompted, or
3. Open Chrome menu → "Add to Home screen"

**iOS Safari:**
1. Visit Tamor in Safari
2. Tap the Share button (⬆️)
3. Select "Add to Home Screen"
4. Tap "Add"

### Offline Capabilities

PWA caching ensures Tamor remains usable with limited connectivity:

| Resource Type | Strategy | Cache Duration | Behavior |
|---------------|----------|----------------|----------|
| API calls | NetworkFirst | 5 minutes | Try network, fall back to cache |
| Images | CacheFirst | 30 days | Use cache, update in background |
| Fonts | CacheFirst | 1 year | Use cache, update in background |
| JS/CSS | StaleWhileRevalidate | 7 days | Use cache while fetching update |

### Update Handling

When a new version is deployed:
1. Service worker detects the update
2. `UpdateNotification` component appears
3. User can choose "Update Now" or "Later"
4. "Update Now" activates new service worker and reloads

### Install Prompt

The `InstallPrompt` component provides a friendly UX for first-time users:

- **Android/Desktop**: Captures `beforeinstallprompt` event, shows native install button
- **iOS Safari**: Shows manual instructions with share icon
- **Dismissal**: Remembers user choice for 7 days
- **Already installed**: Prompt is hidden when running as PWA

### Utility Functions

```javascript
import {
  isInstalledPWA,
  isOnline,
  onOnlineStatusChange
} from './pwa/registerSW';

// Check if running as installed PWA
if (isInstalledPWA()) {
  console.log('Running as standalone app');
}

// Check network status
if (isOnline()) {
  console.log('Connected to network');
}

// Listen for connectivity changes
const cleanup = onOnlineStatusChange((online) => {
  console.log(online ? 'Back online' : 'Gone offline');
});
// Later: cleanup();
```

### File Structure

```
ui/
├── public/
│   ├── manifest.json           # PWA manifest
│   ├── sw.js                   # Generated service worker
│   └── icons/
│       ├── icon.svg            # Source SVG
│       ├── icon-72x72.png      # iOS, Android
│       ├── icon-96x96.png
│       ├── icon-128x128.png
│       ├── icon-144x144.png
│       ├── icon-152x152.png    # iPad
│       ├── icon-192x192.png    # Android
│       ├── icon-384x384.png
│       └── icon-512x512.png    # Splash screens
├── src/
│   ├── pwa/
│   │   └── registerSW.js       # SW registration & utilities
│   └── components/
│       ├── UpdateNotification/
│       │   ├── UpdateNotification.jsx
│       │   └── UpdateNotification.css
│       └── InstallPrompt/
│           ├── InstallPrompt.jsx
│           └── InstallPrompt.css
└── vite.config.js              # PWA plugin configuration
```

### Manifest Configuration

Key manifest.json settings:

```json
{
  "name": "Tamor",
  "short_name": "Tamor",
  "description": "Personal AI workspace for research and knowledge",
  "start_url": "/",
  "display": "standalone",
  "theme_color": "#1a1a2e",
  "background_color": "#0f0f1a",
  "shortcuts": [
    { "name": "New Conversation", "url": "/?action=new" },
    { "name": "Focus Mode", "url": "/?mode=focus" }
  ]
}
```

### iOS Considerations

iOS requires additional meta tags in `index.html`:

```html
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Tamor">
<link rel="apple-touch-icon" href="/icons/icon-152x152.png">
```

---

## Integrated Reader

The Integrated Reader provides a unified reading interface for long-form content with local text-to-speech capabilities. It integrates as an expandable right panel mode, allowing you to read while still having access to chat with Tamor.

### Core Features

- **Visual Reading**: Clean typography with adjustable font size and line spacing
- **Audio Reading**: Local TTS via Piper (fully offline, no cloud services)
- **Speed Control**: Adjust playback speed (0.75x to 2.0x) via browser playbackRate
- **Auto-Advance**: Automatically plays through all chunks; preloads 5 chunks ahead
- **Progress Tracking**: Resume where you left off (visual and audio)
- **Bookmarking**: Mark positions with visual indicators on progress bar
- **Dual Mode**: Read visually, listen via audio, or both simultaneously
- **View Original**: Open original PDF in browser for scanned documents with poor text extraction

### Opening the Reader

Click the "Read" button (book icon) on any file in:
- **Library Tab**: Opens library files in the reader
- **Files Tab**: Opens project files in the reader

When opened, the right panel expands to ~55% width while chat remains visible at ~45%.

### API Endpoints

#### Content & Sessions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/reader/content/<type>/<id>` | GET | Get content for reading |
| `/api/reader/session` | POST | Get or create reading session |
| `/api/reader/session/<id>/progress` | POST | Update session progress |
| `/api/reader/session/<id>/complete` | POST | Mark session complete |
| `/api/reader/sessions` | GET | List user's reading sessions |

#### Bookmarks

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/reader/session/<id>/bookmarks` | GET | Get session bookmarks |
| `/api/reader/session/<id>/bookmarks` | POST | Add bookmark |
| `/api/reader/session/<id>/bookmarks/<bookmark_id>` | DELETE | Remove bookmark |

#### Audio (TTS)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/reader/tts/synthesize` | POST | Synthesize text to audio |
| `/api/reader/tts/chunk` | POST | Synthesize single chunk |
| `/api/reader/tts/status` | GET | Get Piper TTS status |
| `/api/reader/tts/voices` | GET | List available voices |
| `/api/reader/audio/<filename>` | GET | Serve cached audio file |

#### Reading Stats

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/reader/stats` | GET | Get user's reading statistics |

### Piper TTS Setup

Install Piper and download voice models using the setup script:

```bash
# Install default voice (en_US-lessac-medium)
python scripts/setup_piper.py

# List available voices
python scripts/setup_piper.py --list-voices

# Install specific voices
python scripts/setup_piper.py --voices en_US-amy-medium,en_GB-alba-medium

# Install all voices
python scripts/setup_piper.py --voices all

# Validate installation
python scripts/setup_piper.py --validate-only
```

### Available Voices

| Voice | Language | Gender | Quality |
|-------|----------|--------|---------|
| en_US-lessac-medium | American English | Neutral | Medium (default) |
| en_US-lessac-high | American English | Neutral | High |
| en_US-amy-medium | American English | Female | Medium |
| en_US-amy-low | American English | Female | Low |
| en_US-ryan-medium | American English | Male | Medium |
| en_US-ryan-high | American English | Male | High |
| en_US-joe-medium | American English | Male | Medium |
| en_GB-alba-medium | British English | Female | Medium |
| en_GB-aru-medium | British English | Male | Medium |
| en_GB-cori-medium | British English | Female | Medium |
| de_DE-thorsten-medium | German | Male | Medium |
| es_ES-davefx-medium | Spanish | Male | Medium |
| fr_FR-siwis-medium | French | Female | Medium |

### Keyboard Shortcuts (in Reader)

| Key | Action |
|-----|--------|
| `Space` | Play/pause audio |
| `Escape` | Close reader |
| `Ctrl+B` | Add bookmark at current position |
| `Ctrl+F` | Toggle fullscreen |
| `Ctrl++` / `Ctrl+-` | Increase/decrease font size |

### UI Integration

The reader uses an expandable right panel design:
- Normal mode: Standard right panel tabs
- Reader mode: Panel expands to 55% width
- Chat panel shrinks but remains visible and usable
- Allows asking Tamor questions about what you're reading

### Content Support

| Type | Source | Support |
|------|--------|---------|
| `library` | Library files | Full text extraction |
| `file` | Project files | Full text extraction |
| `transcript` | Transcriptions | Timestamped segments |

### Example: Read a Library File

```javascript
import { useReaderContext } from '../context/ReaderContext';

function MyComponent() {
  const { openReader } = useReaderContext();

  const handleRead = (fileId, filename) => {
    // Opens reader with library file, both visual and audio modes
    openReader('library', fileId, 'both', filename);
  };

  return <button onClick={() => handleRead(42, 'document.pdf')}>Read</button>;
}
```

### Architecture

```
Backend Services:
├── api/services/tts_service.py      # Piper TTS wrapper
├── api/services/reader_service.py   # Content & session management
└── api/routes/reader_api.py         # 18 REST endpoints

Frontend:
├── ui/src/components/Reader/
│   ├── ReaderView.jsx               # Main reader component
│   ├── ReaderControls.jsx           # Audio playback controls
│   ├── Reader.css                   # Reader styles
│   └── index.js                     # Exports
├── ui/src/context/ReaderContext.jsx # Global reader state
└── ui/src/hooks/useReader.js        # Reader state & audio logic

Storage:
├── /mnt/library/piper_voices/       # Voice model files (.onnx)
└── api/data/tts/cache/              # Cached audio chunks
```

---

*Last updated: 2026-02-01 (v1.42 - Reader improvements, search mode toggle)*
