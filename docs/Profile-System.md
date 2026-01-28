# GHM Profile System

**Document Type:** Internal Specification
**Status:** Authoritative
**Last Updated:** 2026-01-27

---

## Purpose

Profiles are interpretive lenses that operate **within** GHM constraints. They add observational questions and evidence weighting — they never prescribe conclusions or override GHM rules.

**Core principle:** Profiles may ask harder questions, never give harder answers.

---

## What Profiles Are

A profile is a YAML configuration file that layers additional interpretive behavior on top of GHM:

- **Evidence weighting** — biases for how ambiguous textual evidence is evaluated
- **Question prompts** — additional questions surfaced during analysis
- **Discrimination rules** — when to suppress or strengthen certain questions
- **Synthesis constraints** — epistemic braking on conclusions
- **Output constraints** — modality language and status lines
- **Plausibility notes** — historical context the LLM may reference
- **Guardrails** — strict prohibitions on profile overreach

Profiles do not change GHM's five core rules (GHM-1 through GHM-5). They do not change the canonical authority order. They do not prescribe theological conclusions.

---

## What Profiles Are NOT

- Not a theology engine
- Not a doctrine enforcer
- Not a replacement for GHM
- Not visible when GHM is inactive
- Not prescriptive ("you should keep X")

---

## Architecture

### File Layout

```
api/config/profiles/
  pronomian_trajectory.yml    # First profile
  [future profiles].yml
```

### Code

| Component | File | Role |
|-----------|------|------|
| Profile loader | `api/services/ghm/profile_loader.py` | Loads YAML, caches with `@lru_cache`, builds system prompt text |
| Prompt builder | `api/services/ghm/prompt_builder.py` | Injects profile section into GHM system prompt |
| Chat wiring | `api/routes/chat_api.py` | Passes `profile_id` from project settings to prompt builder |
| Validation | `api/routes/projects_api.py` | Validates profile exists and GHM is active on create/update |
| API endpoint | `GET /api/projects/profiles` | Returns available profiles for UI |
| UI badge | `ui/src/components/GHMBadge/GHMBadge.jsx` | Shows profile badge next to GHM badge |

### Data Flow

```
Project settings (profile column)
    ↓
get_project_ghm_status() → { active, mode, profile }
    ↓
get_ghm_prompt_addition() → build_ghm_system_prompt(frame_challenge, profile_id)
    ↓
build_ghm_system_prompt() calls get_profile_prompt_addition(profile_id)
    ↓
Profile section appended to GHM system prompt (after base, before frame challenge)
    ↓
Combined prompt sent to LLM
```

### Key Design Decisions

1. **Single file, not a package** — Profile logic lives in one file (`profile_loader.py`) within the existing `services/ghm/` package. No separate `services/profiles/` package. Profiles are a feature of GHM, not a parallel system.

2. **Prompt text, not structured data** — `get_profile_prompt_addition()` returns a fully formatted string ready for the system prompt. The prompt builder just appends it. No intermediate data objects passed between modules.

3. **Validation at write time** — Profile validity and GHM requirement are checked when a project is created or updated, not at chat time. This prevents invalid states from reaching the chat handler.

4. **LRU cache** — Profile YAML is cached with `@lru_cache(maxsize=16)`. Cache clears on API restart. No hot-reload mechanism (profiles change rarely).

5. **Requires GHM** — Profiles declare `requires_ghm: true`. The system rejects profile assignment on projects without GHM active. Profiles cannot operate outside GHM constraints.

---

## Database

The `profile` column was added in Migration 009 alongside GHM fields:

```sql
ALTER TABLE projects ADD COLUMN profile TEXT DEFAULT NULL;
```

Profile is a free-text string matching a YAML filename (minus `.yml`). Validation happens in the API layer, not the database.

---

## API

### `GET /api/projects/profiles`

Returns available profiles:

```json
[
  {
    "id": "pronomian_trajectory",
    "display_name": "Pronomian Trajectory (Synthesis Restraint)",
    "category": "theology.hermeneutics.canonical_trajectory",
    "requires_ghm": true,
    "version": "0.3"
  }
]
```

### Setting a Profile

```
PATCH /api/projects/:id
{ "profile": "pronomian_trajectory" }
```

Validation:
- Profile must exist as a YAML file in `api/config/profiles/`
- If profile has `requires_ghm: true`, project must have `hermeneutic_mode: 'ghm'`
- Setting profile to `null` removes it

---

## Pronomian Trajectory Profile

The first (and currently only) profile. A canonical continuity lens.

### Version History

#### v0.1 — Observational (Initial)

**Design goal:** Establish the profile pattern. Simple question prompts and evidence weighting.

- 3 evidence weights: chronological continuity (0.7), explicit over inferred (0.8), silence as silence (0.6)
- 5 question prompts: explicit discontinuity, warrant check, Nazarene practice, canonical trajectory, eschatological check
- 4 plausibility notes: Second Temple context, Nazarene practice, Jesus affirmation, Paul upholds
- 7 guardrails
- Output marker: "Trajectory Lens" badge

