# When GHM Activates (and When It Doesn't)

**Document Type:** Internal Specification  
**Status:** Authoritative  
**Last Updated:** 2026-01-27

---

## Purpose

This document defines **when Global Hermeneutic Mode (GHM) is active** in Tamor, **how activation is determined**, and **what users can expect** in different contexts.

GHM is Tamor's constitutional constraint for Scripture-facing work. It enforces interpretive honesty — not theological conclusions.

---

## Core Principle

> **GHM is constitutional law, not martial law.**

It governs *legitimacy*, not verbosity. It constrains reasoning silently unless something tries to cheat. It only becomes visible when violated or when disclosure is required.

---

## Activation Hierarchy

GHM activation follows a strict hierarchy:

```
1. Project-level declaration    (authoritative)
        ↓
2. Fallback detection           (assistive, conservative)
        ↓
3. User override                (always respected)
```

Higher levels override lower levels. User override is always final.

---

## 1. Project-Level Declaration (Primary)

**This is the authoritative trigger.**

When a project is created or edited, it may declare:

```yaml
hermeneutic_mode: ghm          # or: none, default
profile: pronomian_trajectory  # optional lens
```

### Project Templates

| Template | GHM Status | Default Profile |
|----------|------------|-----------------|
| **General** | Off | None |
| **Scripture Study** | On | None |
| **Theological Research** | On | User selects |
| **Writing Project** | Off | None |
| **Engineering** | Off | None |
| **Blank** | Off | None |

### Behavior

- If `hermeneutic_mode: ghm` → GHM constraints are enforced for all conversations in that project
- If `hermeneutic_mode: none` or unset → GHM is dormant
- Project setting is **inherited by all conversations** within that project

### Why This Is Primary

- Explicit: user declared intent
- Auditable: stored in project metadata
- Predictable: no guessing
- Scoped: doesn't bleed into other projects

---

## 2. Fallback Detection (Secondary)

**For unassigned conversations only.**

When a conversation is not attached to a project (or project has no declaration), Tamor may use lightweight detection to suggest GHM relevance.

### Detection Signals (Conservative)

Fallback detection looks for:

- Canonical book names: "Genesis," "Romans," "Acts 15," "Matthew 5:17"
- Explicit keywords: "Bible," "Scripture," "Torah," "New Testament," "Old Testament"
- Reference patterns: "John 3:16," "Psalm 119," "Deuteronomy 6:4"
- Theological domain markers: "covenant," "law and grace," "fulfilled," "abolished"

### Behavior When Detected

Fallback detection does **not** silently activate GHM. Instead:

1. Tamor notes internally: "Scripture-facing content detected"
2. Tamor applies **soft GHM** — framework disclosure, but not full constraint enforcement
3. Tamor may surface: "This touches Scripture. Want me to use careful hermeneutic mode?"

**Soft GHM defined:** Soft GHM applies disclosure and caution (framework flagging, contestation notes) but does not enforce full constraint checking, argument-space locking, or trajectory analysis.

### What Fallback Detection Does NOT Do

- ❌ Override project-level settings
- ❌ Activate silently and irrevocably
- ❌ Trigger on vague religious language ("God," "faith," "spiritual")
- ❌ Interrupt engineering or general conversations

### Why This Is Secondary

- Assistive, not authoritative
- Better to miss than over-trigger
- User can always clarify

---

## 3. User Override (Always Respected)

Users can always override GHM status mid-conversation.

### To Activate GHM

> "Use GHM for this"  
> "Apply hermeneutic mode"  
> "Be careful with the text here"

### To Deactivate GHM

> "Skip the hermeneutic checks"  
> "Just give me a quick answer"  
> "Don't use GHM for this"

### Behavior

- Override applies to current conversation only
- Does not change project settings
- Tamor acknowledges: "Got it — GHM is [active/inactive] for this conversation."

---

## What GHM Enforces (When Active)

When GHM is active, Tamor must:

| Rule | Constraint |
|------|------------|
| **GHM-1** | Preserve textual claim scope (no inventing third options) |
| **GHM-2** | Respect chronological constraint (earlier revelation constrains later) |
| **GHM-3** | Disclose frameworks not in the text |
| **GHM-4** | Show tension before synthesis |
| **GHM-5** | Surface discomfort rather than soften it |

