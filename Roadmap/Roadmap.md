Tamor Development Roadmap

Project: Tamor
Purpose: Personal AI workspace for research, knowledge management, reasoning, and assisted creation
Scope Constraint: This roadmap applies only to Tamor.
Business- or employer-specific systems (e.g., Anchor Assistant) are intentionally excluded.

Overview

This document defines the authoritative roadmap for Tamor.
It is intentionally stable, versioned, and slow-changing.

New ideas must first pass through the companion document:

Tamor – Roadmap Extensions & Proposals

Only approved, scoped items are promoted here.

Phase 1 – Core System (Completed)

Backend foundational architecture (Flask, Gunicorn)

Project + conversation model

File upload system

Embedding pipeline + memory databases

Core React UI (Left / Chat / Right panels)

Cloudflare Tunnel + HTTPS (Caddy)

Local-first deployment model

Phase 2 – Intelligence Upgrade (Mostly Completed)
2.1 Semantic Multi-File Search

File chunking and embeddings

Cross-file semantic search endpoint

UI integration with result navigation

2.2 Project Summaries

Cross-file summarization

Structured summaries

“Send to chat” workflow

2.3 Knowledge Graph (Initial)

Symbol extraction

Knowledge database

Knowledge tab UI

2.4 File Parsing Stability

PDF / DOCX / XLSX / EPUB parsing

Error handling and resilience

Parsing normalization

2.5 UI Polishing

RightPanel redesign

CSS cleanup

Improved interactions

2.6 Structured Tasking (Mostly Complete)

✅ Task database schema and API endpoints

✅ Reminder detection from chat messages

✅ Task confirmation/cancel/complete/pause/resume workflows

✅ Task deletion and editing (title, scheduled time)

✅ TaskPill (chat) and TasksPanel (sidebar) UI

⬜ Detect tasks embedded in project content (deferred to Phase 4.x)

Phase 3 – Stability, Cleanup, and Refactoring (Complete)
3.1 Backend Refactor & Deterministic Safety (Complete)

✅ Remove legacy and dead code

✅ Standardize API error responses (utils/auth.py, utils/errors.py)

✅ Add /health endpoint (database + LLM status checks)

✅ Review and align migrations (schema.sql updated, migration runner fixed)

✅ LLM Provider Abstraction Layer:

✅ Create unified LLM service interface (services/llm_service.py)

✅ Centralize client initialization and configuration

✅ Enable future multi-provider support (Phase 6.2 dependency)

✅ Deterministic Safety Enforcement:

✅ core/deterministic.py module with DeterministicResult pattern

✅ Explicit separation between deterministic and LLM responses

✅ Hard-stop rules: deterministic queries never fall through to LLM

✅ Chat flow integration for count/list queries

3.2 UI Refactor (Complete)

✅ RightPanel state cleanup

✅ Remove unused components (8 backup/copy files deleted)

✅ Fix scrolling and viewport issues

✅ Introduce global CSS tokens (standardized theming across all CSS)

✅ Improve mobile and accessibility foundations (focus-visible, reduced-motion, touch targets)

3.3 Database Cleanup (Complete)

✅ Align migrations with live schema (000_baseline.sql)

✅ Add migration version tracking (migrations table with history, checksums)

✅ Add rollback and validation utilities (run_migrations.py, db_validate.py)

3.4 Interface Restoration (In Progress)

Align the UI with Tamor's core philosophy (Wholeness • Light • Insight). Simplify the default experience, add voice interaction, and make mobile a first-class citizen.

**Guiding Principles:**
- Every UI element must earn its place — if it doesn't serve the current task, hide it
- Mobile is not a smaller desktop — design for touch and voice first, expand for desktop
- Depth on demand — simple by default, powerful when needed
- Developer tools are not user tools — separate concerns cleanly

3.4.1 UI Audit & Developer Mode (Complete)

✅ Audit all components in ui/src/components/

✅ Categorize each as: Essential | Power User | Developer Only

✅ Create DevModeContext for toggling developer UI

✅ Wrap developer-only elements in conditional rendering (TasksPanel, StructurePanel)

✅ Remove dead code (MemoryList, MemoryCard, memory.css, MemoryList.css)

✅ Settings page includes "Developer Mode" toggle (off by default)

3.4.2 Mobile-First Layout Refactor (Complete)

✅ Responsive breakpoint system (Mobile < 768px, Tablet 768-1024px, Desktop > 1024px)

✅ useBreakpoint hook for responsive logic

✅ MobileNav component (bottom navigation: Chat, Projects, Settings)

✅ Drawer component (reusable slide-in panels with focus trap, scroll lock)

✅ Layout behavior by breakpoint:
  - Mobile: Slide-out drawers, Full screen chat, Bottom navigation
  - Tablet: Collapsible sidebars with header toggle buttons
  - Desktop: Fixed three-panel layout

✅ Touch targets minimum 44px throughout

✅ RightPanel tab grouping for mobile (Essential | Research ▼ | Tools ▼)

✅ Tools button in mobile chat header for RightPanel access

3.4.3 Voice Input/Output (Complete)

✅ useVoiceInput hook (Web Speech API speech-to-text)

✅ useVoiceOutput hook (Web Speech API text-to-speech)

✅ VoiceButton component with visual states (idle, listening, error)

✅ Mic button in chat input (prominent, easy to tap)

✅ Visual feedback during listening (pulse animation, live transcript preview)

✅ "Read aloud" button on assistant messages (hover on desktop, visible on mobile)

✅ VoiceSettingsContext for app-wide voice preferences

✅ Voice settings in Settings page (enable/disable, voice selection, speech rate, auto-read)

✅ Graceful degradation when Speech API unavailable

✅ Auto-read responses option

3.4.4 Focus Mode (Complete)

✅ Single-screen chat, no panels

✅ Large central mic button

✅ Minimal chrome (project indicator + settings access only)

✅ Easy toggle in/out of Focus Mode

> Note: Completed in Phase 8.3

**Success Criteria:**
- ✅ New user sees clean, simple chat interface by default
- ✅ Mobile experience is native-feeling (bottom nav, appropriate sizing)
- ✅ Voice input/output works reliably on iOS Safari and Android Chrome
- ✅ Developer tools accessible but hidden by default
- ✅ Interface embodies Tamor: calm, purposeful, illuminating

3.5 Reference Integration (Local-First) (Complete)

Integrate biblical and scholarly reference sources into Tamor, enabling grounded research with clear source attribution.

**Philosophy: Local Independence**
- SWORD modules — Bible translations stored locally, no API calls
- Sefaria caching — API for Jewish texts, but aggressively cached locally
- Single data directory — easy migration to NAS when ready
- Offline capable — works without internet for cached/local content

**Storage Structure:**
```
{TAMOR_REFERENCE_PATH}/          # Default: /home/tamor/data/references/
├── sword/                       # SWORD root directory
│   ├── mods.d/                  # Module configuration files
│   └── modules/texts/           # Module data (~50-100MB typical)
├── sefaria_cache/               # Cached Sefaria responses
└── config.json                  # Module preferences, enabled translations
```

3.5.1 Storage & Module Management (Complete)

✅ Create reference data directory structure (storage.py)

✅ SWORD module downloader (fetch from CrossWire)

✅ Module configuration (enable/disable translations)

✅ pysword integration for reading modules

✅ Setup script for downloading modules (scripts/setup_references.py)

3.5.2 SWORD Client (Complete)

✅ Read passages from local modules

✅ List available/enabled translations

✅ Search within modules (basic keyword)

✅ Compare translations locally

3.5.3 Sefaria Client with Caching (Complete)

✅ API client for Sefaria

✅ File-based cache for responses

✅ TTL-based expiration with offline fallback to expired cache

✅ Cache management (stats, clear)

3.5.4 Unified Reference Service (Complete)

✅ Combined interface for both sources (reference_service.py)

✅ Reference parser with 200+ book abbreviations (reference_parser.py)

