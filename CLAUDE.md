# Tamor

Personal AI workspace for research, knowledge management, and assisted creation. Local-first, privacy-respecting.

## Stack

- **Frontend:** React + Vite (`ui/`)
- **Backend:** Flask/Gunicorn (`api/`)
- **Database:** SQLite (`api/memory/tamor.db`)
- **Config:** YAML files in `config/`

## Key Documentation

- `docs/INDEX.md` — documentation hub
- `docs/architecture.md` — system design
- `docs/BOUNDARIES.md` — what Tamor will/won't do
- `docs/Features.md` — feature reference
- `Roadmap/Roadmap.md` — authoritative development plan (separate from docs by design)

## Key Concepts

### Multi-Agent Routing
Requests are routed to specialized agents based on intent:
- **Researcher** — source gathering, analysis
- **Writer** — prose synthesis
- **Engineer** — code generation
- **Archivist** — memory management

### Epistemic System
Tamor surfaces uncertainty and contested topics. Responses are classified:
- Deterministic (computed/exact)
- Grounded-Direct (restating text)
- Grounded-Contested (interpretive)
- Ungrounded (inferential)

Configured in `config/epistemic_rules.yml`.

## Configuration Files

| File | Purpose |
|------|---------|
| `config/modes.yml` | Assistant mode definitions |
| `config/personality.yml` | Tamor's identity and tone |
| `config/epistemic_rules.yml` | Truth signaling rules |
| `.env` | Environment variables, API keys |

## Conventions

- UI does not invent state — all truth comes from API
- Tasks require explicit user approval before execution
- Epistemic honesty: surface uncertainty, name interpretive lenses
- SQLite by design (single-user, zero config)

## Running

```bash
make dev        # start both API and UI
make api        # API only
make ui         # UI only
```

## Debugging

Add `?debug=1` to URL or `X-Tamor-Debug: 1` header to see routing decisions in API responses.

## Next Steps

- [ ] **Install Ollama + local LLM** — Add as fallback/offline provider
  ```bash
  # Install Ollama
  curl -fsSL https://ollama.com/install.sh | sh

  # Pull recommended model
  ollama pull llama3.1:8b
  ```
  Then wire into `api/services/llm_service.py` as secondary provider.

## Session Notes

### 2026-01-30 (Moltbook Research)
- **Created ~/moltbook-research/** — Side project for archiving AI agent social network posts
- Analyzed 100 posts for memory management strategies
- Added **Section J: Memory System Research Extensions** to Roadmap-extensions.md
  - Memory aging & decay, automated compression, token budget awareness, memory stats dashboard
  - All parked until after Phase 8
- Research artifacts: `~/moltbook-research/research/outputs/`

### 2026-01-29 (Phase 6.4 Complete)
- **Phase 6.4 Plugin Framework Expansion** — all 5 items complete:
  - Markdown export (plugin + API + UI menu)
  - PDF export (WeasyPrint, styled output)
  - Plugin config persistence (per-project settings in DB)
  - Reference caching with version tracking
  - Zotero integration (reads local SQLite, API ready)
- Backend-first approach: APIs ready, UI when friction demands it
- Zotero will be set up alongside NAS library system

### 2026-01-29 (Earlier)
- Created CLAUDE.md for session context
- Cleaned up roadmap inconsistencies (Focus Mode, completed extensions)
- Prioritized Phase 6.4 plugin items (Markdown/PDF export, Zotero, etc.)
- System maintenance: disabled ethernet (wifi only), removed Cardano (freed 316GB)
- Installed all SWORD modules (KJV, ASV, YLT, OSHB, LXX, SBLGNT, TR)
- Downloaded Whisper models (base, small, large-v2)
