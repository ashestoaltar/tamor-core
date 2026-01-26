# Epistemic Honesty System

> Phase 8.2 Design Reference

This document describes the architecture and implementation of Tamor's epistemic honesty system — the unified pipeline for truth signaling, provenance transparency, and confidence enforcement.

---

## Architecture Overview

```
User message arrives
        ↓
Agent generates draft response
        ↓
┌─────────────────────────────────────────┐
│         EPISTEMIC PIPELINE              │
├─────────────────────────────────────────┤
│ 1. Classify answer type                 │
│    (deterministic/grounded/contested/   │
│     ungrounded)                         │
│                                         │
│ 2. Detect contested domains             │
│    (theology, history, ethics, etc.)    │
│                                         │
│ 3. Lint for risky certainty claims      │
│    (absolutist language, clarity)       │
│                                         │
│ 4. Attempt anchor attachment            │
│    (≤250ms budget, cached sources)      │
│                                         │
│ 5. Apply minimal repairs if needed      │
│    (sentence-level, not tone rewrite)   │
│                                         │
│ 6. Assign badge + metadata              │
└─────────────────────────────────────────┘
        ↓
Response with epistemic metadata
        ↓
UI renders with progressive disclosure
```

---

## Answer Classification (Four-Tier Model)

Every response is classified by provenance:

| Category | Definition | Example |
|----------|------------|---------|
| **Deterministic** | Computed, exact, from trusted data | "There are 12 items." / "Your next reminder is at 3:15 PM." |
| **Grounded–Direct** | Restating or summarizing explicit text | "Paul says X, then Y." / "Jeremiah 7 describes..." |
| **Grounded–Contested** | Grounded in text but interpretive, with live disagreement | "Romans 9 is about corporate election, not individual predestination." |
| **Ungrounded Synthesis** | No anchors, purely inferential | General reasoning without source backing |

**Key rule:** Grounded–Contested is not "less true." It means the claim requires a stated interpretive frame.

---

## Contested Domains

Six domains where contestation detection is active:

1. **Theology / doctrinal conclusions**
2. **Historical reconstruction** beyond explicit sources
3. **Authorship/dating debates**
4. **Prophecy interpretations**
5. **Denominational distinctives**
6. **Ethical application / contemporary mapping**

---

## Contestation Intensity Scale

| Level | Name | Meaning |
|-------|------|---------|
| **C1** | Intra-tradition nuance | Disagreement within the same broad interpretive family |
| **C2** | Cross-tradition split | Major traditions diverge (Reformed vs Arminian, etc.) |
| **C3** | Minority/novel position | Legitimate but not widely held historically |

**Key insight:** Contestation is relative to declared lens.

---

## Confidence Language Enforcement

**Core principle:** Don't enforce "confidence language." Enforce "confidence claims."

### What We Prevent
- "This proves…", "It's definitely…", "Always…", "Never…"
- Hard factual claims without deterministic backing or cited text

### What We Do NOT Do
- Auto-insert hedges everywhere
- Rewrite tone
- Add qualifiers to everything

### Repair Strategies

1. **Anchor, don't hedge** (preferred) — attach evidence, keep confident tone
2. **Minimal sentence rewrite** — only the offending sentence
3. **Clarifying question** — for high-stakes ungrounded claims

---

## Latency Budget

| Pass | Budget | Sources |
|------|--------|---------|
| Fast anchor | ≤250ms | Cached: project chunks, library cache, SWORD/Sefaria cache |
| Deep anchor | ≤800ms | Only if high-risk + user prefers accuracy |
| Fallback | — | Grounded–Contested framing or minimal rewrite |

---

## UI: Progressive Disclosure

### Primary Signal: Badge

Near timestamp or message footer:
- ✔︎ Deterministic
- ● Grounded
- ◐ Contested

### Secondary Signal: Popover (hover/long-press)

```
Contested interpretation
Level: Cross-tradition (C2)

This response reflects:
• Primary lens: [Project lens or default]
• Notable alternatives: [short labels]
```

### Tertiary Signal: Expandable "Why?"

2–4 bullet explanation of why the topic is contested.

---

## Configuration

`config/epistemic_rules.yml`:
- `risky_phrases`: absolutist verbs
- `theology_contested_markers`: patterns indicating contested claims
- `allowed_absolutes`: facts allowed in certain contexts
- `domain_overrides`: per-project settings

---

## Design Principles

1. **Anchor, don't hedge** — citations do the epistemic work
2. **Governed, not model-decided** — rules are authored and versioned
3. **Progressive disclosure** — complexity on demand, not by default
4. **Contestation is relative** — lens-aware, not absolute
5. **Transparency earns authority** — the badge doesn't weaken, it strengthens

---

## Target Voice

**Bad (overconfident):** "It was definitely about corporate election."

**Bad (formulaic):** "Based on the available information, it is possible that some scholars believe..."

**Good (Phase 8 voice):**
> My reading: Paul's argument in Romans 9 is primarily about God's covenant purposes and the identity of God's people (a "corporate election" lens).
>
> **Text anchors:** [key moves in the passage]
>
> **But:** Many readers (Augustinian/Reformed traditions) take the same chapters as individual election.

---

*Last updated: Phase 8.2*
