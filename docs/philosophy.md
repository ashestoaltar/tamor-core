# Agent Philosophy

Tamor is built on the belief that a useful AI agent must be **trustworthy over time**, not
impressive in a single interaction.

As a result, Tamor deliberately avoids hidden autonomy, speculative actions, and UI-driven
state inference.

---

## Core Principles

### 1. State is sacred
All important agent state is explicit, persisted, and inspectable.
Nothing “just happens.”

### 2. Confirmation over autonomy
Tasks do not execute without clear user approval.
Ambiguity defaults to safety.

### 3. Persistence over cleverness
Durable memory and traceable decisions are favored over short-term reasoning tricks.

### 4. Separation of concerns
- UI reflects state
- Agent reasons about intent
- Executor performs actions

No layer overrides another.

### 5. The agent is a collaborator, not a controller
Tamor assists, remembers, and organizes — it does not decide on the user’s behalf.

---

## Design Consequence

Tamor may feel more conservative than novelty agents.
That conservatism is intentional.

The goal is an assistant that remains reliable weeks, months, and years later —
not one that surprises the user today.
