# Tamor Changelog

Running log of issues, root causes, and fixes.

---

## 2026-01-27

### Feature: Conversation Message Search

**Problem:** Search only matched conversation titles. Users couldn't find conversations by message content (e.g., "that conversation where we discussed Acts 15").

**Fix:** Extended `global_search()` to also search `messages.content` via SQL LIKE. Message-matched results appear after title matches, with a truncated snippet showing the matching text. Frontend renders snippets below conversation titles in search results.

**Files changed:**
- `api/routes/search_api.py`
- `ui/src/components/LeftPanel/LeftPanel.jsx`
- `ui/src/components/LeftPanel/LeftPanel.css`

---

### Feature: Conversation Export

**Purpose:** Export any conversation as a downloadable markdown file.

**Implementation:**
- New endpoint: `GET /api/conversations/:id/export?format=markdown`
- Returns formatted markdown with title, export date, project name, and all messages with role labels
- Frontend adds a download button (arrow icon) in the chat header area
- Button visible on both mobile and desktop when a conversation has messages

**Files changed:**
- `api/routes/conversations_api.py`
- `ui/src/components/ChatPanel/ChatPanel.jsx`
- `ui/src/components/ChatPanel/ChatPanel.css`

---

### Feature: Pronomian Trajectory Profile v0.3 — Synthesis Restraint

**Problem:** Even with GHM + v0.2, responses slide from observation to synthesis too smoothly, converting apostolic practice into normative conclusions without marking them as synthesis.

**New in v0.3:**
- Synthesis constraints: no unmarked normativity, no inference-as-command, mark synthesis as synthesis
- Conclusion modality: descriptive language only ("the text presents..."), forbidden prescriptive phrases ("therefore Gentiles must...")
- Status line: epistemic grounding summary at end of responses (explicit / described / inferred / unaddressed)
- 3 new guardrails: no Gentile obligation statements without explicit warrant, no apostolic-to-universal conversion, always mark synthesis

**Profile loader updated:**
- Renders `synthesis_constraints` with bad/good examples
- Renders `output_constraints` (conclusion modality with allowed/forbidden phrases, status line format with examples)

**Files changed:**
- `api/config/profiles/pronomian_trajectory.yml`
- `api/services/ghm/profile_loader.py`

---

### Style: GHM response formatting — prose mode over outline mode

**Problem:** GHM responses read as study notes — excessive headers, bullet lists, vertical whitespace. Responses should read as polished prose.

**Fix:** Added formatting instructions to `build_ghm_system_prompt()`:
1. Collapse headers into bold lead sentences
2. Prefer paragraphs over bullets (bullets only for 3+ distinct items)
3. Maximum 3 structural sections (frame challenge, textual analysis, summary)
4. Minimize vertical whitespace (one blank line = one idea shift)
5. Write to be read, not scanned

**Profile integration note:** Profile observations integrate naturally into prose, not as separate bulleted sections.

**Files changed:**
- `api/services/ghm/prompt_builder.py`
- `api/services/ghm/profile_loader.py`

---

### Feature: Pronomian Trajectory Profile v0.2 — Discriminating Continuity

Upgrade to smarter, not stronger profile. Reduces noise, increases discrimination.

**New in v0.2:**
- Context-sensitive triggers with `context_filters` and `skip_when` conditions
- Repetition detector: classifies commands as reinforced, transformed, reinterpreted, or silent
- Scope-of-audience flag: Israel-specific, universal pre-Sinai, Gentile-addressed, or both
- Burden of proof weighting (0.65): abolition claims need stronger warrant than continuity
- Discrimination rules: suppress continuity questions where discontinuity is explicit (Hebrews on sacrifices, Acts 15), strengthen where pre-Sinai or Decalogue
- New guardrail: "Do not ask continuity questions where discontinuity is explicitly warranted"

**Profile loader updated:**
- Renders `context_filters`, `skip_when`, `categories` in system prompt
- Renders `discrimination_rules` (suppress/strengthen) section

**Files changed:**
- `api/config/profiles/pronomian_trajectory.yml`
- `api/services/ghm/profile_loader.py`

---

### Feature: GHM Profile System — Pronomian Trajectory

**Purpose:** Add a thin observational profile layer that operates WITHIN GHM. Profiles add questions and evidence weighting, never prescribe conclusions. Core rule: "Profiles may ask harder questions, never give harder answers."

**Profile Loader (`api/services/ghm/profile_loader.py`):**
- `load_profile()` — loads YAML profile definitions from `api/config/profiles/`, cached with `@lru_cache`
- `get_available_profiles()` — scans directory, returns metadata list
- `get_profile_prompt_addition()` — builds system prompt section from profile config (weighting, questions, plausibility notes, guardrails, disclosure)
- `is_valid_profile()` — existence check

