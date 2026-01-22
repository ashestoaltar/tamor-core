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

Phase 4 – Research & Intelligence Expansion
4.1 Auto-Insights Engine

Automatically generate insights on project upload

Detect:

Contradictions

Missing information

Key themes and assumptions

4.2 Multi-File Reasoning Mode

System-wide reasoning across all project documents

Dependency and logic consistency checks

4.3 On-Disk Caching Layer (Complete)

✅ Persistent embedding cache in file_chunks table

✅ Cache-first retrieval with on-demand generation

✅ Cache invalidation on project/file deletion

✅ Batch embedding with embed_many for efficiency

Phase 5 – Automation & Actions
5.1 File Actions

Rewrite files

Generate specs

Parameter extraction

5.2 Project Pipelines

Define structured workflows:

Research

Writing

Study

Long-form projects

5.3 Media & Transcript Integration

Ingest audio and video sources

Transcription pipelines

Structured summaries

Export to searchable formats

Phase 6 – Advanced Assistant Evolution
6.1 Long-Term Memory 2.0 (Governed Memory)

Category-based memory

Searchable and pinnable memory

Explicit memory governance rules:

Manual vs automatic memory

User consent for persistence

User-visible memory controls

6.2 Multi-Agent Support

Distinct assistant roles (e.g., researcher, writer, teacher)

Task-appropriate behavior models

Optional LLM routing (future)

6.3 Plugin Framework

Pluggable integrations

Importers and exporters

Read-only reference backends

Governance Rules

This roadmap is authoritative

New ideas must originate in Tamor – Roadmap Extensions & Proposals

Promotion requires:

Phase alignment

Clear rationale

Bounded scope

Dependency awareness

Roadmap Change Log
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
