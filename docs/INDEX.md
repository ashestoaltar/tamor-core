# Tamor Documentation

Welcome to Tamor's documentation. This index provides access to all documentation.

---

## Quick Start

- **[Features Guide](Features.md)** — Complete feature reference with API examples
- **[Architecture](architecture.md)** — System design and component overview

---

## Core Concepts

### Philosophy & Boundaries

- **[Boundaries](BOUNDARIES.md)** — What Tamor will and won't do
- **[Philosophy](philosophy.md)** — Design principles and values

### System Behavior

- **[Tasks](tasks.md)** — Task and reminder lifecycle
- **[Deprecations](DEPRECATIONS.md)** — Deprecated features and APIs
- **[Epistemic System](epistemic-system.md)** — How Tamor handles truth and uncertainty

---

## Feature Documentation

### Research & Knowledge

- **Global Library** — Centralized document storage ([Features Guide](Features.md#global-library-system))
- **References** — Bible and scholarly sources ([Features Guide](Features.md#reference-integration))
- **Memory System** — Persistent knowledge storage ([Features Guide](Features.md#memory-system))

### Assistant Capabilities

- **Multi-Agent System** — Specialized assistant roles ([Features Guide](Features.md#multi-agent-system))
- **Pipelines** — Workflow templates ([Features Guide](Features.md#project-pipelines))
- **Focus Mode** — Distraction-free interface ([Features Guide](Features.md#focus-mode))

### Epistemic Honesty

- **Answer Classification** — How responses are categorized ([Epistemic System](epistemic-system.md))
- **Contested Topics** — How disagreement is surfaced
- **Confidence Rules** — Configured in `config/epistemic_rules.yml`

### Global Hermeneutic Mode

- **[GHM Specification](GHM-Spec.md)** — Core rules for Scripture-facing interpretation
- **[When GHM Activates](When-GHM-Activates.md)** — Activation hierarchy, templates, examples

---

## Operations & Maintenance

- **[System Configuration](system-config.md)** — Environment setup and configuration
- **[Maintenance Runbook](maintenance-runbook.md)** — Operational procedures

---

## Configuration

| File | Purpose |
|------|---------|
| `config/modes.yml` | Assistant mode definitions |
| `config/personality.yml` | Tamor's identity and tone |
| `config/epistemic_rules.yml` | Epistemic honesty rules |
| `.env` | Environment variables |

---

## Development

### Roadmap

- **[Roadmap](../Roadmap/Roadmap.md)** — Authoritative development plan
- **[Extensions](../Roadmap/Roadmap-extensions.md)** — Proposed features

### Internal Documentation

- **[Phase 3.4.1 UI Audit](phase-3.4.1-ui-audit.md)** — Component categorization results

---

## Document Status

| Document | Status | Last Updated |
|----------|--------|--------------|
| Features.md | ✅ Complete | v1.30 |
| BOUNDARIES.md | ✅ Complete | v1.29 (Phase 8.1) |
| DEPRECATIONS.md | ✅ Complete | v1.32 (Phase 8.5) |
| epistemic-system.md | ✅ Complete | v1.29 (Phase 8.2) |
| philosophy.md | ✅ Complete | Phase 1 |
| tasks.md | ✅ Complete | Phase 2 |
| architecture.md | ✅ Complete | v1.33 (Phase 8.6) |
| system-config.md | ✅ Complete | Phase 7 |
| maintenance-runbook.md | ✅ Complete | Phase 7 |
| GHM-Spec.md | ✅ Complete | v1.29 (Phase 8.2.7) |
| When-GHM-Activates.md | ✅ Complete | v1.29 (Phase 8.2.7) |
| INDEX.md | ✅ Complete | v1.33 (Phase 8.6) |

---

*Tamor documentation follows the principle: if it's not documented, it doesn't exist.*