**Profile Config (`api/config/profiles/pronomian_trajectory.yml`):**
- Evidence weighting: chronological continuity (0.7), explicit over inferred (0.8), silence as silence (0.6)
- 5 question prompts (explicit discontinuity, warrant check, Nazarene practice, canonical trajectory, eschatological check)
- 4 plausibility notes (Second Temple context, Nazarene practice, Jesus affirmation, Paul upholds)
- 7 guardrails (never assert, never prescribe, never override GHM, etc.)
- Output markers: "Trajectory Lens" badge, disclosure text

**Prompt Builder Update:**
- `build_ghm_system_prompt()` now accepts `profile_id` parameter
- Profile section injected after GHM base instructions, before frame challenge

**Chat API Wiring:**
- `get_ghm_prompt_addition()` passes `ghm_status.get('profile')` to prompt builder

**Projects API:**
- Profile validation on create/update: must exist as YAML file, must have GHM active if `requires_ghm: true`
- `GET /api/projects/profiles` — new endpoint returning available profiles

**UI:**
- GHMBadge accepts `profile` prop, shows "Trajectory Lens" secondary badge when active
- Profile badge with tooltip showing disclosure text

**Files changed:**
- `api/config/profiles/pronomian_trajectory.yml` (new)
- `api/services/ghm/profile_loader.py` (new)
- `api/services/ghm/prompt_builder.py`
- `api/services/ghm/__init__.py`
- `api/routes/chat_api.py`
- `api/routes/projects_api.py`
- `ui/src/components/GHMBadge/GHMBadge.jsx`
- `ui/src/components/GHMBadge/GHMBadge.css`
- `ui/src/components/LeftPanel/ProjectsPanel.jsx`

---

### Feature: GHM Frame Analyzer and Prompt Builder

**Frame Analyzer (`api/services/ghm/frame_analyzer.py`):**
- Detects when questions assume post-biblical frameworks (moral/ceremonial law, fulfilled=ended, law vs grace, old/new covenant replacement, works of the law, sabbath categorization)
- Returns challenge text that instructs the LLM to surface the assumption before answering within it
- Only fires under full GHM — frame challenge is argument-space locking, not just disclosure; soft GHM discloses after the fact per spec

**Prompt Builder (`api/services/ghm/prompt_builder.py`):**
- `build_ghm_system_prompt()` injects full GHM constraint set into LLM system prompt: canonical authority order, GHM-1 through GHM-5, response sequence
- Optionally includes frame challenge when a framework assumption is detected
- Wired into both fallback LLM path (system prompt append) and router path (via `ctx.ghm_frame_challenge` on researcher/writer agents)

**Files changed:**
- `api/services/ghm/frame_analyzer.py` (new)
- `api/services/ghm/prompt_builder.py` (new)
- `api/services/ghm/__init__.py`
- `api/services/agents/base.py` (added `ghm_frame_challenge` field to `RequestContext`)
- `api/services/agents/writer.py` (injects GHM prompt into system prompt)
- `api/services/agents/researcher.py` (injects GHM prompt into system prompt)
- `api/routes/chat_api.py` (added `get_ghm_prompt_addition()`, wired into both chat paths)

---

### Fix: GHM override short-circuits before LLM

**Symptom:** User says "skip GHM for this" and Tamor detects the override, but still sends the message to the LLM, which doesn't know what GHM is and responds with confusion.

**Root cause:** `check_user_ghm_override()` ran inside `apply_ghm_pipeline()`, which executes *after* the LLM response. The override was detected too late.

**Fix:** Moved override detection into the main `chat()` handler, before the router/LLM call. When a GHM override phrase is detected, the handler returns immediately with an acknowledgment ("Got it — GHM is now active/deactivated for this conversation.") and never sends the meta-command to the LLM.

**Files changed:**
- `api/routes/chat_api.py`

---

### Fix: Excessive vertical spacing in chat message list items

**Symptom:** Bullet-point responses had a visible gap between the bullet marker and the content text (e.g., above "Moral law:" and "Ceremonial law:").

**Root cause:** ReactMarkdown wraps list item content in `<p>` tags, which carry default margins. No list-specific CSS existed in `ChatPanel.css`.

**Fix:** Added rules to `.chat-bubble` for `ul`/`ol` margin, `li` spacing, and `li > p { margin: 0 }` with `li > p:first-child { display: inline }` to keep content flush with the bullet.

**Files changed:**
- `ui/src/components/ChatPanel/ChatPanel.css`

---

### Feature: Global Hermeneutic Mode (GHM) — Phase 8.2.7

Foundational implementation of GHM for Scripture-facing epistemic honesty.

