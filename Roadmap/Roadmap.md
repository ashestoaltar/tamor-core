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

PDF / DOCX / XLSX parsing improvements

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

3.4.4 Focus Mode (Optional)

⬜ Single-screen chat, no panels

⬜ Large central mic button

⬜ Minimal chrome (project indicator + settings access only)

⬜ Easy toggle in/out of Focus Mode

**Success Criteria:**
- ✅ New user sees clean, simple chat interface by default
- ✅ Mobile experience is native-feeling (bottom nav, appropriate sizing)
- ✅ Voice input/output works reliably on iOS Safari and Android Chrome
- ✅ Developer tools accessible but hidden by default
- ✅ Interface embodies Tamor: calm, purposeful, illuminating

3.5 Reference Integration (Local-First) (Proposed)

Integrate biblical and scholarly reference sources into Tamor, enabling grounded research with clear source attribution.

**Philosophy: Local Independence**
- SWORD modules — Bible translations stored locally, no API calls
- Sefaria caching — API for Jewish texts, but aggressively cached locally
- Single data directory — easy migration to NAS when ready
- Offline capable — works without internet for cached/local content

**Storage Structure:**
```
{TAMOR_REFERENCE_PATH}/          # Default: /home/tamor/data/references/
├── sword/modules/               # SWORD Bible modules (~50-100MB typical)
├── sefaria_cache/               # Cached Sefaria responses
└── config.json                  # Module preferences, enabled translations
```

3.5.1 Storage & Module Management

⬜ Create reference data directory structure

⬜ SWORD module downloader (fetch from CrossWire)

⬜ Module configuration (enable/disable translations)

⬜ pysword integration for reading modules

3.5.2 SWORD Client

⬜ Read passages from local modules

⬜ List available/enabled translations

⬜ Search within modules (basic keyword)

⬜ Compare translations locally

3.5.3 Sefaria Client with Caching

⬜ API client for Sefaria

⬜ File-based cache for responses

⬜ SQLite index for cache lookups

⬜ Offline fallback to cache

3.5.4 Unified Reference Service

⬜ Combined interface for both sources

⬜ Reference parser (human input → structured)

⬜ API endpoints: /api/references/lookup, /search, /compare, /versions, /modules

3.5.5 Frontend Integration

⬜ CitationCard component

⬜ ReferencesTab in RightPanel

⬜ Chat citation display

⬜ LLM context injection

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

6.4 Plugin Framework Expansion (Future)

Additional exporters:

⬜ Markdown export (formatted project documentation)

⬜ PDF export (polished report generation)

Additional reference backends:

⬜ Zotero integration (academic reference management)

⬜ Notion import (external knowledge base sync)

⬜ RSS/Atom feeds (content monitoring)

Plugin enhancements:

⬜ Plugin configuration persistence per project

⬜ Scheduled/automated imports

⬜ Reference content caching and versioning

Governance Rules

This roadmap is authoritative

New ideas must originate in Tamor – Roadmap Extensions & Proposals

Promotion requires:

Phase alignment

Clear rationale

Bounded scope

Dependency awareness

Roadmap Change Log
v1.17 – 2026-01-23

Added Phase 3.5 Reference Integration (Local-First):

⬜ 3.5.1 Storage & Module Management — directory structure, SWORD downloader, pysword

⬜ 3.5.2 SWORD Client — local Bible module reading, translation comparison

⬜ 3.5.3 Sefaria Client with Caching — API client, file cache, offline fallback

⬜ 3.5.4 Unified Reference Service — combined interface, reference parser, API endpoints

⬜ 3.5.5 Frontend Integration — CitationCard, ReferencesTab, chat citations

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

Tamor – Roadmap Extensions & Proposals

Internal design notes

Phase-specific execution checklists (as needed)
