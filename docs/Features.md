# Tamor Features Guide

This document provides a reference for Tamor's major features, their APIs, and usage patterns.

---

## Table of Contents

1. [Global Library System](#global-library-system)
2. [Reference Integration](#reference-integration)
3. [Multi-Agent System](#multi-agent-system)
4. [Memory System](#memory-system)
5. [Plugin Framework](#plugin-framework)
6. [Project Pipelines](#project-pipelines)
7. [Auto-Insights & Reasoning](#auto-insights--reasoning)
8. [Media & Transcription](#media--transcription)

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

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/library/search` | POST | Semantic search across library |
| `/api/library/search/file/<id>` | GET | Search within specific file |
| `/api/library/<id>/similar` | GET | Find similar files |

**Search Request Body:**
```json
{
  "query": "search text",
  "scope": "library",      // "library", "project", or "all"
  "project_id": 13,        // Required if scope is "project" or "all"
  "limit": 10,
  "min_score": 0.4,
  "file_types": ["application/pdf"]
}
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

Specialized agents handle different types of requests.

### Available Agents

| Agent | Purpose | Triggers |
|-------|---------|----------|
| **Researcher** | Source gathering, structured analysis | "research", "analyze", "find", "compare" |
| **Writer** | Prose synthesis from research | "write", "draft", "compose" |
| **Engineer** | Code generation with project awareness | "implement", "fix", "create function" |
| **Archivist** | Memory management | "remember", "forget", "I prefer" |

### How Routing Works

1. Intent is classified using pattern matching
2. Agent sequence is selected based on intent
3. For research/writing: Researcher → Writer pipeline
4. For code with project context: Researcher → Engineer
5. Simple queries fall through to single LLM call

### Debug Trace

Add `?debug=1` or header `X-Tamor-Debug: 1` to see routing decisions:

```json
{
  "router_trace": {
    "trace_id": "abc123",
    "route_type": "agent_pipeline",
    "intents_detected": ["research", "summarize"],
    "agent_sequence": ["researcher", "writer"],
    "retrieval_used": true,
    "retrieval_count": 15
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
   - ZIP Download, JSON Export

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
| `/api/library/transcription/queue` | GET | List queue items with status |
| `/api/library/transcription/queue/stats` | GET | Queue statistics |
| `/api/library/transcription/queue/add` | POST | Add file to queue |
| `/api/library/transcription/queue/<id>` | DELETE | Remove from queue |
| `/api/library/transcription/candidates` | GET | Files without transcripts |
| `/api/library/transcription/candidates/queue-all` | POST | Queue all candidates |
| `/api/library/transcription/process/next` | POST | Process next queue item |
| `/api/library/transcription/process/batch` | POST | Process batch of items |
| `/api/library/transcription/<file_id>/transcript` | GET | Get transcript for library file |

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
curl -X POST http://localhost:5055/api/library/transcription/candidates/queue-all \
  -H "Content-Type: application/json" \
  -d '{"model": "base"}'

# Process next item in queue
curl -X POST http://localhost:5055/api/library/transcription/process/next
```

### Background Worker

Run the transcription worker as a background service:

```bash
# Run continuously (polls every 60 seconds)
python -m scripts.run_transcription_worker --interval 60

# Process one item and exit
python -m scripts.run_transcription_worker --once

# Process batch of 10 items
python -m scripts.run_transcription_worker --batch 10
```

Systemd service file available at `api/scripts/tamor-transcription.service`

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

*Last updated: 2026-01-24 (v1.27)*
