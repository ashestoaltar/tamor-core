# Tamor Architecture Overview

This document explains how Tamor is structured and why certain boundaries exist.

---

## High-Level Components

UI (React)
↓
API (Flask)
↓
Agent Logic
↓
Memory Store (SQLite)

yaml
Copy code

---

## UI Layer (React + Vite)

Key components:

- `ChatPanel`
- `TaskPill`
- `LeftPanel` (Conversations / Tasks)
- `TasksPanel`

### Rules

- UI does not invent state
- TaskPill attaches to the assistant message following the user message
- TasksPanel is isolated from chat hydration

Violating these rules causes UI instability.

---

## API Layer

Primary endpoints:

- `/api/chat`
- `/api/tasks`
- `/api/tasks/:id/confirm`
- `/api/tasks/:id/cancel`
- `/api/tasks/:id/complete`

The API enforces lifecycle rules and persistence.

---

## Agent Logic

The agent:

- detects tasks
- normalizes dates and recurrence
- assigns initial status
- never executes unconfirmed tasks

The agent is intentionally conservative.

---

## Executor

- Polling loop
- Selects `status = confirmed`
- Ignores UI state
- Updates DB after execution

---

## Memory Store

Single source of truth:

api/memory/tamor.db

diff
Copy code

Contains:
- conversations
- messages
- detected tasks
- long-term memory entries

No secondary databases should exist.
