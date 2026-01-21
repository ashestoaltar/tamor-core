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

2.6 Structured Tasking (Partially Complete)

Detect tasks embedded in project content

Represent tasks structurally (not reminders yet)

Task database schema and API endpoints implemented

Phase 3 – Stability, Cleanup, and Refactoring (Next Active Phase)
3.1 Backend Refactor & Deterministic Safety

Remove legacy and dead code

Standardize API error responses

Add /health endpoint

Review and align migrations

LLM Provider Abstraction Layer:

Create unified LLM service interface

Centralize client initialization and configuration

Enable future multi-provider support (Phase 6.2 dependency)

Deterministic Safety Enforcement (Promoted):

Explicit separation between:

Deterministic responses (e.g., drawing numbers, exact lookups)

Probabilistic LLM responses

Hard-stop rules:

If a deterministic answer cannot be found, return a clear “not found”

Never fall through to the LLM for deterministic queries

Demo-safe behavior guarantees

3.2 UI Refactor

RightPanel state cleanup

Remove unused components

Fix scrolling and viewport issues

Introduce global CSS tokens

Improve mobile and accessibility foundations

3.3 Database Cleanup

Align migrations with live schema

Add migration version tracking

Add rollback and validation utilities

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

4.3 On-Disk Caching Layer

Cache summaries, embeddings, and insights

Improve performance for large libraries

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
| OpenAI for LLM (with abstraction planned) | Best quality/cost for chat; Phase 3.1 enables switching |
| SQLite | Single-user, file-based, zero config |
| React + Vite frontend | Fast dev iteration, familiar tooling |
| Cloudflare Tunnel | Secure remote access without exposing ports |

Companion Documents

Tamor – Roadmap Extensions & Proposals

Internal design notes

Phase-specific execution checklists (as needed)
