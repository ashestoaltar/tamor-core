# Tamor – Roadmap Extensions & Proposals

**Project:** Tamor
**Role:** Roadmap Intake & Evaluation Layer
**Status:** Living Document (Non-Authoritative)

This document captures ideas, extensions, and refinements that have emerged through discussion but are **not yet promoted** into the authoritative Tamor Development Roadmap.

Nothing in this file is considered committed work until formally promoted.

---

## Status Legend

- 🟡 Idea / Captured
- 🔵 Investigating / Needs Design
- 🟢 Approved for Promotion
- 🔴 Deferred / Rejected

---

## A. Platform & Core Intelligence Extensions

### 1. Deterministic Safety Boundaries
**Status:** 🟢 Approved for Promotion
**Maps To:** Phase 3.1 – Backend Refactor

- Hard-stop rules preventing LLM fallthrough on deterministic queries
- Explicit "not found" responses when certainty cannot be guaranteed
- Strict separation of deterministic vs probabilistic responses

**Promotion Edit:**
Add explicit deterministic enforcement language to Phase 3.1, including demo-safety guarantees.

---

### 2. Multi-LLM Routing & Fallback
**Status:** 🟢 Partially Complete
**Maps To:** Phase 6.2 – Multi-Agent Support

- ✅ Primary LLM with secondary fallback (`get_best_available_client()`)
- ✅ Ollama provider integration (`OllamaProvider` class)
- ✅ Intent classification using local LLM (phi3:mini)
- ⏳ Optional task-based routing (writing vs code vs analysis)
- ⏳ Health-based failover

Constraints:
- Must preserve consistent tone
- Must not fragment memory semantics

> Partial implementation completed 2026-02-01. Cloud for generation, local for classification.

---

### 3. Auto-Insights Expansion
**Status:** 🟢 Completed
**Maps To:** Phase 4.1 – Auto-Insights Engine / Phase 4.2 – Multi-File Reasoning

- ✅ Detect contradictions across documents (Phase 4.2)
- ✅ Identify missing specs or assumptions (Phase 4.1)
- ✅ Highlight inconsistencies early (Phase 4.2 logic flow)

> Implemented in Phase 4.1 (file insights) and Phase 4.2 (cross-document reasoning).

---

## B. Input, Media, and Accessibility

### 4. Voice-to-Text Input (Android-First)
**Status:** 🟢 Completed
**Maps To:** Phase 3.4.3 – Voice Input/Output

- ✅ Browser-native speech-to-text (Web Speech API)
- ✅ Append-to-chat behavior
- ✅ Mobile-first UX

> Implemented in Phase 3.4.3 with useVoiceInput hook and VoiceButton component.

---

### 5. Audio Reading Mode (Read Aloud)
**Status:** 🟢 Completed
**Maps To:** Phase 3.4.3 – Voice Input/Output

- ✅ Read articles, summaries, and structured content aloud
- ✅ Simple TTS pipeline (Web Speech API)
- ✅ Auto-read responses option

> Implemented in Phase 3.4.3 with useVoiceOutput hook and read-aloud button on messages.

---

## C. Knowledge Sources & Reference Backends

### 6. Reference-Only External Backends
**Status:** 🔵 Investigating
**Maps To:** Phase 6.3 – Plugin Framework

- Read-only integrations
- Clearly labeled as reference material
- Never presented as authoritative answers

---

### 6b. Web Search Context Injection (Tavily)
**Status:** 🔵 Investigating
**Maps To:** Phase 6.3 – Plugin Framework / Phase 8.x – Context Intelligence
**Created:** 2026-01-27

**Purpose:** Allow Tamor to ground answers in current web sources for non-scripture, non-library questions. Opt-in per project.

**Problem:**
When a user asks something outside scripture and their uploaded docs, Tamor has nothing to reference except the LLM's training data. This is fine for Scripture Study projects (which have SWORD + Sefaria), but engineering, writing, and general research projects lack access to current information.

**Proposed Solution:**
Add web search as a context injection source, following the exact pattern used by scripture/library/project-files context. Per-project opt-in via a `web_search_enabled` column on the projects table.

