# Contributing to Tamor

Thanks for your interest in Tamor.

Before proposing changes, please understand the following constraints.

---

## Non-Negotiable Rules

- Do not bypass task confirmation
- Do not allow executor to run unconfirmed tasks
- Do not merge task state into chat messages
- Do not introduce secondary databases
- Do not add hidden autonomy

---

## Sensitive Areas

Be cautious when modifying:

- Chat hydration / message merge logic
- Task attachment logic
- Executor polling behavior
- Task status transitions

These areas are intentionally conservative.

---

## Preferred Contributions

Good contributions include:

- Documentation improvements
- UI polish that reflects existing state
- Tooling around inspection and visibility
- Memory ingestion enhancements

---

## Philosophy

Tamor values:

- clarity over novelty
- correctness over speed
- trust over autonomy

If your proposal aligns with these values, it’s welcome.