**Documentation:**
- Added `docs/GHM-Spec.md` — five core hermeneutic constraints, canonical authority order, failure conditions
- Added `docs/When-GHM-Activates.md` — activation hierarchy, project templates, domain examples
- Updated `docs/INDEX.md` with GHM section and status entries
- Updated `Roadmap/Roadmap.md` with Phase 8.2.7 section and v1.29 changelog

**Database (Migration 009):**
- `projects.hermeneutic_mode` — `TEXT DEFAULT NULL` (`'ghm'`, `'none'`, or `NULL`)
- `projects.profile` — `TEXT DEFAULT NULL` (e.g., `'pronomian_trajectory'`)
- `messages.ghm_active` — `BOOLEAN DEFAULT FALSE` (audit trail per message)
- Index on `projects.hermeneutic_mode`

**API — Projects endpoints:**
- `GET /api/projects` — now includes `hermeneutic_mode` and `profile` fields
- `POST /api/projects` — accepts `template`, `hermeneutic_mode`, `profile`; template defaults apply GHM for Scripture Study and Theological Research
- `PATCH /api/projects/:id` — supports updating `hermeneutic_mode`, `profile`, `name`, `description`
- `GET /api/projects/templates` — returns 5 project templates with GHM status

**GHM Rules Configuration (`api/config/ghm_rules.yml`):**
- Canonical authority order (Torah → Prophets → Jesus → Apostolic → Post-biblical)
- 5 constraints (GHM-1 through GHM-5), all strict enforcement
- 6 post-biblical frameworks requiring disclosure
- Scripture detection patterns: 57 book names, 8 keywords, verse reference regex, 9 theological markers
- Output requirements for full and soft GHM
- Failure conditions

**GHM Services (`api/services/ghm/`):**
- `config_loader.py` — cached YAML loader with typed accessors
- `detector.py` — conservative Scripture-facing content detector for fallback activation; returns confidence score and suggested action (`none`/`soft_ghm`/`suggest_ghm`)
- `enforcer.py` — post-response constraint checker; detects framework usage (6 types), premature harmonization, comfort-softening; builds disclosure text

**Chat Pipeline Integration:**
- `apply_ghm_pipeline()` orchestrates detection → user override → enforcement → disclosure
- Integrated into both router (multi-agent) and fallback LLM response paths
- `ghm_active` audit field written per message; `ghm` metadata returned in API response

**UI — GHM Badge (`ui/src/components/GHMBadge/`):**
- Badge component with full/soft mode variants (amber accent for full, outlined for soft)
- Hover tooltip showing constraint summary
- Integrated in ProjectsPanel next to project name

**UI — Framework Disclosure (ChatPanel):**
- Post-biblical framework disclosure block rendered after epistemic badge
- Lists detected frameworks with origin attribution
- Displays enforcement warnings (harmonization, softening)

**UI — Project Template Selector (`ui/src/components/ProjectTemplates/`):**
- 5-card grid: General, Scripture Study, Theological Research, Engineering, Writing
- GHM indicator on Scripture Study and Theological Research cards
- Integrated into ProjectsPanel new-project modal (replaced `window.prompt`)
- Integrated into ChatPanel `ProjectRequiredModal`
- Template value sent to `POST /api/projects` for server-side defaults

**Files changed:**
- `docs/GHM-Spec.md` (new)
- `docs/When-GHM-Activates.md` (new)
- `docs/INDEX.md`
- `Roadmap/Roadmap.md`
- `api/migrations/009_ghm_project_fields.sql` (new)
- `api/config/ghm_rules.yml` (new)
- `api/services/ghm/__init__.py` (new)
- `api/services/ghm/config_loader.py` (new)
- `api/services/ghm/detector.py` (new)
- `api/services/ghm/enforcer.py` (new)
- `api/routes/projects_api.py`
- `api/routes/chat_api.py`
- `ui/src/components/GHMBadge/GHMBadge.jsx` (new)
- `ui/src/components/GHMBadge/GHMBadge.css` (new)
- `ui/src/components/ProjectTemplates/ProjectTemplates.jsx` (new)
- `ui/src/components/ProjectTemplates/ProjectTemplates.css` (new)
- `ui/src/components/ChatPanel/ChatPanel.jsx`
- `ui/src/components/LeftPanel/ProjectsPanel.jsx`

---

### Chore: Consolidate context imports, remove unused axios dependency

- Moved `FocusModeContext.jsx` from `contexts/` into `context/` to match all other context files. Removed empty `contexts/` directory.
- Updated imports in `main.jsx`, `App.jsx`, `Settings.jsx`, and `FocusMode.jsx`.
- Removed `axios` from `package.json` — nothing imports it; all API calls use the custom `apiFetch` wrapper.