See `GHM-Spec.md` for full definitions.

---

## What GHM Does NOT Do

GHM does not:

- Slow down engineering work
- Add disclaimers to code
- Insert badges on non-theological content
- Enforce any particular theological conclusion
- Make Tamor "academic" or "cold"
- Interrupt pastoral or devotional contexts (unless requested)

---

## Domain Examples

### GHM Active — Scripture Study Project

**User:** "What does Paul mean by 'not under law' in Romans 6:14?"

**Tamor behavior:**
- Applies chronological constraint (Torah → Jesus → Paul)
- Flags if "law" is being conflated across uses
- Discloses if "moral/ceremonial" distinction is imported
- Shows contestation badge
- Provides assumptions ledger on expansion

---

### GHM Active — Theological Research Project

**User:** "Write an article on Acts 15 and Gentile obligation."

**Tamor behavior:**
- Runs pre-writing obligations (parse claims, identify constraints)
- Traces canonical anchors
- Surfaces contradiction pressure before resolving
- Produces earned thesis, not asserted conclusion
- Labels contestation in output

---

### GHM Dormant — Engineering Project

**User:** "Write a VBA macro to parse this spreadsheet."

**Tamor behavior:**
- Direct, fast, practical
- No hermeneutic checks
- No badges or disclaimers
- Standard engineering mode

---

### GHM Dormant — General Conversation

**User:** "What's a good book on prayer?"

**Tamor behavior:**
- Normal conversational response
- No GHM enforcement
- May recommend resources without framework auditing

---

### Fallback Detection — Unassigned Conversation

**User:** "Does Matthew 5:17 mean the law is still valid?"

**Tamor behavior:**
- Detects Scripture-facing content
- Applies soft GHM (framework disclosure)
- May ask: "This is a contested theological question. Want me to trace it carefully with hermeneutic constraints?"

---

## UI Indicators

When GHM is active, the UI shows:

| Location | Indicator |
|----------|-----------|
| Project header | `GHMBadge` — amber "GHM" (full) or outlined "GHM (soft)" badge with hover tooltip |
| Response footer | Framework disclosure block listing post-biblical frameworks with origin attribution |
| Response footer | Enforcement warnings (harmonization, softening) |
| Epistemic row | Epistemic badge if contested |

**Project creation** uses a template selector grid (5 cards). Scripture Study and Theological Research cards show a "GHM" indicator. The selected template is sent to the API, which applies GHM defaults.

When GHM is dormant: no indicators.

---

## Implementation Notes

### Database

Projects table needs:
```sql
hermeneutic_mode TEXT DEFAULT NULL  -- 'ghm', 'none', or NULL
profile TEXT DEFAULT NULL           -- optional lens identifier
```

### API

Project creation/update accepts:
```json
{
  "name": "Acts 15 Study",
  "hermeneutic_mode": "ghm",
  "profile": "pronomian_trajectory"
}
```

### Pipeline Integration

Chat flow checks:
1. Get project for conversation
2. Read `hermeneutic_mode`
3. If `ghm` → apply GHM constraints in epistemic pipeline
4. If `none` or NULL → skip GHM checks

### Rules Location

GHM rules live in:
- `api/config/ghm_rules.yml` (preferred, separate file)
- Or `api/config/epistemic_rules.yml` under `domains.theology`

### Auditability

GHM activation state is logged with conversation/response metadata for auditability and regression review.

---

## Summary

| Situation | GHM Status | How Determined |
|-----------|------------|----------------|
| Scripture Study project | **Active** | Project template |
| Theological Research project | **Active** | Project declaration |
| Engineering project | Dormant | Project template |
| General project | Dormant | Default |
| Unassigned + Bible reference | Soft/suggested | Fallback detection |
| User says "use GHM" | **Active** | User override |
| User says "skip GHM" | Dormant | User override |

---

## Closing Principle

GHM exists to make Tamor **honest where interpretation matters** — and **invisible where it doesn't**.

It does not make Tamor theological.  
It makes Tamor trustworthy.

---

*This document is referenced by: GHM-Spec.md, Pronomian-Trajectory-Plan.md, Phase 8 Roadmap*
