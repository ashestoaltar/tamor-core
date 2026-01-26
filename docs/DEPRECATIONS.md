# Tamor Deprecations

This document tracks deprecated features, APIs, and code paths.

---

## Deprecated in Phase 8

### Removed

| Item | Reason | Removed In |
|------|--------|------------|
| `MemoryList.jsx` | Replaced by Memory tab | 3.4.1 |
| `MemoryCard.jsx` | Replaced by Memory tab | 3.4.1 |
| `memory.css` | Orphaned styles | 3.4.1 |
| `intent_old.py` | Legacy intent detection | 3.1 |
| Various `.bkp` files | Backup files in repo | 3.1 |

### Deprecated (Removal Planned)

| Item | Reason | Deprecation | Planned Removal |
|------|--------|-------------|-----------------|
| None currently | | | |

---

## API Stability

### Stable APIs (No Breaking Changes)

- `/api/chat` — Core chat endpoint
- `/api/projects/*` — Project CRUD
- `/api/files/*` — File management
- `/api/library/*` — Library system (Phase 7)
- `/api/references/*` — Scripture references
- `/api/conversations/*` — Conversation management
- `/api/messages/*` — Message retrieval
- `/api/memory/*` — Memory system
- `/api/system-status` — System status (Phase 8.4)

### Experimental APIs (May Change)

- `/api/pipelines/*` — Project pipelines
- `/api/plugins/*` — Plugin framework

### Personal Addons (Not Core Tamor)

- `/stremio/christmas/*` — Stremio Christmas movie playlist addon

---

## Configuration Stability

### Stable Configuration

- `config/modes.yml` — Assistant modes
- `config/personality.yml` — Tamor personality
- `config/epistemic_rules.yml` — Epistemic rules

### Experimental Configuration

- None currently

---

## Deprecation Policy

1. Features are deprecated with at least one version notice
2. Deprecated features are documented here
3. Deprecated APIs return warning headers when possible
4. Removal happens in the next minor version at earliest

---

## Code Audit Results

### Phase 8.5 Audit (2026-01-26)

Ran comprehensive audit for unused code:

**React Components:** All components in `ui/src/components/` are imported and used.

**CSS Files:** All CSS files have corresponding imports.

**Python Files:** All Python modules in `api/` are imported or serve as entry points.

**Backup Files:** No `.bkp`, `.backup`, `.orig`, or `*_old.*` files found in repository.

**Build Artifacts:** No `__pycache__`, `.pyc`, or `node_modules` tracked in git.

**Result:** Codebase is clean. No unused code requiring removal.

---

## How to Report Unused Features

If you notice unused code or features:

1. Check this document first
2. If not listed, open an issue or note in roadmap extensions
3. Don't remove without documentation
