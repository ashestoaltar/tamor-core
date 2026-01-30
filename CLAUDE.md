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

## Session Notes

<!-- Add notes from sessions here -->
