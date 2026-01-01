# Tamor Core

Tamor is a **self-hosted personal AI agent** designed for long-term use, with a focus on
persistent memory, explicit task orchestration, and transparent state management.

Unlike typical chat assistants, Tamor emphasizes **correctness, inspectability, and user
control** over autonomy or novelty.

---

## What Tamor Is

Tamor is:

- A **local-first, self-hosted AI agent**
- Built around **persistent memory** (SQLite, not ephemeral context)
- Capable of detecting, confirming, scheduling, and executing tasks/reminders
- **Project-aware**: conversations, tasks, and files are scoped intentionally
- UI-driven, with explicit state boundaries between chat, tasks, memory, and execution

Tamor prioritizes reliability over cleverness.

---

## What Tamor Is Not

Tamor is **not**:

- A SaaS chatbot or ChatGPT wrapper
- A roleplay persona or novelty agent
- A niche-content assistant (music, tarot, etc.)
- An autonomous agent that acts without confirmation

Autonomy is intentionally constrained.

---

## Who Tamor Is For

Tamor is intended for:

- Engineers exploring **agent architectures**
- Users who want a **long-running, stateful assistant**
- Projects where **trust and correctness** matter more than speed
- Self-hosters who value **local control**

Tamor is not optimized for casual chatbot usage or mass consumer deployment.

---

## High-Level Architecture

Tamor consists of four layers:

UI (React)
↓
API (Flask)
↓
Agent Logic
↓
Memory Store (SQLite)

yaml
Copy code

Each layer has a clearly defined responsibility.

For details, see:
- `docs/architecture.md`
- `docs/tasks.md`
- `docs/philosophy.md`

---

## Task & Reminder System (Core Feature)

The task system is one of Tamor’s most mature components.

### Lifecycle

User message
→ task detection
→ task persisted (needs_confirmation | confirmed)
→ UI attaches TaskPill
→ user action (if required)
→ executor runs confirmed tasks
→ task completed / cancelled

yaml
Copy code

### Key Guarantees

- Unconfirmed tasks never execute
- Executor only runs `status = confirmed`
- UI reflects DB truth (never infers state)

---

## Project Status

- 🟢 Task / reminder system: stable
- 🟢 UI state & persistence: stable
- 🟡 Memory ingestion & synthesis: evolving
- 🟡 Agent reasoning depth: intentionally conservative
- 🟡 Documentation: actively improving

Tamor is under active development but already suitable for daily personal use.

---

## For Reviewers & Collaborators

If you are evaluating or contributing:

1. Start with `docs/architecture.md`
2. Read `docs/tasks.md` to understand the lifecycle
3. Review `docs/philosophy.md` for design intent
4. Read `CONTRIBUTING.md` before proposing changes

Some parts of Tamor are intentionally conservative and state-sensitive.

---

## License

This project is currently shared for review and collaboration purposes.
A formal open-source license may be added later.
