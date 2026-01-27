# Tamor Changelog

Running log of issues, root causes, and fixes.

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