**API Choice: Tavily**
- Returns AI-ready, pre-processed content with citations (no scraping needed)
- Built for RAG pipelines (exactly Tamor's use case)
- 1,000 free searches/month, ~$8/1K after that
- Brave Search is cheaper ($3-5/1K) but returns raw SERPs requiring extraction
- Tavily Python SDK: `pip install tavily-python`

**Architecture:**
Follows the existing context injection pattern in `chat_api.py`:
1. Check project setting (`web_search_enabled`) → skip if false
2. Check API key configured (`TAVILY_API_KEY`) → skip if missing
3. Call Tavily search (3 results, 5s timeout)
4. Format as `[Web Search Context]...[End Web Search Context]` block
5. Append to system prompt (same as scripture/library)
6. Wrap in try/except (never fail chat if search fails)

**Implementation Scope:**

| Component | File | Change |
|-----------|------|--------|
| Migration | `api/migrations/010_web_search_project_setting.sql` | `ALTER TABLE projects ADD COLUMN web_search_enabled BOOLEAN DEFAULT FALSE` |
| Config | `api/core/config.py` | Add `TAVILY_API_KEY` env var |
| Service | `api/services/web_search.py` | Thin Tavily wrapper with timeout + graceful degradation |
| Context injection | `api/routes/chat_api.py` | `_get_web_search_context()` function, wired into both chat paths |
| RequestContext | `api/services/agents/base.py` | Add `web_search_context: Optional[str]` field |
| Agent injection | `api/services/agents/writer.py`, `researcher.py` | Append web search context to system prompt if present |
| Projects API | `api/routes/projects_api.py` | Handle `web_search_enabled` in list/create/patch + template defaults |
| UI | `ProjectsPanel.jsx` or project settings | Toggle for web search per project |

**Template Defaults:**
| Template | Web Search |
|----------|-----------|
| General | Off |
| Scripture Study | Off |
| Theological Research | Off |
| Engineering | On |
| Writing | Off |

**Explicitly Out of Scope:**
- No auto-search for unassigned conversations (project opt-in only)
- No search result caching across conversations
- No academic/scholar search (JSTOR, Google Scholar) — separate future proposal
- No UI display of search sources in chat messages (future enhancement)
- No search for scripture projects by default

**Dependencies:**
- `tavily-python` package in `api/venv/`
- Tavily API key (free tier sufficient for personal use)
- Existing context injection pattern (complete)
- Project settings infrastructure (complete — Migration 009 pattern)

**Cost Estimate:**
Personal use at ~20-30 searches/day = ~600-900/month. Within free tier. Paid tier ($8/1K) would cost <$10/month at heavy usage.

**Risks:**
- External API dependency (mitigated: graceful degradation when key missing or API down)
- Search quality varies (mitigated: LLM treats as context, not truth)
- Cost creep if overused (mitigated: per-project opt-in, not global)

---

### 7. Network-Based File Discovery
**Status:** 🟢 Approved for Promotion
**Maps To:** Phase 7.2 – Library Ingest Pipeline

- Index approved network locations (NAS mount points)
- No file duplication (reference model)
- Permission-aware access
- Incremental sync for new/changed files

**Promotion Edit:**
Merged into Phase 7 Global Library System as part of the ingest pipeline.

---

## D. Media, Transcripts, and Long-Form Workflows

### 8. Bulk Audio → Text → PDF Pipelines
**Status:** 🟢 Approved for Promotion
**Maps To:** Phase 7.5 – Transcription Queue

- Batch MP3/video ingestion
- Background transcription with queue management
- Model selection (speed vs accuracy tradeoff)
- Transcript stored as searchable library item

**Promotion Edit:**
Merged into Phase 7 Global Library System as the transcription queue subsystem.

---

### 9. Long-Form Article Pipelines
**Status:** 🔵 Investigating
**Maps To:** Phase 5.2 – Project Pipelines

- Multi-source research aggregation
- Structured outlining
- Iterative drafting support

---

### 24. Integrated Reader (Visual + Audio)
**Status:** 🟢 Approved for Promotion
**Maps To:** Phase 5.5 – Integrated Reader
**Created:** 2026-02-01
**Expands:** Extension #5 (Audio Reading Mode, completed in 3.4.3)

**Purpose:** A unified reading interface for long-form content from the NAS library, project files, and transcripts. Combines visual reading with local text-to-speech for offline, distraction-free consumption.

**Visual Reader:**
- Distraction-free reading view (full-screen or overlay)
- Clean typography with adjustable font size and line spacing
- Pagination or continuous scroll modes
- Bookmarking and progress tracking
- Support for: PDFs (text extraction), transcripts, DOCX, HTML, plain text

**Audio Reader (TTS):**
- Local text-to-speech via Piper (MIT licensed, high quality, fully offline)
- Playback controls: speed adjustment, pause/resume, skip forward/back
- Sentence-level text highlighting synced with audio position
- Queue multiple documents for continuous listening
- "Read this to me" command from chat or file actions

**Progress Tracking:**
- `reading_sessions` table: file_id, position, duration, last_accessed
- Resume where you left off (visual and audio)
- Optional reading history / "recently read"

**Integration Points:**
- NAS Library (Phase 7): browse and select content
- Transcripts (Phase 5.3): read/listen to transcribed content
- File Actions (Phase 5.1): "Open in Reader" action
- Chat: "Read me [document]" or "Continue reading"

**Technical Decisions:**
- **PDF handling:** Text extraction (reuse library indexing), not full PDF.js rendering. "View Original" link for layout-critical docs.
- **Audio sync:** Sentence-level highlighting (word-level deferred as future enhancement)
- **Non-English TTS:** Deferred. English voices only in v1.

**Technical Dependencies:**
- Piper TTS: `pip install piper-tts` (or run as subprocess)
- Voice models: downloadable, stored on NAS (~50-100MB each)
- Audio streaming: chunked TTS generation for long documents
- Existing MediaTab UI patterns (timestamps, segments)

**Voice Models (starter set):**
- en_US-lessac-medium (male) - ~50MB
- en_US-amy-medium (female) - ~50MB
- Additional voices as needed

**Scope Boundaries:**
- Single-user, local playback only (no casting/sync initially)
- No annotation or highlighting in v1 (future extension)
- TTS quality is "good enough" not "perfect narrator"
- Progress is per-file, not per-device
- English only for TTS

**MVP Path:**
1. Visual reader view (reuse transcript viewer patterns)
2. Piper TTS integration with basic controls
3. Progress tracking table and resume logic
4. "Open in Reader" file action
5. Chat command support

**Constraints:**
- Must work fully offline
- No cloud TTS APIs
- Reader view must not interfere with main workspace flow

**Promotion Edit:**
Add Phase 5.5 – Integrated Reader to main roadmap after Phase 5.4.

---

## E. UI, UX, and Presentation

### 10. Search Results UX Improvements
**Status:** 🟡 Idea
**Maps To:** Phase 2.5 / Phase 3.2

- Better hit context
- Confidence indicators
- Clearer navigation

---

### 11. Knowledge Graph Visualization
**Status:** 🟡 Idea
**Maps To:** Phase 2.3 / Phase 4.x

- Visual node relationships
- Symbol exploration
- Read-only initially

---

### 14. Interface Restoration (Mobile-First + Voice)
**Status:** 🟢 Approved for Promotion
**Maps To:** Phase 3.4 – Interface Restoration
**Created:** 2026-01-23

**Purpose:** Align the UI with Tamor's core philosophy (Wholeness • Light • Insight). Simplify the default experience, add voice interaction, and make mobile a first-class citizen.

**Context:**
Tamor's name derives from Tav (purpose/completion) + Or (light/understanding). The current UI has accumulated scaffolding from development that contradicts the philosophy of restraint, quiet strength, and clarity without flash.

**Guiding Principles:**
- Every UI element must earn its place
- Mobile is not a smaller desktop – design for touch and voice first
- Depth on demand – simple by default, powerful when needed
- Developer tools are not user tools – separate concerns cleanly

**Subphases:**
1. **3.4.1 UI Audit & Developer Mode** – Categorize components, create DevModeContext, remove dead code
2. **3.4.2 Mobile-First Layout Refactor** – Bottom nav, drawer components, responsive breakpoints
3. **3.4.3 Voice Input/Output** – Web Speech API hooks, mic button, read-aloud, voice settings
4. **3.4.4 Focus Mode (Optional)** – Ultra-minimal voice-first view

**Promotion Edit:**
Add Phase 3.4 to main roadmap after Phase 3.3 Database Cleanup. Full specification included in promotion.

---

## F. Infrastructure & Storage

### 12. Global Library System (NAS-Backed)
**Status:** 🟢 Approved for Promotion
**Maps To:** Phase 7 – Global Library System
**Created:** 2026-01-24

**Purpose:** Centralized, NAS-backed knowledge repository that serves as the single source of truth for all documents, transcripts, and media. Projects reference library items without duplication.

**Context:**
Current Tamor architecture stores files per-project, leading to potential duplication and no unified search across all knowledge. The Global Library introduces a reference model where:
- Library items live in one place (NAS-backed storage)
- Projects hold references to library items (no copying)
- Search can be scoped: project-only, library-wide, or hybrid
- Transcripts from audio/video are stored as library items linked to source media

**Hardware Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│   Synology DS224+        SMB/NFS      ASUS PN51-S1          │
│   (4TB mirrored)    ◄──────────────►  (Tamor Server)        │
│                                                             │
│   • PDFs, DOCX, media    Mount at     • Flask API           │
│   • Transcripts          /mnt/library • SQLite indexes      │
│   • Single source                     • Embedding service   │
│     of truth                          • faster-whisper CPU  │
└─────────────────────────────────────────────────────────────┘
```

**Scale Estimate:**
- 150-200 PDFs initially, growing moderately
- 20-30 hours audio, 10 hours video (transcribe once, keep originals)
- Personal use (single user, occasional second user)

**Subphases:**
1. **7.1 Library Schema & Core Service** – Database tables, CRUD, reference management
2. **7.2 Library Ingest Pipeline** – Directory scanning, file routing, batch processing
3. **7.3 Library Search & Retrieval** – Scoped semantic search, hybrid queries
4. **7.4 Library UI** – Browse, search, add-to-project actions
5. **7.5 Transcription Queue** – Background processing for audio/video backlog

**Key Design Decisions:**
- **Reference model:** Projects link to library items via `project_library_refs` (no file duplication)
- **Transcripts as first-class items:** Audio/video is transcribed; transcript becomes the searchable artifact; original kept for playback reference
- **CPU transcription:** Using faster-whisper `base` model; ~30 hours of audio = ~5-7 hours processing (acceptable for one-time backlog)
- **Search scopes:** project | library | all (hybrid searches project first, then widens)

**Dependencies:**
- Phase 4.3 On-Disk Caching Layer (complete) – embedding cache pattern reused
- Phase 5.3 Media & Transcript Integration (complete) – faster-whisper already integrated
- Phase 6.3 Plugin Framework (complete) – importer pattern available

**Promotion Edit:**
Add Phase 7 – Global Library System to main roadmap after Phase 6. Full specification with 5 subphases.

---

## G. Governance & Memory

### 13. Memory Governance Rules
**Status:** 🟢 Approved for Promotion
**Maps To:** Phase 6.1 – Long-Term Memory 2.0

- Manual vs automatic memory
- Category-based persistence
- Explicit user consent
- User-visible memory controls

**Promotion Edit:**
Expand Phase 6.1 to explicitly define memory governance and consent rules.

---

## H. Writing & Content Creation

### 15. Writing Style Preferences
**Status:** 🔵 Investigating
**Maps To:** Phase 6.1 / Phase 6.2
**Created:** 2026-01-24

**Purpose:** Enable Tamor's Writer Agent to produce content that sounds human and matches the user's personal voice.

**Context:**
The Writer Agent (Phase 6.2) already extracts style preferences from memories tagged with "preference" category containing keywords like style, tone, voice, write, formal, casual. This extension formalizes and expands that capability.

**Proposed Enhancements:**
- Dedicated style preference memory category
- Example-based style learning (user provides sample writing)
- Anti-patterns list (phrases to avoid: "It's important to note", "Furthermore", etc.)
- Voice profile: sentence length variance, formality level, rhetorical patterns
- Per-project style overrides

**Implementation Notes:**
- `_extract_style_preferences()` in Writer Agent needs expansion
- Memory category "style" distinct from general "preference"
- UI for managing style preferences in Memory tab

---

## I. UX & Interaction

### 16. Conversation Bookmarking
**Status:** 🟡 Idea
**Maps To:** Phase 3.2 – UI Refactor

- Mark significant points in a conversation for later reference
- Quick-jump to bookmarked messages
- Bookmarks visible in conversation list or sidebar

---

### 17. Keyboard Shortcuts
**Status:** 🟡 Idea
**Maps To:** Phase 3.2 – UI Refactor

- New conversation (Ctrl+N / Cmd+N)
- Switch project (Ctrl+P / Cmd+P)
- Focus mode toggle (Ctrl+Shift+F)
- Navigate conversation list (arrow keys)

---

### 18. Response Regeneration
**Status:** 🟡 Idea
**Maps To:** Phase 3.2 – UI Refactor

- Re-run a question with current GHM/profile settings
- Useful after changing project profile or hermeneutic mode
- Show previous and regenerated responses side-by-side or as replacement

---

### 19. UI Profile Selector
**Status:** 🟡 Idea
**Maps To:** Phase 3.2 – UI Refactor

- Project settings modal with profile dropdown
- Preview profile description and constraints before applying
- Quick-switch profiles without navigating to project settings

---

## J. Memory System Research Extensions

*Research-informed proposals captured 2026-01-30*
*Source: Moltbook agent discourse analysis (~/moltbook-research/)*

### 20. Memory Aging & Decay
**Status:** 🟡 Idea (Parked)
**Maps To:** Phase 6.1 – Long-Term Memory 2.0
**Created:** 2026-01-30

**Source:** Moltbook agents discussing retrieval weighting, Ebbinghaus curve references

**Problem:** All memories treated equally regardless of age or access frequency.

**Proposal:**
- Add `last_accessed` timestamp to memories
- Weight retrieval by recency + access frequency
- Optional: configurable decay curve (not deletion, just deprioritization)

**Complexity:** Medium
**Dependencies:** None

---

### 21. Automated Compression/Distillation
**Status:** 🟡 Idea (Parked)
**Maps To:** Phase 6.1 – Long-Term Memory 2.0
**Created:** 2026-01-30

**Source:** AiChan's two-tier system, DuckBot's pre-compression checkpointing (Moltbook)

**Problem:** Memories accumulate without summarization; old detailed memories consume retrieval capacity.

**Proposal:**
- Periodic background job reviews old memories
- LLM-assisted distillation: "What here is worth remembering forever?"
- Raw → summarized → archived tiers
- Pre-compression checkpoint when context gets heavy

**Complexity:** High
**Dependencies:** Background job infrastructure

---

### 22. Token Budget Awareness
**Status:** 🟡 Idea (Parked)
**Maps To:** Phase 3.1 – Backend Refactor
**Created:** 2026-01-30

**Source:** ClawdVC's tokenization overhead discovery (Moltbook)

**Problem:** Context injection may be wasteful; users unaware of token usage.

**Proposal:**
- Audit current context injection for token efficiency
- Minify JSON in context (40% savings reported by agents)
- Display token budget in UI
- Warn when approaching limits

**Complexity:** Low-Medium
**Dependencies:** None

---

### 23. Memory Stats Dashboard
**Status:** 🟡 Idea (Parked)
**Maps To:** Phase 3.2 – UI Refactor
**Created:** 2026-01-30

**Source:** Multiple Moltbook agents wanting visibility into stored memories

**Problem:** Users don't know what Tamor remembers or why retrieval returns certain items.

**Proposal:**
- Surface memory count, categories, age distribution
- Show what was retrieved for current context
- "Why do you know this?" explainability
- Memory health indicators

**Complexity:** Medium
**Dependencies:** UI work

---

### Research Context: What Tamor Already Does Better

Based on Moltbook analysis, Tamor's architecture already provides:
- Human oversight of retention (agents lack this)
- Epistemic classification of sources (agents just dump everything)
- Project-scoped memory (agents have global only)
- Explicit provenance tracking

### Research Artifacts

- Moltbook archive: `~/moltbook-research/`
- Memory research report: `research/outputs/memory_research_2026-01-30.md`
- Tamor comparison: `research/outputs/tamor_comparison_2026-01-30.md`

### Priority When Revisited

1. Token budget awareness (low effort, immediate value)
2. Memory stats dashboard (visibility builds trust)
3. Memory aging (improves retrieval quality)
4. Automated compression (most complex, biggest payoff)

> **Note:** Parked until after Phase 8 completion and NAS library stabilization. Agents are solving similar problems with less discipline—their approaches are worth learning from but Tamor's human-controlled architecture remains the right foundation.

---

## K. Local AI Vision

**Status:** 🟢 In Progress (K.1 Complete)
**Priority:** High
**Added:** 2026-02-01

A comprehensive plan to make Tamor maximally capable using local AI inference, reducing cloud dependency while improving capabilities.

### Philosophy

**Claude is the expert you consult. The local LLM is the assistant who does the prep work.**

Cloud AI (Claude) should be reserved for:
- Complex reasoning and analysis
- High-stakes decisions
- Tasks requiring frontier-level capability

Everything else can run locally, making Tamor:
- Fully functional offline
- Near-zero marginal cost to operate
- Faster for routine operations
- More private

### Current Hardware Context

- AMD Ryzen 5 5500U (6 cores, 12 threads)
- 64GB RAM (key advantage - enables larger models)
- No discrete GPU (CPU inference only)
- 5.3TB NAS for library storage

### K.1 Local LLM Integration (Ollama)

**Status:** 🟢 Completed (2026-02-01)
**Impact:** High
**Effort:** Medium

Ollama installed with local models as Tamor's "local brain":

| Use Case | Model | Status |
|----------|-------|--------|
| Routing/classification | phi3:mini | ✅ Active (fast, 2.2GB) |
| General purpose | llama3.1:8b | ✅ Installed |
| Summarization | llama3.1:8b | ⏳ Ready to use |

**Implemented:**
- ✅ `OllamaProvider` class in `llm_service.py`
- ✅ Intent classification using local LLM with LRU caching (500 entries)
- ✅ Model pre-warming on startup (background thread)
- ✅ Heuristic → cache → local LLM classification tier
- ✅ System status reporting for local LLM availability
- ✅ Environment config: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`

### K.2 Aggressive Background Processing

**Impact:** High
**Effort:** Medium

With 64GB RAM, batch process the entire library:

- **Document summarization**: Every file gets a 2-3 sentence summary
- **Entity extraction**: People, places, concepts, dates
- **Relationship mapping**: Build knowledge graph edges
- **Cross-reference detection**: "This document mentions X from that document"
- **Pre-computed similarity**: "Related documents" ready instantly

Run overnight, update incrementally as new files arrive.

### K.3 Proactive Context Assembly

**Impact:** High
**Effort:** High

Current: RAG retrieves chunks based on query similarity.
Better: Intelligent context assembly that considers:

- Query intent (what kind of answer is needed?)
- Document authority (primary sources vs commentary)
- Recency and relevance decay
- User's current project focus
- Conversation history context

Assemble the *perfect* context window for each query, not just "top K chunks."

### K.4 Local Embedding Model

**Impact:** Medium
**Effort:** Low

If using cloud embeddings, switch to local:

- `sentence-transformers/all-MiniLM-L6-v2` (fast, decent)
- `BAAI/bge-large-en-v1.5` (better quality, still fast on CPU)
- `intfloat/e5-large-v2` (excellent quality)

All embeddings computed locally, no API calls for semantic search.

### K.5 Voice Interface

**Impact:** Medium
**Effort:** Low

Already have the pieces:
- Whisper for speech-to-text
- Piper for text-to-speech

Wire them together:
- Voice input mode for queries
- Optional spoken responses
- Useful when reading physical books and dictating notes

### K.6 Proactive Insights

**Impact:** High
**Effort:** High

Shift from reactive search to proactive surfacing:

- "Based on your current project, you might find this relevant..."
- "This contradicts something in [other document]..."
- "You asked about X last week—here's new material on that topic"

Requires K.2 (background processing) as foundation.

### Hardware Upgrade Path

If upgrading hardware, priority order:

1. **NVIDIA GPU (RTX 3060 12GB or better)**: 10-50x faster inference, enables larger models in real-time
2. **More CPU cores (Ryzen 9 / Threadripper)**: Better parallel processing for batch jobs
3. **NVMe for model storage**: Faster model loading

The 64GB RAM is already excellent—no upgrade needed there.

### Implementation Order

1. **Ollama + Mistral 7B** — Immediate win, enables everything else
2. **Local embedding model** — Quick, removes cloud dependency
3. **Background summarization pipeline** — Uses local LLM
4. **Knowledge graph extraction** — Uses local LLM
5. **Voice interface** — Polish feature
6. **Proactive insights** — Capstone feature

---

## L. Library System Enhancements

**Status:** 🔵 Ready to Build
**Maps To:** Phase 7 – Global Library System

### L.1 Library Collections

**Status:** 🟢 Planned (design complete)
**Impact:** Medium
**Effort:** Low-Medium

Organize NAS library files into named groups (e.g., "Founding Era", "Patristics", "Torah Commentary"). Files can belong to multiple collections.

**Design:** Flat collections (v1). Files can be in multiple collections. Naming conventions can simulate hierarchy if needed.

**Schema:**
- `library_collections`: id, name, description, color, timestamps
- `library_collection_files`: collection_id, library_file_id (junction table)

**API Endpoints:**
- CRUD for collections
- Add/remove files from collections
- List files in collection
- List collections for file

**UI:**
- Collections view in Library tab
- Collection cards with color indicators
- "Add to Collection" action on files
- CollectionModal for create/edit

**Full design:** `/home/tamor/.claude/plans/valiant-frolicking-flame.md`

---

## Promotion Checklist

An item may be promoted to the authoritative roadmap only when:

- Phase alignment is clear
- Dependencies are known
- Scope is bounded
- Rationale is documented

---

## M. Agent System Expansion: Planner & Writer

**Status:** ✅ Complete
**Maps To:** Phase 6.2 – Multi-Agent Support (Extension)
**Created:** 2026-02-04
**Implemented:** 2026-02-04

### Purpose

Extend the multi-agent system with:
1. **Writer agent wired to library** — Currently exists but not connected to LibrarySearchService
2. **Planner agent** — Orchestrates multi-step writing projects (research → draft → review → revise)

### M.1 Writer Library Integration

**Status:** ✅ Complete
**Impact:** High
**Effort:** Low (replicate Researcher pattern)
**Implemented:** 2026-02-04

The Writer agent now has library access for grounded, cited content.

**Implementation:**
- ✅ Connected Writer to `LibrarySearchService`
- ✅ Library chunks injected into Writer's prompt context
- ✅ Source citations enabled in prose output
- ✅ Fallback search when no prior Researcher output exists

### M.2 Writer Templates

**Status:** ✅ Complete
**Impact:** Medium
**Effort:** Low
**Implemented:** 2026-02-04

Per-project-type templates for recurring content formats.

**Templates:**
- ✅ `article` — Long-form (1,500-2,500 words)
- ✅ `torah_portion` — Weekly parashah teaching (1,000-1,500 words)
- ✅ `deep_dive` — Extended research piece (3,000-5,000 words)
- ✅ `sermon` — Teaching for oral delivery (2,000-3,000 words)
- ✅ `summary` — Brief overview (200-400 words)
- ✅ `blog_post` — Casual web content (600-1,000 words)

**Location:** `api/config/writer_templates.yml`

### M.3 Planner Agent

**Status:** ✅ Complete
**Impact:** High
**Effort:** Medium
**Implemented:** 2026-02-04

A project orchestrator that breaks complex writing projects into research and writing tasks.

**Key Design Decisions:**
1. **External loop, not recursive routing** — Planner creates `pipeline_tasks`, returns plan to user. User approves/triggers each step. Each task routes through normal `router.route()`.
2. **Summary-based context passing** — Store research output as 500-1000 word `output_summary` plus `output_conversation_id` link. Writer receives summary, not full conversation history.
3. **Conversational clarification** — Planner asks questions as its response. No special callback mechanism.
4. **Planning mode detection** — Derived from `pipeline_tasks` state: if active project has tasks not all complete, conversation is in planning mode.

**Provider:** Anthropic (Claude) — Planning is structured reasoning, not theological analysis.

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS pipeline_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,          -- 'research', 'draft', 'review', 'revise'
    task_description TEXT NOT NULL,
    agent TEXT NOT NULL,              -- 'researcher', 'writer', 'planner'
    status TEXT DEFAULT 'pending',    -- 'pending', 'active', 'waiting_review', 'complete'
    input_context TEXT,               -- JSON: references to prior task outputs
    output_summary TEXT,              -- Brief summary of what this task produced
    output_conversation_id INTEGER,
    sequence_order INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

### M.4 Intent Routing Updates

**Status:** ✅ Complete
**Implemented:** 2026-02-04

Route to Planner when:
- ✅ Request mentions "plan," "organize," "break down" + project/writing
- ✅ "multi-step" or "complex" project patterns
- ✅ Active pipeline exists in project (check existing plan)

Route to Writer directly when:
- Simple, bounded writing tasks ("write me a paragraph")
- Rewording, editing, short-form content
- No implied research need

### Implementation Summary

All M.1-M.4 items complete:
- ✅ M.1: Writer wired to LibrarySearchService
- ✅ M.2: Writer templates (6 content types)
- ✅ M.3: Planner agent with pipeline_tasks storage
- ✅ M.4: Router patterns for "plan" intent
3. Add Planner agent and pipeline_tasks table (Phase C)
4. Wire Planner task execution (Phase D)
5. Wire Pipeline UI in right panel (Phase E)

### Design Document

Full specification: User's design document provided 2026-02-04 with Claude Code review feedback incorporated.

---

## N. Code Agent (Claude Code-like CLI Tool)

**Status:** 🟢 Complete (Phases A-D)
**Maps To:** New capability (CLI tool using LLM infrastructure)
**Created:** 2026-02-04
**Implemented:** 2026-02-04
**Decision Document:** `docs/decisions/2026-02-04-code-agent.md`

### Purpose

A Claude Code-like interactive coding agent built into the Tamor ecosystem. CLI-first tool that provides a tool-use conversation loop for filesystem operations.

### Scope

**What it is:**
- Standalone terminal application (`tools/tamor_code.py`)
- Uses Tamor's LLM infrastructure (`llm_service.py`, `AGENT_PROVIDER_MAP`)
- Interactive tool-use loop: read → edit → verify → repeat

**What it is NOT:**
- Not a web UI feature (CLI-first design)
- Not a replacement for Claude Code (insurance policy + provider-agnostic)

### Key Design Decisions

1. **Extend LLMProvider ABC** — Add `supports_tool_use()` and `tool_use_completion()` methods
2. **Shared HTTP retry utility** — `api/utils/http_retry.py` benefits all providers
3. **Path sandboxing** — `PathSandbox` class restricts writes to working_dir, allows configurable read paths
4. **Configurable iteration limit** — `--max-iterations` flag with 80% warning threshold
5. **Provider: Anthropic (Claude)** — Best tool-use support via native API

### Tools

| Tool | Purpose |
|------|---------|
| `read_file` | Read file contents (line ranges supported) |
| `write_file` | Create or overwrite files |
| `patch_file` | Surgical string replacement (must be unique) |
| `list_directory` | Directory listing with depth control |
| `run_command` | Shell command execution |
| `git_status/diff/commit` | Git integration |

### Safety Mechanisms

- Path sandboxing (writes restricted to working_dir)
- `--allow-read` for read-only access to external paths
- Git checkpoint on session start (auto-stash)
- Confirmation gates for commits and dangerous commands
- Iteration limit with warning at 80%
- `/undo` command (soft-reset last commit)

### Implementation Phases

| Phase | Description | Status |
|-------|-------------|--------|
| A | LLM service extension (dataclasses, `tool_use_completion()`) | ✅ Complete |
| B | Tools (`code_tools.py`, `PathSandbox`) | ✅ Complete |
| C | Agent loop (`code_agent.py`) | ✅ Complete |
| D | CLI (`tamor_code.py`) | ✅ Complete |
| D.5 | Streaming output | ⏳ Future enhancement |
| E | Polish (system prompt tuning, project context) | ⏳ Ongoing |

### Files Created/Modified

| File | Change |
|------|--------|
| `api/utils/http_retry.py` | NEW — Shared retry utility |
| `api/services/llm_service.py` | Add dataclasses, ABC methods, Anthropic implementation |
| `api/services/agents/code_tools.py` | NEW — Tool definitions and implementations |
| `api/services/agents/code_agent.py` | NEW — Tool-use conversation loop |
| `api/services/agents/__init__.py` | Export CodeAgent and related classes |
| `tools/tamor_code.py` | NEW — CLI entry point |
| `tools/tamor-code` | NEW — Shell wrapper script |
| `api/tests/test_code_tools.py` | NEW — Tool unit tests |
| `api/tests/test_code_agent.py` | NEW — Agent integration tests |
| `Makefile` | Add `make code` target |

### Design Document

Full specification: `docs/decisions/2026-02-04-code-agent.md`

---

## O. Library Maintenance

### 25. Library Health Check & Path Reconciliation
**Status:** 🟡 Parked
**Maps To:** Phase 7.2 – Library Ingest Pipeline / Phase 8 – Trust, Restraint, and Completion
**Created:** 2026-02-04

**Purpose:** Detect and repair broken file paths in the library when files are renamed or moved on the NAS, without requiring re-indexing.

**Core Insight:** `file_hash` (SHA-256) is the true identity of a file. The path is just a locator. Since chunks and embeddings are linked by `library_file_id` (not by path), updating the stored path on an existing record preserves all indexed data and project references with zero re-indexing cost.

**Proposed Features:**

1. **Orphan Detection** — Compare `stored_path` against filesystem; identify records whose files no longer exist at the recorded path.
2. **Hash-Based Reconciliation** — For each orphaned record, scan the library mount for files matching the same `file_hash`. If found at a new path, update `stored_path` and `filename`.
3. **Health Report** — Summary: total files vs. on-disk, orphaned records, relocated files, new files.
4. **Auto-Repair Mode** — Optional flag for unambiguous matches (one orphan → one hash match). Ambiguous cases flagged for manual review.
5. **Dry Run** — Preview reconciliation before committing changes.

**Implementation Scope:**

| Component | File | Change |
|-----------|------|--------|
| Health check service | `api/services/library/health_service.py` | New service: scan, detect orphans, match by hash, report |
| Path update method | `api/services/library/library_service.py` | `update_path(file_id, new_path)` — updates `stored_path` and `filename` |
| API endpoints | `api/routes/library_api.py` | `GET /api/library/health` (report), `POST /api/library/health/reconcile` (repair) |
| UI | Library manage view | Health status indicator, reconciliation action button |

**Edge Cases:**
- File content changed AND moved → hash won't match; treated as orphan + new file (correct — old index is stale)
- Duplicate content at multiple paths → hash matches multiple files; flag for manual decision
- File deleted entirely → orphan with no match; offer to remove record or keep as "missing"

**Dependencies:** Phase 7.1 Library Schema (complete), Phase 7.2 Ingest Pipeline (complete), `LibraryStorageService.compute_file_hash()` (complete), `LibraryScannerService` directory walking (complete).

**Effort Estimate:** Small-medium. Most infrastructure exists.

**Open Questions (to resolve before building):**

1. **Scan performance** — Walking the full NAS mount to build a hash→path map could be slow at scale. Optimization: only hash new/unrecognized files on disk; orphan matching uses existing stored hashes. Worth confirming this is sufficient.

2. **Missing vs. deleted file state** — When an orphan has no hash match, the design offers "remove record" or "keep as missing." Consider adding a `status` column to `library_files` (e.g., `active`/`missing`/`archived`) so missing files stop appearing in searches but records aren't destroyed. Avoids a destructive binary choice.

3. **Trigger mechanism** — Scoped as manual/batch. Is that sufficient long-term, or should it run on startup or on a schedule? Single-user context suggests manual is fine, but worth confirming.

4. **UI priority** — The health report is useful, but a CLI/API-first approach (run the check, review JSON, approve repairs) may be enough initially. UI could come later if the workflow proves valuable.

---

## P. Output & Publishing

### 26. Teaching Video Pipeline
**Status:** 🟡 Parked (Vision Captured)
**Maps To:** Future phase (Phase 9.x or "Output & Publishing" phase)
**Created:** 2026-02-05

**Purpose:** Automated pipeline that transforms a topic into a downloadable teaching video (MP4): library-grounded research → structured slide content → AI-generated illustrations → local TTS narration → video composition. A 5–7 slide teaching, roughly 3–5 minutes, with every claim traceable to a library source.

**Origin:** Competitive analysis of 119 Ministries' AI Assistant (119assistant.ai). They announced auto-generated teaching videos as a coming feature. Tamor's version differs fundamentally: grounded in library sources with citations, custom AI illustrations, local narration, and epistemic honesty preserved — not a black-box GPT wrapper.

**The Six-Stage Pipeline:**

| Stage | Description | Tool | Status |
|-------|-------------|------|--------|
| 1. Research | Researcher agent queries Global Library | Existing Researcher + Library | ✅ Built |
| 2. Structure | Writer produces structured slide YAML (title, points, notes, image prompts, citations per slide) | Writer agent with new output format | 🔶 New output mode |
| 3. Illustration | Custom AI image per slide via Grok Imagine | xAI `grok-imagine-image` API | 🔶 New method on existing provider |
| 4. Slide Composition | Layer text content over illustrations → PNG | HTML templates + Playwright screenshot | 🔶 New component |
| 5. Narration | Piper TTS reads speaker notes per slide | Existing `tts_service.py` | ✅ Built |
| 6. Video Assembly | Combine slide images + audio → MP4 | FFmpeg or MoviePy | 🔶 Glue code |

**Structured Output Format (Stage 2):**
Writer produces YAML with per-slide: `type` (title/content/scripture/summary), `heading`, `points`, `notes` (narration script), `image_prompt`, `sources` (chunk_id + source name). This is the linchpin — everything downstream depends on this format being right.

**Grok Imagine Integration:**
- Image generation: `grok-imagine-image` — text-to-image, 16:9 aspect ratio, ~$0.02–0.05/image
- Video generation: `grok-imagine-video` — optional animated title cards only (not for teaching content)
- Add `generate_image()` method to existing xAI provider in `llm_service.py`

**Cost Per Teaching:** Under $1 (7 images ~$0.35, Writer generation ~$0.10, TTS free, FFmpeg free).

**Prerequisites (do NOT start pipeline work until these are met):**
- 2–3 full teachings written through Tamor's existing Writer workflow
- Clear sense of what good structured output looks like from real experience
- Library content sufficiently rich for grounded research
- Writer agent tested and tuned through real content production

**Natural Sequence:**
1. **Now → April 2026:** Foundation work (library expansion, real research/writing workflows, Writer tuning)
2. **April → May 2026:** Writer structured output mode + Grok Imagine wiring (2–3 sessions)
3. **Late May → June 2026:** Slide composition + video assembly + pipeline template (3 sessions)
4. **June → July 2026:** Polish (templates, transitions, thumbnails, voice selection)

**Actual pipeline-specific development: 4–6 focused sessions.** The first 2–3 months are prerequisite work you'd be doing anyway.

**Open Questions & Design Notes:**

1. **Stage 2 is the linchpin.** The structured YAML from Writer determines image prompt quality, narration pacing, and citation integrity. Don't codify the schema until you've written enough real teachings to know what good output looks like.

2. **Slide composition: prefer HTML templates → Playwright screenshot.** Most flexible for layout iteration (CSS not code), easiest for typography, Playwright already known in this project (OLL scraping). python-pptx is clunky for custom design; Pillow is pixel-pushing pain for text layout.

3. **Missing: human review gate before render.** Pipeline should have an explicit `waiting_review` step after Stage 2 (structured output) and optionally after Stage 3 (generated images) before committing to narration and video assembly. The `pipeline_tasks` system already supports `waiting_review` status — use it. Don't spend image generation credits on content the user hasn't approved.

4. **Image generation should be provider-abstract.** Grok Imagine pricing could change. The `generate_image()` method should be on the provider ABC, not xAI-specific, so local Stable Diffusion could be swapped in later.

5. **Verse pop-ups → in-video Scripture treatment.** The `scripture` slide type already has full verse text and citations. Consider a distinctive visual treatment for Scripture slides (different layout, typography, background) as a natural Stage 4 enhancement.

6. **119 Ministries Competitive Analysis** — Full comparison saved in vision document. Key takeaway: 119 proved the market for AI-assisted Torah-positive Bible study tools. Their weakness is depth (polished ChatGPT wrapper with good UX). Tamor is a research instrument. Features worth adapting are mostly presentation-layer (verse pop-ups, mode descriptions, YHWH rendering option). Core architectural difference is philosophical and shouldn't change.

**Features Worth Adapting from 119 (separate from video pipeline):**

| Feature | Effort | Notes |
|---------|--------|-------|
| Inline verse pop-ups (click/hover Scripture refs → SWORD/Sefaria preview) | Medium | Natural fit for chat panel |
| Mode descriptions in UI ("What this mode does / Best for / Not for") | Low | Phase 3.4 candidate |
| YHWH rendering option (LORD→YHWH in reference text) | Low | Display preference |
| Prompt templates library (reusable research prompts) | Low-Medium | Extensions candidate |
| "Test everything" footer on scholarly responses | Low | Personality config |

**Full Vision Document:** `Roadmap/teaching-video-pipeline-vision.md`

**Dependencies:** Phase 7 Global Library (complete), Phase 6.2 Multi-Agent (complete), Piper TTS (complete), xAI provider (complete), Pipeline service (complete). New: xAI SDK image generation, slide composition tooling, FFmpeg.

**Effort Estimate:** Medium overall, but spread across months with prerequisite work front-loaded.

---

### 27. Inline Scripture Pop-ups
**Status:** 🟡 Parked
**Maps To:** Phase 3.4 – Interface Restoration / Chat UI
**Created:** 2026-02-05
**Origin:** 119 Ministries competitive analysis

**Purpose:** Click or hover on Scripture references in chat responses to see inline verse preview via SWORD/Sefaria integration.

**Implementation:** Detect Scripture reference patterns in rendered chat messages (e.g., "Genesis 1:1", "Col 2:16-17"), wrap in interactive elements, fetch verse text from existing SWORD module integration on hover/click.

**Dependencies:** SWORD modules installed (KJV, ASV, YLT, OSHB, LXX, SBLGNT, TR — all complete). Sefaria API integration (existing).

**Effort:** Medium. Reference detection regex + UI component + SWORD/Sefaria fetch.

---

## Q. Digital Library Expansion

### 28. Ebook Acquisition Pipeline
**Status:** 🟢 Approved
**Maps To:** Phase 7 – Global Library System (post-completion enhancement)
**Created:** 2026-02-05

**Purpose:** Automated pipeline from book purchase to indexed library: Kindle/EPUB → Calibre (DRM removal + conversion) → NAS inbox → auto-ingest → Tamor library.

**Pipeline:**
```
Purchase → Calibre (DRM removal + EPUB conversion) → NAS Inbox → Auto-Ingest → Tamor Library
```

**Calibre Setup (one-time):**
- Install: `sudo apt install calibre`
- Library location: `/mnt/library/calibre/` (NAS-backed)
- DeDRM plugin from noDRM/DeDRM_tools for Kindle DRM removal
- Auto-convert to EPUB on add

**Acquisition Priority:**
1. Internet Archive (free, IA Harvester already built)
2. DRM-free EPUB (publisher direct, Google Play) → drop straight to NAS
3. Kindle purchase → Calibre + DeDRM conversion

**NAS Inbox Watcher (new service):**
- Monitor `/mnt/library/ebook-inbox/` for new files
- Extract metadata (author, title) from EPUB
- Route to destination folder based on publisher/source rules
- Auto-ingest into Tamor library, auto-assign to collection
- Config-driven publisher → folder → collection mapping

**File:** `api/services/library/inbox_watcher.py`
**Config:** `config/library_inbox.yml`

```yaml
inbox_path: /mnt/library/ebook-inbox/
scan_interval_seconds: 300
supported_extensions: [.epub, .pdf, .mobi]
publisher_rules:
  - match_field: publisher
    pattern: "Pronomian Publishing"
    destination: books/pronomian-publishing
    collection: "Pronomian Publishing"
  - match_field: publisher
    pattern: "First Fruits of Zion"
    destination: books/ffoz
    collection: "First Fruits of Zion"
default_destination: books/uncategorized
auto_index: true
delete_from_inbox: true
```

**Open Questions & Design Notes:**

1. **Cron over watchdog for MVP.** The `watchdog` library adds a dependency for something a 5-minute cron job handles just as well. `watchdog` is appropriate when you need sub-second response to filesystem events; for an ebook inbox that gets a new file once a week, cron is simpler, more predictable, and already available. Start with cron, graduate to watchdog only if scan overhead becomes a problem.

2. **DeDRM is personal-use only.** Noted in spec, reiterating: this is for personally purchased content in a single-user research library. The tooling should not be designed for or exposed as a sharing pipeline.

**Dependencies:** Phase 7 Global Library (complete), Library Collections (complete), EPUB parsing (complete).

**Effort:** Low-medium. Calibre setup is manual one-time. Inbox watcher is a small service.

---

### 29. Calibre Content Server Integration
**Status:** 🟢 Approved
**Maps To:** Phase 7 – Global Library System (reading layer)
**Created:** 2026-02-05

**Purpose:** Use Calibre's built-in web content server for full-fidelity EPUB reading. Don't reinvent the wheel — EPUB rendering is a solved problem.

**Setup:**
- `calibre-server /mnt/library/calibre/ --port 8180 --enable-local-write`
- Run as systemd service (`calibre-server.service`)
- Accessible locally and on LAN (mobile reading)

**Tamor Integration:**
- "Read in Calibre" button on EPUB files in Library UI → opens Calibre reader in new tab
- Match between Tamor's `library_files` and Calibre's `metadata.db` (SQLite at library root)

**Design Principle:** Tamor's existing extracted-text reader stays for quick reference, TTS, and bookmarking. Calibre is for reading a full book cover-to-cover with proper rendering.

**Open Questions & Design Notes:**

1. **Calibre ↔ Tamor matching.** Matching by filename or title could be fragile (titles get truncated, filenames get cleaned up). Consider matching by file hash, or storing Calibre's `book_id` as a foreign reference in `library_files.metadata` JSON. Hash is more robust; Calibre book_id is simpler but couples the systems.

**Dependencies:** Calibre installed, NAS library mount.

**Effort:** Low. Calibre does the heavy lifting. Tamor just adds a button.

---

### 30. Library Audio Player
**Status:** 🟢 Approved
**Maps To:** Phase 5.5 – Integrated Reader (companion feature)
**Created:** 2026-02-05

**Purpose:** In-Tamor audio playback for MP3 files with synchronized Whisper transcript display, timestamp navigation, and persistent mini player.

**Features:**
- Playback controls: play/pause, seek, skip ±15s, speed (0.5x–2x)
- Transcript sync: highlight current Whisper segment as audio plays
- Timestamp nav: click transcript line → jump to that point
- Playlist/queue: play files in sequence (sermon series)
- Resume: remember position per file (reuse `reading_sessions` with content_type='audio')
- Mini player: collapsible bar persists while navigating other tabs

**Backend:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/library/<id>/audio` | GET | Stream audio (Range header support) |
| `/api/library/<id>/transcript` | GET | Whisper transcript with timestamps |
| `/api/audio/session` | POST | Get/create playback session |
| `/api/audio/session/<id>/position` | POST | Update position |
| `/api/audio/queue` | GET/POST | Playback queue |

**Frontend:**
- `AudioPlayer.jsx` — main player component
- `TranscriptSync.jsx` — scrolling transcript with highlight
- `MiniPlayer.jsx` — collapsed persistent player
- `AudioPlayerContext.jsx` — global state across tab switches

**Open Questions & Design Notes:**

1. **Mini player is polish, not MVP.** The persistent mini player with global AudioPlayerContext is the most complex UI piece here. Consider building the full player first (opens in a panel, stops if you navigate away) and adding persistence as a follow-up. The transcript sync and playback controls are the high-value features; the mini player is a UX nicety.

2. **Audio range requests.** Flask's `send_file()` handles Range headers but can be unreliable for large files under Gunicorn. If audio files are large (25+ MB MP3s), test thoroughly. If issues arise, consider serving audio directly from nginx via `X-Accel-Redirect`, or serving from the NAS via a static file route.

3. **Audio player is separate from Reader.** The existing Reader handles text content with optional Piper TTS. The audio player handles original audio files with Whisper transcripts. They serve different purposes and should remain separate components.

**Dependencies:** Phase 5.5 Reader (complete), Whisper transcription (complete, 441 files done), `reading_sessions` table (complete).

**Effort:** Medium. The player itself is straightforward; transcript sync requires careful timing logic; mini player adds UI complexity.

---

### 31. Active Reading Context ("Ask About This")
**Status:** 🟢 Approved
**Maps To:** Phase 6.2 – Multi-Agent Support (context enhancement)
**Created:** 2026-02-05

**Purpose:** Bridge between reading/listening and AI chat. Set a library item as active context so Tamor prioritizes it when answering questions — no need to say "in the book I'm reading..."

**How It Works:**
- Toggle "Set as Active" on any library item
- Tamor injects that item's chunks as prioritized context in chat
- System prompt note: "The user is currently reading/listening to: [title]. Prioritize this source."
- Visual indicator in chat header showing what's active
- Auto-set when opening audio player; manual clear or clear on inactivity

**API:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/context/active` | GET | Get current active context |
| `/api/context/active` | POST | Set active context `{content_type, content_id}` |
| `/api/context/active` | DELETE | Clear active context |

**Chat Integration:** In `chat_api.py`, check for active context → fetch chunks from that library file → inject as prioritized block before general library results.

**Open Questions & Design Notes:**

1. **"Clear after inactivity" needs a definition.** Timer-based (30 min)? Session-based (clear on new login)? Or just manual-only for MVP? Recommend manual-only initially — auto-clear risks surprising the user by losing context mid-study. Add timer-based clearing later if manual feels burdensome.

2. **This is the highest value-to-effort ratio item in this spec.** The API is 3 endpoints. The chat integration is a small addition to the existing context assembly. The UI is a toggle button and a badge. If you build nothing else from this spec, build this.

**Dependencies:** Library search service (complete), chat context injection pattern (complete).

**Effort:** Low. 3 API endpoints, minor chat_api change, toggle button + badge in UI.

---

### Implementation Order

**Phase A — Foundation (do first):**
1. Calibre installation and configuration (manual, one-time)
2. Calibre content server as systemd service
3. NAS folder structure for books (`/mnt/library/books/`)

**Phase B — Automation:**
4. Inbox watcher service (start with cron)
5. Publisher detection and auto-collection assignment
6. "Read in Calibre" button in Library UI

**Phase C — Audio Player:**
7. Audio streaming endpoint with range support
8. AudioPlayer component with playback controls
9. TranscriptSync component
10. Playback session tracking
11. *(Later)* AudioPlayerContext + MiniPlayer for persistence

**Phase D — Context Bridge:**
12. Active context API endpoints
13. Chat integration (context injection)
14. UI indicators (active reading badge, set-as-active buttons)

> **Note:** Phase D (Active Reading Context) could be built independently of Phases A–C. It's low-effort and high-value. Consider building it first if the reading/listening infrastructure isn't ready yet.

**Full Spec Document:** `Roadmap/digital-library-expansion-spec.md`

---

## Promotion Checklist

An item may be promoted to the authoritative roadmap only when:

- Phase alignment is clear
- Dependencies are known
- Scope is bounded
- Rationale is documented

---

## Notes

This document is intentionally expansive.
Stability is preserved by keeping promotion deliberate and infrequent.
