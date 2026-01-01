# Task & Reminder System

This document describes the complete task lifecycle in Tamor.

---

## Overview

Tasks are first-class entities.
They are persisted, inspectable, and explicitly controlled.

---

## Lifecycle

User message
→ task detection
→ task persisted
→ UI attaches TaskPill
→ user action (if required)
→ executor runs task
→ task completed / cancelled

yaml
Copy code

---

## Task Statuses

| Status | Meaning |
|------|--------|
| needs_confirmation | Awaiting user approval |
| confirmed | Approved for execution |
| completed | Executed successfully |
| cancelled | Cancelled before execution |
| dismissed | Removed without execution |

---

## Confirmation Rules

- Explicit one-shot times auto-confirm
- Relative but specific times auto-confirm
- Vague times require confirmation
- Recurring tasks require confirmation

---

## UI Representation

- Tasks are stored against the **user message**
- TaskPill renders on the **next assistant message**
- TasksPanel provides safe global management

---

## Executor Rules

- Executor only runs confirmed tasks
- Unconfirmed tasks never execute
- UI state does not influence executor decisions

---

## Why This Design Exists

This design prevents:

- accidental execution
- hidden state
- UI-driven behavior
- task “ghosting”

Every task is visible and controllable.