✅ API endpoints: /api/references/lookup, /compare, /search, /detect, /commentary, /cross-references, /translations, /modules/*, /book/*, /cache/*

3.5.5 Frontend Integration (Complete)

✅ CitationCard component (compact/expanded modes, Hebrew RTL, copy/compare actions)

✅ ReferencesTab in RightPanel (lookup, compare translations, recent history, module management)

✅ Chat citation display (auto-detect references in messages, fetch and display CitationCards)

✅ LLM context injection (inject actual passage text into system prompt for grounded responses)

**Reference Sources:**
- SWORD Modules: KJV, NASB, ESV, WEB, YLT, ASV, OSHB (Hebrew), LXX (Greek)
- Sefaria: Tanakh, Talmud, Midrash, Mishnah, commentaries

**Offline Behavior:**
| Source | Online | Offline |
|--------|--------|---------|
| SWORD modules | ✅ Full | ✅ Full |
| Sefaria (cached) | ✅ Fresh + cached | ✅ Cached only |
| Sefaria (not cached) | ✅ Fetch + cache | ❌ Unavailable |

**Success Criteria:**
- Bible translations available locally (SWORD)
- Works fully offline for Bible lookups
- Sefaria content cached locally after first fetch
- User can compare translations instantly
- Citations display clearly in chat
- Storage easily movable to NAS (env var or symlink)
- Hebrew text displays correctly

Phase 4 – Research & Intelligence Expansion
4.1 Auto-Insights Engine (Complete)

✅ Auto-generate insights on file text extraction (lazy, on-demand)

✅ Detect themes, contradictions, missing info, and assumptions via LLM

✅ Cache insights in file_insights table

✅ API endpoints: GET /files/{id}/insights, GET /projects/{id}/insights

✅ Project-level aggregation with file attribution

4.2 Multi-File Reasoning Mode (Complete)

✅ Cross-document relationship analysis (dependencies, references)

✅ Cross-file contradiction detection

✅ Logic flow and coherence checking

✅ Cached results in project_reasoning table

✅ API endpoints: GET /projects/{id}/reasoning[/relationships|contradictions|logic-flow]

4.3 On-Disk Caching Layer (Complete)

✅ Persistent embedding cache in file_chunks table

✅ Cache-first retrieval with on-demand generation

✅ Cache invalidation on project/file deletion

✅ Batch embedding with embed_many for efficiency

Phase 5 – Automation & Actions
5.1 File Actions (Complete)

✅ Rewrite files (6 modes: simplify, expand, improve, restructure, technical, executive)

✅ Generate specs (formal specification documents from content)

✅ Parameter extraction (extract config values with structured output)

✅ API endpoints: POST /files/{id}/rewrite, /generate-spec, /extract-parameters

5.2 Project Pipelines (Complete)

✅ Pipeline templates: Research, Writing, Study, Long-form

✅ State tracking with step progress and notes

✅ Step guidance with available actions

✅ LLM-generated progress summaries

✅ API: GET /pipelines, /projects/{id}/pipeline[/start|advance|abandon|reset|guidance|summary]

5.3 Media & Transcript Integration (Complete)

✅ YouTube/URL download via yt-dlp

✅ Audio/video transcription via faster-whisper

✅ Timestamped segments with full text

✅ Transcript storage and retrieval

✅ API: POST /projects/{id}/transcribe-url, GET/DELETE /transcripts, POST /files/{id}/transcribe

✅ Media tab UI in RightPanel (transcribe URLs, view/delete transcripts)

✅ PDF export for transcripts with timestamps

5.4 Feature UI Integration (Complete)

UI exposure for backend services from Phases 4-5:

✅ Auto-Insights UI (Phase 4.1):

✅ Dedicated Insights tab in RightPanel

✅ Summary view (aggregated) and By File view

✅ Display themes, contradictions, missing info, assumptions

✅ Multi-File Reasoning UI (Phase 4.2):

✅ Dedicated Reasoning tab in RightPanel

✅ Three views: Relationships, Contradictions, Logic Flow

✅ Trigger analysis from UI with coherence scoring

✅ File Actions UI (Phase 5.1):

✅ Actions panel in Files tab (expandable per file)

✅ Rewrite with mode selector (6 modes)

✅ Generate Spec and Extract Parameters buttons

✅ Result display with copy functionality

✅ Project Pipelines UI (Phase 5.2):

✅ PipelinePanel in WorkspaceTab

✅ Template selector (Research, Writing, Study, Long-form)

✅ Progress bar and step visualization

✅ Step notes, advance, reset, abandon controls

5.5 Integrated Reader (Complete)

A unified reading interface for long-form content from the NAS library, project files, and transcripts. Combines visual reading with local text-to-speech.

**Visual Reader:**
- ✅ Distraction-free reading view (expandable right panel mode)
- ✅ Clean typography with adjustable font size and line spacing
- ✅ Continuous scroll with progress tracking
- ✅ Bookmarking with visual markers on progress bar
- ✅ Support for: PDFs (text extraction), transcripts, library files, project files

**Audio Reader (Piper TTS):**
- ✅ Local text-to-speech via Piper (MIT licensed, fully offline)
- ✅ Playback controls: speed (0.5x-2x), pause/resume, skip forward/back
- ✅ Chunk-based audio synthesis with preloading
- ✅ Sentence-aware text chunking for natural TTS
- ✅ Audio caching with SHA-256 cache keys

**Progress Tracking:**
- ✅ `reading_sessions` table: content_type, content_id, position, progress, mode, bookmarks
- ✅ Resume where you left off (visual and audio positions)
- ✅ Per-session bookmarks stored in JSON

**Integration:**
- ✅ "Read" button on Library files (opens reader in panel)
- ✅ "Read" button on Project files (opens reader in panel)
- ✅ Expandable right panel mode (55% width, chat stays visible)
- ✅ ReaderContext for global state management

**Backend Services:**
- ✅ `tts_service.py`: Piper TTS wrapper with chunking and caching
- ✅ `reader_service.py`: Content retrieval, session management, bookmarks
- ✅ `reader_api.py`: 18 API endpoints for reader functionality

**Setup:**
- ✅ `scripts/setup_piper.py`: CLI for installing Piper and voice models
- ✅ 13 voices available (en_US, en_GB, de_DE, es_ES, fr_FR)

**Constraints:**
- Fully offline (no cloud TTS)
- English TTS primary (other languages available)
- PDF via text extraction (not full rendering)

Phase 6 – Advanced Assistant Evolution
6.1 Long-Term Memory 2.0 (Governed Memory) (Complete)

✅ Category-based memory

✅ Searchable and pinnable memory

✅ Explicit memory governance rules:

✅ Manual vs automatic memory

✅ User consent for persistence

✅ User-visible memory controls (Memory tab in RightPanel)

6.2 Multi-Agent Support (Complete)

✅ Distinct assistant roles:

✅ Researcher: source gathering, structured analysis, citations

✅ Writer: prose synthesis from research notes

✅ Engineer: code generation following project patterns

✅ Archivist: memory governance (remember/forget commands)

✅ Task-appropriate behavior models (intent-based routing)

✅ Heuristic routing with smart project context detection

6.3 Plugin Framework (Complete)

✅ Plugin architecture with base classes and auto-discovery registry

✅ Importers: Local folder, Audio transcript, Bulk PDF

✅ Exporters: ZIP archive download, JSON data export

✅ Reference backends: Local docs folder, Web fetch (URL content)

✅ Full API endpoints for all plugin types

✅ UI with tabbed Importers/Exporters/References sections

### Phase 6.4 — Plugin Framework Expansion (Complete)

**Status:** Complete

**Purpose:** Extend Tamor's capabilities through exporters, integrations, and external content management.

#### Prioritized Items

| Priority | Item | Status | Description |
|----------|------|--------|-------------|
| 1 | **Markdown export** | ✅ | Export project conversations and notes as formatted .md files |
| 2 | **PDF export** | ✅ | Generate polished PDF reports from projects (WeasyPrint) |
| 3 | **Zotero integration** | ✅ | Read from local Zotero SQLite database |
| 4 | **Plugin config persistence** | ✅ | Store per-project plugin settings in database |
| 5 | **Reference caching/versioning** | ✅ | Cache external content with version tracking |

#### Implementation Notes

**Markdown Export**
- Export conversation history as clean markdown
- Export project notes and summaries
- Include metadata (timestamps, project name)
- Option to include/exclude system messages

**PDF Export**
- Build on markdown export
- Apply consistent styling/branding
- Support for academic formatting (citations, bibliography)
- Use weasyprint or similar for generation

**Zotero Integration**
- Read from local Zotero SQLite database (simplest)
- Or import BibTeX/CSL-JSON exports (manual but portable)
- Extract PDF text and index in library
- Make citations available for writing projects
- Future: Zotero API for cloud sync

**Plugin Config Persistence**
- Store plugin settings per project in database
- API: GET/PATCH /api/projects/{id}/plugins
- UI: Plugin settings section in project settings

**Reference Caching/Versioning**
- Cache external web content (Sefaria, articles)
- Store fetch timestamp and content hash
- Support for version comparison
- Graceful degradation when source unavailable

#### Future Consideration (Unpromoted)

These items may be promoted based on user need:

| Item | Notes |
|------|-------|
| Notion import | External knowledge base sync — if workflow demands |
| RSS/Atom feeds | Content monitoring — news, blog tracking |
| Scheduled imports | Automated ingestion — automation polish |

#### Success Criteria

- [x] Can export any project as clean markdown
- [x] Can generate PDF report from project
- [x] Can search Zotero library from Tamor (API ready, UI when needed)
- [x] Can cite Zotero references in writing (API ready)
- [x] Plugin settings persist per project
- [x] External references cached with versions

## Phase 7 – Global Library System

**Purpose:** Centralized, NAS-backed knowledge repository that serves as the single source of truth for all documents, transcripts, and media. Projects reference library items without duplication.

### 7.1 Library Schema & Core Service ✅

Database foundation for the global library:

✅ `library_files` table (id, filename, stored_path, mime_type, size_bytes, source_type, metadata_json, created_at)

✅ `library_chunks` table (id, library_file_id, chunk_index, content, embedding, page)

✅ `project_library_refs` table (project_id, library_file_id, added_at, notes)

✅ `library_service.py` with CRUD operations

✅ Reference management (add/remove library items from projects)

✅ Deduplication check on ingest (hash-based)

### 7.2 Library Ingest Pipeline ✅

Automated ingestion from configured paths:

✅ Mount point configuration (`/mnt/library` or configurable)

✅ Directory scanner (recursive, with include/exclude patterns)

✅ File type detection and routing (PDF → extract, audio → transcribe, etc.)

✅ Batch ingest with progress tracking

✅ Incremental sync (detect new/changed/deleted files)

✅ Ingest queue for large batches (background processing)

### 7.3 Library Search & Retrieval ✅

Search capabilities across the full library:

✅ LibrarySearchService with `scope` parameter (library | project | all)

✅ Library-wide semantic search with cosine similarity

✅ Hybrid search: project-first with 10% boost in 'all' scope

✅ Search result attribution (library_file_id, filename, chunk_index, page, score)

✅ LibraryContextService for chat context injection

✅ API: POST /api/library/search, GET /search/file/<id>, GET /search/similar/<id>

### 7.4 Library UI ✅

User interface for browsing and managing the library:

✅ Library tab in RightPanel (essential tabs group)

✅ Browse files with search, manage view for ingest/indexing

✅ "Add to project" action (creates reference, not copy)

✅ Ingest status and queue visibility in manage view

✅ Library statistics (file count, total size, indexed count)

✅ LibrarySettings panel (context injection preferences)

✅ ProjectLibraryRefs component (show linked library files in Files tab)

### 7.5 Transcription Queue (CPU-Optimized) ✅

Batch transcription for audio/video backlog:

✅ Transcription queue table (library_file_id, status, model, started_at, completed_at)

✅ Background worker for queue processing (TranscriptionWorker with faster-whisper)

✅ Model selection per item (tiny/base/small/medium/large-v2 for speed vs accuracy)

✅ Progress reporting and queue statistics

✅ Store transcript as library item (linked via source_library_file_id)

✅ TranscriptionQueue UI component (queue management, add candidates, model selection)

✅ Standalone worker runner script (systemd service ready)

## Phase 8 – Trust, Restraint, and Completion

**Theme:** Tamor becomes unmistakably reliable, bounded, and calm.

**Core Philosophy:** Phase 1–7 built Tamor's mind. Phase 8 defines its soul.

---

### Why Phase 8 Exists

By the end of Phase 7, Tamor is capable. Phase 8 ensures Tamor is understandable, trustworthy, and finished-feeling — to you and to any future user.

This phase is about:
- Making boundaries explicit
- Making system behavior visible
- Removing ambiguity
- Preventing future scope creep

**Phase 8 is about trust, not power.**

---

### Phase 8 Goals

1. Make Tamor's limits as clear as its abilities
2. Surface system confidence and uncertainty honestly
3. Lock in philosophical and ethical boundaries
4. Eliminate "mystery behavior"
5. Declare Tamor complete — not endless

---

### Prerequisites

Before declaring Phase 8 complete, the following must be resolved:
- **Mobile access** (APK or PWA) — a personal AI agent you can only use at your desk isn't complete ✅
- **NAS integration** (Synology DS224+) — storage architecture is infrastructure, not a feature

These are core, not extensions.

#### PWA Implementation ✅

Progressive Web App support for installable, offline-capable mobile access:

✅ **Manifest & Icons**
- `manifest.json` with app metadata, shortcuts, theme colors
- Full icon set: SVG source + PNG sizes (72, 96, 128, 144, 152, 192, 384, 512)
- iOS-specific icons and splash behavior

✅ **Service Worker**
- Vite PWA plugin with workbox caching strategies
- API: NetworkFirst (5 min cache)
- Images: CacheFirst (30 days)
- Fonts: CacheFirst (1 year)
- JS/CSS: StaleWhileRevalidate (7 days)

✅ **PWA Registration**
- `registerSW.js` with update detection
- Custom event dispatch for update notifications
- Utility functions: `isInstalledPWA()`, `isOnline()`, `onOnlineStatusChange()`

✅ **User Experience**
- `UpdateNotification` component for seamless updates
- `InstallPrompt` component with platform detection
- iOS: Manual "Add to Home Screen" instructions
- Android/Desktop: Native install prompt capture
- Smart dismissal (7-day cooldown after dismissal)

---

### 8.1 Tamor Principles & Boundaries Manifesto ✅

**Purpose:** Formally document what Tamor will never do, even if it technically could.

#### Deliverables

- ✅ `docs/BOUNDARIES.md` (user-readable)
- ⬜ Short in-app "What Tamor Is / Is Not" page
- ⬜ Linked from Settings

#### Boundaries

- ❌ No autonomous actions without consent
- ❌ No silent memory persistence
- ❌ No scraping private systems
- ❌ No pretending certainty where none exists
- ❌ No replacing human judgment, conscience, or authority

**Why this matters:** This locks Tamor's character, not just its code.

---

### 8.2 Epistemic Honesty System ✅

**Purpose:** Unified system for truth signaling — combining provenance transparency, confidence enforcement, and user-facing indicators into one coherent honesty layer.

#### Implementation Status

✅ **Backend Services** (`api/services/epistemic/`)
- `config_loader.py` - YAML rules configuration
- `classifier.py` - Four-tier answer classification
- `linter.py` - Confidence linting (certainty/clarity)
- `anchor_service.py` - Evidence attachment with time budget
- `repair_service.py` - Minimal claim fixes
- `pipeline.py` - Main orchestration

✅ **Configuration** (`api/config/epistemic_rules.yml`)
- Risky phrases (high/medium risk)
- Six contested domains with markers
- Manual topic contestation mappings (C1/C2/C3)
- Allowed absolutes patterns
- Hedge detection settings
- Anchor search budgets

✅ **Chat Integration** (`api/routes/chat_api.py`)
- Epistemic processing on all responses
- Metadata included in JSON response
- Stored in messages table (epistemic_json column)

✅ **UI Components** (`ui/src/components/Chat/`)
- `EpistemicBadge.jsx` - Badge with progressive disclosure
- Popover with contestation details
- Mobile-responsive (tap for modal)

> **Design Note:** This section merges the original 8.2 (Deterministic vs Probabilistic Transparency) and 8.3 (Confidence Language Enforcement) into a single integrated design. The separation was artificial; they're one system.

#### 8.2.1 Answer Classification (Four-Tier Model)

Every response is classified by provenance:

| Category | Definition | Example |
|----------|------------|---------|
| **Deterministic** | Computed, exact, from trusted data | "There are 12 items." / "Your next reminder is at 3:15 PM." |
| **Grounded–Direct** | Restating or summarizing explicit text | "Paul says X, then Y." / "Jeremiah 7 describes..." |
| **Grounded–Contested** | Grounded in text but interpretive, with live disagreement | "Romans 9 is about corporate election, not individual predestination." |
| **Ungrounded Synthesis** | No anchors, purely inferential | General reasoning without source backing |

**Key rule:** Grounded–Contested is not "less true." It means the claim requires a stated interpretive frame.

#### 8.2.2 Contested Domains (v1)

Six domains where contestation detection is active:

1. **Theology / doctrinal conclusions**
2. **Historical reconstruction** beyond explicit sources
3. **Authorship/dating debates**
4. **Prophecy interpretations**
5. **Denominational distinctives**
6. **Ethical application / contemporary mapping** *(added based on design review)*

##### Ethical Application Domain

Flag patterns:
- "Scripture clearly teaches X about modern issue Y"
- "Therefore Christians must/should support/oppose…"
- "This passage proves we should do policy/action Y"
- "If you disagree, you're disobeying Scripture" (high severity)

**Why separate from theology?** Even when doctrine is agreed, application can be contested:
- Same text, different prudential judgments
- Same principle, different real-world constraints
- Same moral aim, different means

**Behavior in this domain:** Show the bridge explicitly:
1. What the text says (Grounded–Direct)
2. What principle is being inferred (Grounded–Contested often)
3. What assumptions map to modern issue Y (often ungrounded/prudential)
4. What other faithful applications exist

#### 8.2.3 Contestation Intensity Scale

Three levels (shown only when relevant, not by default):

| Level | Name | Meaning |
|-------|------|---------|
| **C1** | Intra-tradition nuance | Disagreement within the same broad interpretive family |
| **C2** | Cross-tradition split | Major traditions diverge (Reformed vs Arminian, Catholic vs Protestant, etc.) |
| **C3** | Minority/novel position | Legitimate but not widely held historically or academically |

**Key insight:** Contestation is relative to declared lens. A Torah-observant Messianic reading isn't C3 within that tradition.

##### v1 Implementation: How to Determine C1/C2/C3

1. **Manual overrides** (best for recurring topics)
   - Small mapping file for: Romans 9 election, Law/Grace frameworks, Eschatology schemas, Israel/Church identity, Torah observance debates

2. **Rule-based defaults**
   - Claim asserts "the" interpretation / "clearly teaches" → bump to C2
   - Claim contradicts multiple mainstream frames → bump to C3 unless user has declared that frame as primary

3. **Project lens**
   - If project declares a lens (e.g., "Foundations / Torah frame"), system marks it as "Primary lens for this workspace"
   - Reduces friction while acknowledging alternatives

#### 8.2.4 Confidence Language Enforcement

**Core principle:** Don't enforce "confidence language." Enforce "confidence claims."

We don't prescribe how Tamor must sound; we prevent it from making invalid certainty assertions.

##### What We Prevent
- "This proves…", "It's definitely…", "Always…", "Never…"
- Hard factual claims without deterministic backing or cited text

##### What We Do NOT Do
- Auto-insert "Based on available information…" everywhere
- Rewrite tone
- Add hedges to everything

##### Two Lint Dimensions

1. **Certainty posture vs provenance**
   - Absolute phrasing allowed if: Deterministic, OR Grounded–Direct with anchor, OR matches Allowed Absolutes

2. **Clarity erosion**
   - Flag sentences with 3+ hedge tokens and no thesis
   - "Maybe possibly seems like could suggest" is evasive, not honest

##### Risky Claim Patterns (Configurable)

`config/epistemic_rules.yml`:
- `risky_phrases`: absolutist verbs (proves, refutes, settles, definitely)
- `theology_contested_markers`: "the real meaning," "clearly teaches," "is about corporate election"
- `allowed_absolutes`: facts allowed in certain contexts
- `domain_overrides`: per project (teaching vs engineering vs general)

**The guardrails are governed, not "the model decided."**

##### Repair Strategies (Only When Needed)

**Strategy A (preferred): Anchor, don't hedge**
- If Tamor can pull an anchor quickly, attach evidence and keep confident tone
- Best outcome: honest + natural

**Strategy B: Minimal sentence rewrite**
- Only the offending sentence, not global tone
- "This proves X" → "This strongly suggests X"
- "It's definitely X" → "It appears to be X"

**Strategy C: Clarifying question**
- For high-stakes ungrounded claims
- "Do you mean X or Y?" or "Do you want sources, or a best-guess explanation?"

##### Latency Budget

- **Fast anchor pass (≤150–250ms):** Use cached sources only
  - Project file chunks already retrieved this session
  - Library context injection cache
  - Recent reference lookups (SWORD/Sefaria cache)
- **Deeper anchor pass (≤500–800ms):** Only if claim is high-risk AND user has "accuracy > speed" preference
- **Fallback:** If anchor not found in budget, use Grounded–Contested framing or minimal rewrite

#### 8.2.5 UI Design: Progressive Disclosure

**Design principle:** Most users should sense contestation before they ever read about it.

##### Primary Signal: Single Calm Badge (Always Present)

Near timestamp or message footer:
- ✔︎ Deterministic
- ● Grounded
- ◐ Contested

No C1/C2/C3 exposed at this level. Badge answers: "What kind of answer is this?"

##### Secondary Signal: Contestation Detail (On Intent)

**Desktop:** Hover on Contested badge
**Mobile:** Long-press

Popover content:
```
Contested interpretation
Level: Cross-tradition (C2)

Meaning:
Major Christian traditions interpret this passage differently.

This response reflects:
• Primary lens: [Project lens or default]
• Notable alternatives: [short labels only]
```

##### Tertiary Signal: Expandable Explanation

Inside popover, "Why?" link expands to 2–4 bullet summary:
```
Why this is contested:
• Some read Romans 9 as addressing corporate identity (Israel/Gentiles).
• Others read it as individual election tied to salvation.
• Both readings appeal to different sections of the chapter.
```

##### Intensity Visibility Rules

- **C1:** Only visible inside popover
- **C2:** Visible in popover header
- **C3:** Visible and lightly emphasized ("Minority position" label)

##### Ethical Application: Extra Affordance

Same Contested badge, but popover includes labeled divider:
```
This response includes:
• Textual interpretation
• Ethical application (modern context)

Faithful readers may agree on the text while differing on application.
```

##### Badge Fatigue Prevention

1. **Follow-up suppression:** In contested threads, badge dims or shows only on first message
2. **Project defaults:** Setting "Assume declared lens unless noted" — badge still exists but explanatory text adapts: "Within this project's framework, this is a standard reading."

#### 8.2.6 Target Voice Example

**User:** "Was Paul's argument in Romans 9 about individual or corporate election?"

**Bad (overconfident):** "It was definitely about corporate election."

**Bad (formulaic):** "Based on the available information, it is possible that some scholars believe..."

**Good (Phase 8 voice):**
> My reading: Paul's argument in Romans 9 is primarily about God's covenant purposes and the identity of God's people (a "corporate election" lens), not a philosophical treatise on individual predestination.
>
> **Text anchors:** [key moves in the passage]
>
> **But:** Many readers (Augustinian/Reformed traditions) take the same chapters as individual election; their strongest hooks are [cite them].
>
> If you want, I can lay both readings side-by-side with the exact verses each one leans on.

**The badge doesn't weaken authority — it earns it.**

#### 8.2.7 Global Hermeneutic Mode (GHM)

**Purpose:** Extend epistemic honesty to Scripture-facing domains with specific interpretive constraints.

GHM enforces textual-historical discipline when Tamor handles Scripture and Scripture-derived arguments. It prevents interpretive shortcuts from post-biblical abstraction, premature harmonization, or silent framework importation.

**Activation Model:**
- Primary: Project-level declaration (`hermeneutic_mode: ghm`)
- Secondary: Fallback detection for unassigned conversations (conservative, suggestive)
- Override: User can always activate/deactivate mid-conversation

**Core Constraints (GHM-1 through GHM-5):**
- GHM-1: Preserve textual claim scope
- GHM-2: Respect chronological constraint (earlier → later)
- GHM-3: Disclose frameworks not in the text
- GHM-4: Show tension before synthesis
- GHM-5: Surface discomfort rather than soften

**Project Templates:**
| Template | GHM Status |
|----------|------------|
| General | Off |
| Scripture Study | On |
| Theological Research | On |
| Engineering | Off |

**Deliverables:**
✅ `hermeneutic_mode` field in projects table (Migration 009)
✅ `ghm_rules.yml` configuration file
✅ Pipeline integration (check project mode, apply constraints)
✅ Fallback detection for unassigned conversations
✅ User override handling
✅ Project template selector in UI
✅ GHM indicator badge

**Documentation:**
- `docs/GHM-Spec.md` — Full specification
- `docs/When-GHM-Activates.md` — Activation rules and examples

**Profile System (Implemented):**
✅ Profile loader (`profile_loader.py`) with YAML config, caching, validation
✅ Pronomian Trajectory profile (evidence weighting, question prompts, guardrails)
✅ Profile injection into GHM system prompt
✅ Profile validation on project create/update (requires GHM check)
✅ `GET /api/projects/profiles` endpoint
✅ Profile badge in GHM badge UI

**Future (Post-GHM):**
- Additional profiles (e.g., dispensational, covenantal)
- UI profile selector in project settings
- PromptPacks for tone/style variants
- Test harness for regression validation

---

### 8.3 Focus Mode Completion ✅

**Purpose:** Deliver a distraction-free Tamor experience.

> **Design Note:** Focus Mode is one valuable mode among equals, not "Tamor's final form." The research/citation workflow remains equally central.

#### Features
- ✅ Single screen (full-screen overlay)
- ✅ Voice-first option (large mic button, auto-read responses)
- ✅ No panels, no noise (minimal header with exit button)
- ✅ Explicit "thinking space" (animated dots during processing)

#### Deliverables
- ✅ Toggle in header (◉ button)
- ✅ Keyboard exit (Escape key via FocusModeContext)
- ✅ Settings panel integration (voice-first, auto-enter mobile, show project indicator)
- ✅ Direct API integration (shares conversation context with main app)

---

### 8.4 System State Awareness & Indicators ✅

**Purpose:** Make system behavior legible.

#### Indicators
- ✅ Online vs offline (network status)
- ✅ LLM availability and provider
- ✅ Library mount status and file count
- ✅ SWORD module availability
- ✅ Embeddings availability

#### Deliverables
- ✅ `SystemStatus` service (`api/services/system_status.py`)
- ✅ `GET /api/system-status` endpoint
- ✅ `StatusIndicator` component (minimal dot, expandable panel)
- ✅ Auto-refresh every 60 seconds
- ✅ Expanded by default in Developer Mode

---

### 8.5 Feature Freeze & Deprecation Pass ✅

**Purpose:** Stop the slow creep.

#### Actions
- ✅ Audit unused or redundant features (all components, CSS, Python modules)
- ✅ Mark deprecated APIs and UI paths (stable vs experimental classification)
- ✅ Remove experimental flags that graduated or failed (none found - codebase clean)

#### Deliverables
- ✅ `docs/DEPRECATIONS.md` with full audit results
- ✅ Code audit: no unused files found (prior cleanup in 3.1, 3.4.1 was thorough)
- ✅ API stability classification documented

---

### 8.6 Documentation as First-Class Artifact ✅

**Purpose:** Make Tamor understandable without oral tradition.

#### Finalize
- ✅ Features Guide (Features.md - comprehensive, 31KB)
- ✅ Architecture overview (architecture.md - fully updated)
- ✅ Philosophy & boundaries (philosophy.md, BOUNDARIES.md)
- ✅ Epistemic system (epistemic-system.md)

#### Deliverables
- ✅ `/docs/INDEX.md` — central documentation hub
- ✅ Documentation section in Settings with links
- ✅ AboutTamor in-app page (modal from Settings)
- ✅ All docs linked and status tracked in INDEX.md

---

### 8.7 Declaration of Stability

**Purpose:** Formally end "core feature development."

#### Deliverable

Roadmap entry:

> **Tamor core is feature-complete.**
> Future work focuses on content, libraries, and refinement — not expansion.

**This is significant. Most systems never do this.**

---

### What Phase 8 Is NOT

- ❌ Not new agents
- ❌ Not new plugins
- ❌ Not more automation
- ❌ Not more intelligence

---

### Phase 8 Success Criteria

Tamor passes Phase 8 when:

1. A new user understands its limits in 5 minutes
2. You never wonder why it answered the way it did
3. Nothing feels hidden
4. Nothing feels rushed
5. You stop asking "what should we add next?"

---

### v1 Implementation Notes

#### What's In Scope for v1

1. **Four-tier answer classification** (Deterministic / Grounded–Direct / Grounded–Contested / Ungrounded)
2. **Six contested domains** with configurable detection
3. **Three-level contestation scale** (C1/C2/C3)
4. **Two lint dimensions** (certainty posture, clarity erosion)
5. **Budgeted anchor attempts** using cached sources
6. **Configurable rules file** (`epistemic_rules.yml`)
7. **Progressive disclosure UI** (badge → popover → expandable)
8. **Manual topic mappings** for recurring theological debates

#### What Can Wait for v2+

- ML-based contestation detection
- Automatic C-level inference from source analysis
- Cross-project lens inheritance
- Badge analytics (which topics trigger most expansions)

#### Technical Pipeline (v1)

```
Generate draft response (agent)
    ↓
Determine answer_type (deterministic/grounded-direct/grounded-contested/ungrounded)
    ↓
Lint for risky certainty claims + clarity erosion
    ↓
If needed:
    → Try to attach anchors (search refs/library, ≤250ms budget)
    → Else minimal sentence-level rewrite
    ↓
Assign badge + contestation metadata
    ↓
Display with progressive disclosure UI
```

---

### Decision Rationale & Design Notes

#### Why Four Tiers Instead of Two?

The original "deterministic vs probabilistic" split was too coarse. Theological interpretation needed its own category because you can be 100% grounded in text and still make a contestable inference. "Grounded–Contested" captures this: it's not about being less confident, it's about being transparent about *what kind* of confidence you're expressing.

#### Why "Anchor, Don't Hedge"?

The biggest insight from design review: epistemic humility shouldn't mean weakening claims. It should mean strengthening transparency. Citations do the epistemic work — if Tamor attaches the relevant passage, it can speak plainly. This reframes the restriction as a positive behavior.

#### Why Ethical Application as Separate Domain?

The move from "Scripture says X" to "therefore policy Y" almost always hides assumptions (prudential judgments, contextual factors, competing goods). Even when doctrine is agreed, application can be contested. Forcing Tamor to *show the bridge* makes reasoning auditable without weakening conviction.

#### Why Contestation Relative to Lens?

Contestation isn't absolute in the abstract. A Torah-observant reading isn't "minority" within that tradition. The project lens concept makes the system usable for focused theological work without constantly "arguing with itself."

#### Why Progressive Disclosure?

If C1/C2/C3 is always visible, it becomes noise. If hidden too deeply, it fails its purpose. The three-tier approach (badge → popover → explanation) matches how curiosity actually works. Most users sense it; some investigate; few need full detail.

#### Why "Governed, Not Model-Decided"?

The `epistemic_rules.yml` approach keeps you in control. The guardrails are authored, versioned, and project-specific. Tamor serves your judgment; it doesn't replace it.

#### Why Merged 8.2 and 8.3?

The original roadmap separated "Deterministic vs Probabilistic Transparency" (UI) from "Confidence Language Enforcement" (backend). In practice, they're one system: badge handles provenance metadata; linting handles content integrity; popover handles explanation. Separating them was artificial.

---

### Closing Frame

> "I know where the ground is firm, and I won't pretend the hills are bedrock."

That's Tamor's voice. Phase 8 succeeds when the system consistently embodies this.

Governance Rules

This roadmap is authoritative

New ideas must originate in Tamor – Roadmap Extensions & Proposals

Promotion requires:

Phase alignment

Clear rationale

Bounded scope

Dependency awareness

Roadmap Change Log
v1.40 – 2026-02-01

Completed Phase 5.5 Integrated Reader:
- ✅ TTS Service wrapping Piper for local text-to-speech
- ✅ Reader Service for content retrieval and session management
- ✅ 18 API endpoints under /api/reader Blueprint
- ✅ ReaderView and ReaderControls React components
- ✅ Expandable right panel mode (reader takes 55%, chat stays visible)
- ✅ Bookmarking with progress bar markers
- ✅ Audio playback with speed control, skip, chunk preloading
- ✅ setup_piper.py CLI for voice model installation
- ✅ "Read" buttons in Library and Files tabs

v1.39 – 2026-02-01

Internet Archive Harvester Integration:
- ✅ CLI tool for searching/downloading from Internet Archive (`api/tools/ia_harvester.py`)
- ✅ Provenance tracking in `ia_items` table with full IA metadata
- ✅ Clean filename renaming (`{Author} - {Title}.pdf` format)
- ✅ Import service bridging IA downloads to library system
- ✅ API endpoints for import management (`/api/library/ia/*`)
- ✅ OCR integration for scanned PDFs during import

Downloads to NAS at `/mnt/library/internet_archive/`. Enables corpus building for public domain research materials.

v1.38 – 2026-01-29

Completed Phase 6.4 Plugin Framework Expansion:
- ✅ Markdown export (plugin + API + UI menu item)
- ✅ PDF export with WeasyPrint (styled output, Tamor branding)
- ✅ Plugin config persistence (per-project settings in database)
- ✅ Reference caching with version tracking (content hash, TTL, cleanup)
- ✅ Zotero integration (read local SQLite, collections, items, citations)

Backend-first approach: API endpoints ready, UI to be added when friction demands it.

v1.37 – 2026-01-29

Updated Phase 6.4 Plugin Framework Expansion:
- Prioritized 5 items: Markdown export, PDF export, Zotero integration, Plugin config persistence, Reference caching
- Moved 3 items to "Future Consideration": Notion import, RSS/Atom feeds, Scheduled imports
- Added implementation notes and success criteria

v1.36 – 2026-01-27

GHM Profile System:
- ✅ Profile loader with YAML config and LRU caching
- ✅ Pronomian Trajectory profile (evidence weighting, 5 question prompts, 4 plausibility notes, 7 guardrails)
- ✅ Profile injection into GHM system prompt via prompt builder
- ✅ Profile validation on project create/update
- ✅ GET /api/projects/profiles endpoint
- ✅ Profile badge in GHM badge UI

v1.35 – 2026-01-25

PWA refinement:
- ✅ Install prompt now only displays on mobile devices
- Desktop users can still install via browser's native address bar icon

v1.34 – 2026-01-25

Completed PWA Implementation (Phase 8 Prerequisite):
- ✅ PWA manifest with icons, shortcuts, theme colors
- ✅ Full icon set (SVG + PNG 72-512px)
- ✅ iOS meta tags and apple-touch-icons
- ✅ Vite PWA plugin with workbox caching strategies
- ✅ Service worker registration with update detection
- ✅ UpdateNotification component for seamless updates
- ✅ InstallPrompt component with iOS/Android support
- ✅ Smart dismissal with 7-day cooldown
- ✅ Utility functions for PWA state detection

v1.33 – 2026-01-26

Completed Phase 8.6 Documentation as First-Class Artifact:
- ✅ Created `docs/INDEX.md` with links to all documentation
- ✅ Updated `docs/architecture.md` with current system design
- ✅ Added Documentation section to Settings with GitHub links
- ✅ Created AboutTamor in-app page (modal from Settings)
- ✅ Document status tracking in INDEX.md

v1.32 – 2026-01-26

Completed Phase 8.5 Feature Freeze & Deprecation Pass:
- ✅ Created `docs/DEPRECATIONS.md`
- ✅ Documented previously removed items (Phase 3.1, 3.4.1)
- ✅ Classified API stability (stable vs experimental)
- ✅ Audited React components, CSS files, Python modules
- ✅ Result: Codebase is clean, no unused code found

v1.31 – 2026-01-26

Completed Phase 8.4 System State Awareness & Indicators:
- ✅ SystemStatus dataclass with component availability flags
- ✅ get_system_status() checks: library, LLM, SWORD, Sefaria, embeddings
- ✅ GET /api/system-status endpoint in system_api.py
- ✅ StatusIndicator component with minimal/expanded views
- ✅ Color-coded status items (ok/warn/error)
- ✅ Auto-refresh every 60 seconds
- ✅ Integrated in header (expanded by default in dev mode)

v1.30 – 2026-01-26

Completed Phase 8.3 Focus Mode:
- ✅ FocusModeContext for state management (localStorage persistence)
- ✅ FocusMode component with voice-first interface
- ✅ Large mic button with pulse animation when listening
- ✅ Thinking animation (three animated dots)
- ✅ Response display with read-aloud toggle
- ✅ Text input fallback for non-voice usage
- ✅ Header toggle button (◉) in main app
- ✅ Conditional render in App.jsx (Focus Mode replaces main layout when active)
- ✅ Settings panel integration (voice-first, auto-enter mobile, show project indicator)
- ✅ Direct API calls sharing conversation context
- ✅ Escape key exit via context

v1.29 – 2026-01-26

Added Phase 8.2.7 Global Hermeneutic Mode (GHM):
- Epistemic honesty extension for Scripture-facing domains
- Project-level activation with fallback detection
- Five core hermeneutic constraints (GHM-1 through GHM-5)
- Project templates (Scripture Study, Theological Research enable GHM)
- GHM enforcer service (framework disclosure, harmonization/softening detection)
- Chat pipeline integration (both router and fallback LLM paths)
- GHM badge component (full/soft mode indicators with tooltip)
- Project template selector in new-project flows (ProjectsPanel modal, ChatPanel modal)
- Framework disclosure display in chat messages
- Documentation: GHM-Spec.md, When-GHM-Activates.md

Completed Phase 8.1 Tamor Principles & Boundaries Manifesto:
- ✅ Created `docs/BOUNDARIES.md` defining Tamor's philosophical limits

Completed Phase 8.2 Epistemic Honesty System:
- ✅ Four-tier answer classification (Deterministic/Grounded-Direct/Grounded-Contested/Ungrounded)
- ✅ Confidence linting with risky phrase detection
- ✅ Anchor service for evidence attachment (≤250ms budget)
- ✅ Repair service (anchor, rewrite, clarify strategies)
- ✅ Main pipeline orchestrating classify → lint → anchor → repair
- ✅ Chat integration with epistemic metadata in responses
- ✅ EpistemicBadge UI component with progressive disclosure
- ✅ Configurable rules via `epistemic_rules.yml`
- ✅ Database schema update (epistemic_json column)

v1.28 – 2026-01-25

Added Phase 8 – Trust, Restraint, and Completion:

- 8.1 Tamor Principles & Boundaries Manifesto (BOUNDARIES.md, in-app page)
- 8.2 Epistemic Honesty System (merged transparency + confidence enforcement)
  - Four-tier answer classification (Deterministic/Grounded-Direct/Grounded-Contested/Ungrounded)
  - Six contested domains with configurable detection
  - Three-level contestation scale (C1/C2/C3)
  - Progressive disclosure UI (badge → popover → expandable)
  - Configurable epistemic_rules.yml
- 8.3 Focus Mode Completion
- 8.4 System State Awareness & Indicators
- 8.5 Feature Freeze & Deprecation Pass
- 8.6 Documentation as First-Class Artifact
- 8.7 Declaration of Stability

Prerequisites: Mobile access (APK/PWA), NAS integration (Synology DS224+)

Philosophy: "Phase 1–7 built Tamor's mind. Phase 8 defines its soul."

v1.27 – 2026-01-24

Completed Phase 7.5 Transcription Queue (CPU-Optimized):

✅ TranscriptionQueueService: queue management with priority ordering
✅ TranscriptionWorker: faster-whisper processing with model caching
✅ Whisper models: tiny, base, small, medium, large-v2 (speed vs accuracy)
✅ Queue states: pending, processing, completed, failed
✅ Candidate discovery: find transcribable library files without transcripts
✅ API endpoints: 10 new endpoints for queue management
✅ TranscriptionQueue UI component with queue view and add candidates view
✅ Standalone worker runner script with --interval, --once, --batch options
✅ Systemd service file for background daemon deployment
✅ CSS standardization: all Library components use project CSS variables

v1.26 – 2026-01-24

Completed Phase 7.4 Library UI:

✅ useLibrary hook with all library API methods
✅ LibraryTab component (browse, search, manage views)
✅ Library statistics bar (file count, size, indexed/pending)
✅ LibrarySettings panel for context injection preferences
✅ ProjectLibraryRefs component for Files tab (linked library files)
✅ RightPanel integration (Library in essential tabs group)
✅ Add to project, remove reference, open library actions

v1.25 – 2026-01-24

Added Library Settings & Documentation:

✅ LibrarySettingsService for per-user context injection preferences
✅ Settings API: GET/PATCH /api/library/settings, POST /api/library/settings/reset
✅ Configurable: enabled, max_chunks, max_chars, min_score, scope
✅ Chat context injection respects user settings
✅ Created comprehensive Features Guide (docs/Features.md)

v1.24 – 2026-01-24

Completed Phase 7.3 Library Search & Retrieval:

✅ LibrarySearchService: semantic search with scope control (library/project/all)
✅ Cosine similarity scoring with project-referenced file boost
✅ search_by_file() for within-document search
✅ find_similar_files() using average embeddings
✅ LibraryContextService: inject library content into chat context
✅ ContextChunk dataclass with citation formatting
✅ System prompt builder with source attribution instructions
✅ API endpoints: search, search by file, find similar files

v1.23 – 2026-01-24

Completed Phase 7.2 Library Ingest Pipeline:

✅ LibraryScannerService: directory scanning with include/exclude patterns
✅ LibraryIngestService: batch importing with progress tracking
✅ LibraryIndexQueueService: background embedding generation queue
✅ Incremental sync: add new files, remove missing
✅ API endpoints: scan config/preview/summary, ingest, sync, index queue

v1.22 – 2026-01-24

Completed Phase 7.1 Library Schema & Core Service:

✅ Migration 008: library_files, library_chunks, library_text_cache, library_config, project_library_refs tables
✅ LibraryStorageService: mount path config, hash computation, path resolution
✅ LibraryService: full CRUD with deduplication, metadata, tags, stats
✅ LibraryReferenceService: project-library links, bulk operations
✅ LibraryTextService: text extraction with caching
✅ LibraryChunkService: chunking and embeddings for semantic search
✅ REST API: 12 endpoints for library and project reference management

v1.21 – 2026-01-24

Added Phase 7 – Global Library System:

- Centralized NAS-backed knowledge repository
- Library schema with project references (no duplication)
- Ingest pipeline with directory scanning and batch processing
- Library-wide semantic search with scope parameter
- Transcription queue for audio/video backlog
- UI for browsing, searching, and adding items to projects

v1.20 – 2026-01-24

Added EPUB file parsing support:

✅ ebooklib integration for EPUB text extraction
✅ Chapter structure preservation with offsets
✅ Dublin Core metadata extraction (title, author)
✅ Structure extraction for file analysis
✅ Seamless integration with semantic search and chunking

v1.19 – 2026-01-24

Completed Phase 3.5.5 Frontend Integration (Reference System):

✅ CitationCard component:
  - Compact and expanded display modes
  - Hebrew text support with RTL layout
  - Source badges (SWORD/Sefaria)
  - Copy, compare, external link actions

✅ Frontend utilities:
  - referenceParser.js with 66-book abbreviation mapping
  - useReferences hook for all API operations
  - Caching and batch lookup support

✅ Chat integration:
  - MessageCitations component detects references in assistant messages
  - Auto-fetches passage text and displays CitationCards
  - Limits to 5 citations per message

✅ ReferencesTab in RightPanel:
  - Passage lookup with translation dropdown
  - Compare translations panel
  - Recent lookups stored in localStorage
  - Module management (installed/available)

✅ LLM context injection:
  - inject_scripture_context() detects references in user messages
  - Fetches actual text from SWORD modules
  - Injects formatted context block into system prompt
  - Enables grounded, text-aware LLM responses

Phase 3.5 Reference Integration is now fully complete.

v1.18 – 2026-01-24

Completed Phase 3.5.1–3.5.4 Reference Integration (Backend):

✅ 3.5.1 Storage & Module Management:
  - Reference storage system with configurable paths (storage.py)
  - SWORD module downloader from CrossWire (sword_manager.py)
  - Setup script with CLI options (scripts/setup_references.py)
  - Default modules: KJV, ASV, YLT, SBLGNT

✅ 3.5.2 SWORD Client:
  - Read passages from local modules via pysword
  - Translation comparison, verse ranges, Greek text support
  - Book info with chapter/verse counts

✅ 3.5.3 Sefaria Client with Caching:
  - API client with aggressive file-based caching
  - TTL-based expiration with offline fallback
  - Hebrew text support, commentary, cross-references

✅ 3.5.4 Unified Reference Service:
  - ReferenceService combining SWORD + Sefaria
  - Reference parser with 200+ book abbreviations
  - Full API: lookup, compare, search, detect, commentary, cross-references, translations, modules, cache

✅ 3.5.5 Frontend Integration — completed in v1.19

v1.17 – 2026-01-23

Added Phase 3.5 Reference Integration (Local-First):

Philosophy: Local independence (SWORD local, Sefaria cached, NAS-ready)

v1.16 – 2026-01-23

Completed Phase 3.4.1 UI Audit & Developer Mode:

✅ UI audit with component categorization (Essential, Power User, Developer Only)

✅ DevModeContext with localStorage persistence

✅ TasksPanel and StructurePanel hidden behind dev mode toggle

✅ Removed dead components (MemoryList, MemoryCard, orphaned CSS)

✅ Developer Mode toggle in Settings panel

Completed Phase 3.4.2 Mobile-First Layout Refactor:

✅ useBreakpoint hook with responsive breakpoint detection

✅ Drawer component (slide-in panels with focus trap, escape key, backdrop)

✅ MobileNav bottom navigation component

✅ Settings panel for mobile drawer

✅ App.jsx refactored with conditional rendering by breakpoint

✅ RightPanel tab grouping (Essential tabs + collapsible Research/Tools groups)

✅ Tools button in mobile chat header

Completed Phase 3.4.3 Voice Input/Output:

✅ useVoiceInput hook (Web Speech API speech-to-text)

✅ useVoiceOutput hook (Web Speech API text-to-speech with Chrome bug workaround)

✅ VoiceButton component with pulse animation and live transcript preview

✅ Mic button integrated into chat input area

✅ Read aloud button on assistant messages (strips markdown for clean speech)

✅ VoiceSettingsContext for voice preferences (input/output enable, voice selection, rate, auto-read)

✅ Full voice settings UI in Settings panel with test button

✅ Auto-read responses feature

v1.15 – 2026-01-23

Added Phase 3.4 Interface Restoration:

⬜ 3.4.1 UI Audit & Developer Mode — categorize components, DevModeContext

⬜ 3.4.2 Mobile-First Layout Refactor — bottom nav, drawers, responsive breakpoints

⬜ 3.4.3 Voice Input/Output — Web Speech API hooks, mic button, read-aloud

⬜ 3.4.4 Focus Mode (Optional) — ultra-minimal voice-first view

Philosophy alignment: Wholeness • Light • Insight

v1.14 – 2026-01-22

Completed Phase 6.3 Plugin Framework:

✅ Plugin base classes: ImporterPlugin, ExporterPlugin, ReferencePlugin

✅ Auto-discovery registry with support for all plugin types

✅ ZIP Download exporter (project files + transcripts + manifest)

✅ JSON Export (structured project data with insights)

✅ Local Docs reference (browse folders without importing)

✅ Web Fetch reference (explicit URL content retrieval)

✅ API endpoints for exporters and references

✅ Tabbed UI in PluginsTab (Importers, Exporters, References)

Added Phase 6.4 Plugin Framework Expansion for future enhancements

v1.13 – 2026-01-22

Completed Phase 6.1 Long-Term Memory 2.0:

✅ Category-based memory with governance controls

✅ Searchable and pinnable memory

✅ Manual vs automatic memory distinction

✅ User-visible Memory tab in RightPanel

✅ Memory injection into chat context

Completed Phase 6.2 Multi-Agent Support:

✅ Router-based agent orchestration (services/router.py)

✅ Researcher agent: source analysis with citations

✅ Writer agent: prose synthesis from research

✅ Engineer agent: code generation with project awareness

✅ Archivist agent: memory commands (remember/forget)

✅ Heuristic intent classification (no LLM routing overhead)

✅ Smart project context detection for code requests

v1.12 – 2026-01-22

Completed Phase 5.4 Feature UI Integration:

✅ InsightsTab: aggregated and per-file insight views

✅ ReasoningTab: relationships, contradictions, logic flow analysis

✅ File Actions: rewrite modes, spec generation, parameter extraction

✅ PipelinePanel: workflow templates, progress tracking, step management

v1.11 – 2026-01-21

Enhanced Phase 5.3 with UI and export:

✅ Added Media tab to RightPanel for transcript management

✅ PDF export endpoint for transcripts with formatted timestamps

✅ Export PDF button in transcript viewer

Added Phase 5.4 Feature UI Integration (completed in v1.12)

v1.10 – 2026-01-21

Completed Phase 5.3 Media & Transcript Integration:

✅ Created services/transcript_service.py with yt-dlp + faster-whisper

✅ YouTube and URL audio download support

✅ Local GPU-accelerated transcription

✅ Timestamped segments for navigation

✅ Transcripts table for storage and retrieval

✅ API endpoints for URL and file transcription

v1.9 – 2026-01-21

Completed Phase 5.2 Project Pipelines:

✅ Created services/pipeline_service.py with workflow management

✅ Four pipeline templates: research, writing, study, long_form

✅ Pipeline state tracking (project_pipelines table)

✅ Step guidance with action recommendations

✅ LLM-generated progress summaries

✅ Full API for pipeline lifecycle management

v1.8 – 2026-01-21

Completed Phase 5.1 File Actions:

✅ Created services/file_actions_service.py with LLM-powered transformations

✅ Rewrite action with 6 modes + custom instructions support

✅ Spec generation from file content

✅ Parameter extraction with structured JSON output

✅ API endpoints for all three actions

v1.7 – 2026-01-21

Completed Phase 4.2 Multi-File Reasoning Mode:

✅ Created services/reasoning_service.py with cross-document analysis

✅ Added project_reasoning table (migration 003_project_reasoning.sql)

✅ Relationship analysis: file dependencies and references

✅ Cross-file contradiction detection

✅ Logic flow analysis: assumption coverage and coherence

✅ API endpoints for individual and combined reasoning results

v1.6 – 2026-01-21

Completed Phase 4.1 Auto-Insights Engine:

✅ Created services/insights_service.py with LLM-powered document analysis

✅ Added file_insights table via migration 002_file_insights.sql

✅ Hooked insights generation into file text extraction flow

✅ Added GET /files/{id}/insights and GET /projects/{id}/insights endpoints

✅ Detects: themes, contradictions, missing information, assumptions

v1.5 – 2026-01-21

Completed Phase 4.3 On-Disk Caching Layer:

✅ Created services/embedding_cache.py with persistent cache management

✅ Updated file_semantic_service.py to use cached embeddings (query-only embedding)

✅ Added cache invalidation on project deletion in projects_api.py

✅ Leverages existing file_chunks table for storage

v1.4 – 2026-01-21

Completed Phase 3 – Stability, Cleanup, and Refactoring:

Phase 3.2 UI Refactor:

✅ Introduced global CSS tokens across all component stylesheets

✅ Removed 8 unused backup/copy files

✅ Fixed scrolling and viewport issues (flex scroll patterns)

✅ Added accessibility foundations (focus-visible, prefers-reduced-motion, touch targets)

Phase 3.3 Database Cleanup:

✅ Created baseline migration (000_baseline.sql) documenting full schema

✅ Added migrations table with version tracking, checksums, and history

✅ Created db_validate.py utility for schema and data validation

✅ Enhanced run_migrations.py with --status, --validate, --dry-run options

v1.2 – 2026-01-21

Completed LLM provider abstraction layer (Phase 3.1)

Added /health endpoint with component checks (Phase 3.1)

Added task deletion and editing (Phase 2.6)

Enhanced TaskPill with full action buttons (Phase 2.6)

Updated Phase 2.6 to "Mostly Complete"; deferred content extraction to Phase 4.x

v1.3 – 2026-01-21

Completed Phase 3.1 Backend Refactor & Deterministic Safety:

Removed legacy/dead code (backup files, intent_old.py, empty directories)

Standardized API error responses (utils/auth.py, utils/errors.py)

Fixed migration runner import, updated schema.sql documentation

Implemented deterministic safety enforcement (core/deterministic.py)

Integrated deterministic queries into chat flow

v1.1 – 2026-01-20

Promoted deterministic safety enforcement into Phase 3.1

Expanded Phase 6.1 to include explicit memory governance

Clarified Tamor-only scope (separate from Anchor Assistant)

Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| Local-first deployment | Privacy, no cloud dependency, full data ownership |
| Flask + Gunicorn | Simplicity over async; sufficient for single-user workload |
| Sentence-Transformers (local) | No API cost for embeddings; works offline |
| OpenAI for LLM (abstraction layer done) | Best quality/cost for chat; services/llm_service.py enables provider switching |
| SQLite | Single-user, file-based, zero config |
| React + Vite frontend | Fast dev iteration, familiar tooling |
| Cloudflare Tunnel | Secure remote access without exposing ports |

Companion Documents

**[Features Guide](../docs/Features.md)** – Comprehensive reference for all Tamor features, APIs, and usage patterns. Includes:
- Global Library System (scanning, ingestion, search, context injection, settings)
- Reference Integration (SWORD, Sefaria)
- Multi-Agent System (Researcher, Writer, Engineer, Archivist)
- Memory System, Plugin Framework, Pipelines, Insights, Transcription

Tamor – Roadmap Extensions & Proposals

Internal design notes

Phase-specific execution checklists (as needed)
