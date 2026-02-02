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

## Notes

This document is intentionally expansive.
Stability is preserved by keeping promotion deliberate and infrequent.
