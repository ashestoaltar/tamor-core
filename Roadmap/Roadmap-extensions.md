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
**Status:** 🔵 Investigating
**Maps To:** Phase 6.2 – Multi-Agent Support

- Primary LLM with secondary fallback
- Optional task-based routing (writing vs code vs analysis)
- Health-based failover

Constraints:
- Must preserve consistent tone
- Must not fragment memory semantics

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