**Files changed:**
- `ui/src/context/FocusModeContext.jsx` (moved from `ui/src/contexts/`)
- `ui/src/main.jsx`
- `ui/src/App.jsx`
- `ui/src/components/Settings/Settings.jsx`
- `ui/src/components/FocusMode/FocusMode.jsx`
- `ui/package.json`

---

### Fix: Header & Chat UI cleanup

**Changes:**

1. **Chat input overflow** — Added `box-sizing: border-box` and `max-width: 100%` to `.input-area` and `.chat-input` so the input container no longer overruns its parent on the right side.

2. **Focus Mode button relocated** — Moved the ◉ toggle from its orphaned center-header position into the right-side control group (next to status indicator and logout), with `title="Focus Mode"` tooltip.

3. **Mode dropdown removed from header** — The Mode selector is no longer in the header. It now lives in Settings → Advanced → Developer Mode as "Assistant Mode Override", visible only when Developer Mode is enabled. Auto mode routes to the best agent automatically (Phase 6.2 multi-agent routing).

**Files changed:**
- `ui/src/App.jsx`
- `ui/src/components/ChatPanel/ChatPanel.css`
- `ui/src/components/Settings/Settings.jsx`
- `ui/src/styles/dark.css`

---

## 2026-01-26

### Fix: PDF parsing fails with "pypdf not installed"

**Symptom:** Summarizing a PDF in Workspace > Files returned "the PDF parser (pypdf) is not installed on the server."

**Root cause:** `pypdf` was installed in the system Python 3.10 but not in the API's virtual environment (`api/venv/`, Python 3.11). Additionally, the failed parse result was cached in `file_text_cache`, so even after installing the package, the error message persisted.

**Fix:**
- Installed pypdf in the correct venv: `api/venv/bin/pip install pypdf==6.6.1`
- Cleared stale cache: `DELETE FROM file_text_cache WHERE text LIKE '%pypdf%'`

**Files changed:** None (runtime/environment fix)

---

### Fix: Conversation not moving to project after file upload

**Symptom:** User starts chat in Unassigned, uploads a file and creates a new project from the upload modal. The file moves to the new project but the conversation stays in Unassigned, even after page refresh.

**Root cause:** Two issues:
1. `ChatPanel.jsx` `confirmProjectForAttach()` updated the UI project state but never called the API to move the conversation.
2. `ProjectsPanel.jsx` `moveConversation()` called `PATCH /api/conversations/:id` (the rename endpoint) instead of `PATCH /api/conversations/:id/project` (the move endpoint). The `project_id` in the request body was silently ignored by the rename handler.

**Fix:**
- `ChatPanel.jsx`: Added API call to `PATCH /conversations/:id/project` in `confirmProjectForAttach()` when an active conversation exists.
- `ProjectsPanel.jsx`: Changed `moveConversation()` to call `/conversations/:id/project` instead of `/conversations/:id`.

**Files changed:**
- `ui/src/components/ChatPanel/ChatPanel.jsx`
- `ui/src/components/LeftPanel/ProjectsPanel.jsx`

---

### Fix: Chat cannot access project files

**Symptom:** User asks Tamor about files in the current project (e.g., "check the pdf in this project") and gets "I have no access to project files," even though the PDF is parsed and visible in the right panel.

**Root cause:** No context injection existed for project files. The library context injection (Phase 7.3) only searches `library_files`/`library_chunks` (semantic search index), not `project_files` (files uploaded directly to a project). These are separate systems, and project files were never included in the LLM prompt.

**Fix:**
- Added `_get_project_files_context()` function in `chat_api.py` that fetches all project files and their cached text, builds a formatted context block, and injects it into the system prompt.
- Added `project_files_context` field to `RequestContext` in `agents/base.py`.
- Injected context in both the router path and the fallback LLM path.

**Files changed:**
- `api/routes/chat_api.py`
- `api/services/agents/base.py`

---

### Fix: LLM generates fake download links in chat

**Symptom:** When asked to generate a downloadable file, Tamor outputs a fake markdown link (e.g., `Acts_15_Gentiles_Law_Synagogue.md`) that does nothing when clicked. The file was never actually created.

**Root cause:** The system prompt had no guidance on file capabilities. The LLM hallucinated the ability to create downloadable files and generated links pointing to non-existent resources.

**Fix:**
- Added "File capabilities" section to the system prompt in `core/prompt.py` instructing the LLM to never generate fake file links, and to use fenced code blocks instead so the user can copy the content.

**Files changed:**
- `api/core/prompt.py`

**Future upgrade:** Add real file generation from chat — the LLM outputs content, the backend creates an actual file (md, txt, pdf, docx), and a real download link is returned in the response. This would involve a new API endpoint for generated artifacts and a download button in chat message rendering.
