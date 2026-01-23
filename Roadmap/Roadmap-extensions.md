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
- Explicit “not found” responses when certainty cannot be guaranteed
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
**Status:** 🟡 Idea  
**Maps To:** Phase 4.x – Intelligence Expansion

- Index approved network locations
- No file duplication
- Permission-aware access

---

## D. Media, Transcripts, and Long-Form Workflows

### 8. Bulk Audio → Text → PDF Pipelines
**Status:** 🟡 Idea  
**Maps To:** Phase 5.3 – Media & Transcript Integration

- Batch MP3 ingestion
- Transcription and formatting
- Export to searchable PDFs

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
- Mobile is not a smaller desktop — design for touch and voice first
- Depth on demand — simple by default, powerful when needed
- Developer tools are not user tools — separate concerns cleanly

**Subphases:**
1. **3.4.1 UI Audit & Developer Mode** — Categorize components, create DevModeContext, remove dead code
2. **3.4.2 Mobile-First Layout Refactor** — Bottom nav, drawer components, responsive breakpoints
3. **3.4.3 Voice Input/Output** — Web Speech API hooks, mic button, read-aloud, voice settings
4. **3.4.4 Focus Mode (Optional)** — Ultra-minimal voice-first view

**Promotion Edit:**
Add Phase 3.4 to main roadmap after Phase 3.3 Database Cleanup. Full specification included in promotion.

---

## F. Infrastructure & Storage

### 12. NAS-Backed Library Expansion
**Status:** 🔵 Investigating  
**Maps To:** Phase 4.3 – On-Disk Caching Layer

- Large-scale local storage
- RAID-backed libraries
- Indexed, not duplicated

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