**Limitation identified:** Questions fired indiscriminately. Asked continuity questions even where discontinuity was explicit (e.g., Hebrews on sacrifices). No awareness of context.

#### v0.2 — Discriminating Continuity

**Design goal:** Smarter, not stronger. Better-timed questions, not more questions.

**Added:**
- Context-sensitive triggers with `context_filters` and `skip_when` conditions — questions only fire when contextually appropriate
- Repetition detector — classifies NT treatment of commands as reinforced, transformed, reinterpreted, or silent
- Scope-of-audience flag — asks whether instruction targets Israel, Gentiles, both, or humanity universally
- Burden of proof weighting (0.65) — abolition claims need stronger warrant than continuity claims
- Discrimination rules — explicit rules for when to suppress continuity questions (typological fulfillment, apostolic council, dominical reinterpretation) and when to strengthen them (pre-Sinai, Decalogue, Jesus restates, eschatology envisions)
- New guardrail: "Do not ask continuity questions where discontinuity is explicitly warranted"

**Limitation identified:** Even with smarter questions, synthesis paragraphs still slid from observation to conclusion. Apostolic practice was being converted to normative prescription without marking it as synthesis.

#### v0.3 — Synthesis Restraint (Current)

**Design goal:** Tighter epistemic braking. Stop exactly where Scripture stops.

**Problem solved:** Quiet conclusion creep — the tendency to convert apostolic patterns into universal norms, state theological inferences as commands, and introduce moral/ceremonial conclusions as facts.

**Added:**
- Synthesis constraints (3 rules):
  - No unmarked normativity — don't convert apostolic patterns into universal norms
  - No inference as command — don't state theological inferences as biblical commands
  - Mark synthesis as synthesis — explicitly label theological synthesis
- Output constraints:
  - Conclusion modality — descriptive language only ("the text presents..."), forbidden prescriptive phrases ("therefore Gentiles must...")
  - Status line — epistemic grounding summary at end of responses: what is explicit, what is described, what is inferred, what is unaddressed
- 3 new guardrails:
  - Never state Gentile obligation/non-obligation without explicit textual warrant
  - Never convert apostolic practice descriptions into universal prescriptions
  - Always mark theological synthesis as synthesis, not as biblical command

### Design Principles

1. **Observational, not prescriptive** — The profile asks "does the text say this ended?" It never says "the text says this continues, therefore keep it."

2. **Epistemic, not theological** — Burden of proof asymmetry is about interpretive logic (ending something requires a reason), not about Torah theology.

3. **Self-limiting** — Guardrails constrain the profile itself. The profile cannot assert Torah observance, prescribe practices, override GHM, or claim certainty.

4. **Context-aware** — Discrimination rules prevent the profile from asking inappropriate questions. It suppresses continuity questions where Hebrews explicitly addresses typological fulfillment. It strengthens them where commands are pre-Sinai or in the Decalogue.

5. **Transparent** — Every profile-influenced observation is labeled "trajectory lens." The disclosure statement appears in responses. The status line shows epistemic grounding.

---

## Response Formatting

GHM responses (with or without profiles) follow prose formatting rules:

1. Collapse headers into bold lead sentences
2. Prefer paragraphs over bullets (bullets only for 3+ distinct items)
3. Maximum 3 structural sections (frame challenge, textual analysis, summary)
4. Minimize vertical whitespace (one blank line = one idea shift)
5. Write to be read, not scanned

Profile observations integrate naturally into prose — they do not appear as separate bulleted sections.

---

## Future Profiles

The system is designed for multiple profiles. Potential future profiles:

- Dispensational trajectory (weights toward discontinuity)
- Covenantal trajectory (weights toward covenant theology categories)
- Historical-critical lens (weights toward source analysis)

Each would follow the same pattern: YAML config, evidence weighting, question prompts, guardrails, disclosure. Each would operate within GHM, not outside it.

No UI profile selector exists yet (no project settings modal). Profiles are currently set via API PATCH.

---

## Relationship to Other Systems

| System | Relationship |
|--------|-------------|
| GHM (base) | Profile operates within GHM. Cannot override GHM rules. Requires GHM active. |
| Frame Analyzer | GHM-level, not profile-level. Frame challenges fire on framework assumptions regardless of profile. |
| GHM Enforcer | GHM-level, not profile-level. Post-response constraint checking is unchanged by profiles. |
| GHM Detector | GHM-level. Fallback detection for unassigned conversations is profile-unaware. |
| Epistemic System | Independent. Epistemic badges (contested, debated) operate separately from GHM/profiles. |

---

## References

- `docs/GHM-Spec.md` — GHM core specification
- `docs/When-GHM-Activates.md` — Activation hierarchy
- `api/config/profiles/pronomian_trajectory.yml` — Profile definition
- `api/services/ghm/profile_loader.py` — Profile loader implementation
- `docs/changelog.md` — Implementation details per version

---

*This document is referenced by: GHM-Spec.md, When-GHM-Activates.md, Phase 8 Roadmap*
