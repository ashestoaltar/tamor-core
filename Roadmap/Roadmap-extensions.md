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
**Status:** 🟡 Idea
**Maps To:** Phase 4.1 – Auto-Insights Engine

- Detect contradictions across documents
- Identify missing specs or assumptions
- Highlight inconsistencies early

---

## B. Input, Media, and Accessibility

### 4. Voice-to-Text Input (Android-First)
**Status:** 🔵 Investigating
**Maps To:** Phase 3.2 – UI Refactor

- Browser-native speech-to-text
- Append-to-chat behavior
- Mobile-first UX

---

### 5. Audio Reading Mode (Read Aloud)
**Status:** 🟡 Idea
**Maps To:** Phase 5.3 – Media & Transcript Integration

- Read articles, summaries, and structured content aloud
- Simple TTS pipeline
- Explicitly non-authoritative delivery

---

## C. Knowledge Sources & Reference Backends

### 6. Reference-Only External Backends
**Status:** 🔵 Investigating
**Maps To:** Phase 6.3 – Plugin Framework

- Read-only integrations
- Clearly labeled as reference material
- Never presented as authoritative answers

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
