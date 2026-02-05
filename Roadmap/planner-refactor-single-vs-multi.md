# Planner Workflow Refactor: Single-Piece vs. Multi-Piece

## Status: DRAFT — For future implementation after current pipeline stabilizes

## Problem

The current Planner decomposes every writing request into 5 discrete steps (research → research → draft → review → revise), each requiring `/next-task` to advance. This works mechanically but is tedious for single articles. The friction is wrong — it treats "write me an article" the same as "plan my 8-part article series."

## Core Insight

The Planner should orchestrate **between pieces**, not **within a piece**. Research, drafting, and revision within a single article should happen fluidly in one turn (as the Writer already does). The Planner's value is coordinating a body of work across sessions.

## Two Workflows

### 1. Single-Piece Workflow (No Planner needed)

**Trigger:** "Write me an article/teaching/blog post about X"

**Flow:**
1. Router detects `write` intent → routes to Writer
2. Writer optionally asks 1-2 clarifying questions (audience, length, angle)
3. Researcher runs silently (library search for relevant chunks)
4. Writer produces the piece with inline citations
5. User reads, may ask for revisions in conversation
6. Done — no pipeline, no `/next-task`

**This already works.** The researcher→writer chain handles it. No changes needed.

### 2. Multi-Piece Workflow (Planner orchestrates)

**Trigger:** "I want to write an article series about X" / "Plan my sermon series" / "I have 8 articles to write for America at 250"

**Flow:**
1. Router detects `plan` intent → routes to Planner
2. Planner asks clarifying questions about the **series**: how many pieces, themes, audience, shared research needs, publication order
3. Planner creates pipeline_tasks — one per **piece**, not one per sub-step:
   ```
   1. [ARTICLE] "Covenant and Constitution" — 1,500 words, founding documents through biblical lens
   2. [ARTICLE] "Sabbath, Liberty, and Rest" — 1,500 words, Sabbath rest and founders' concept of liberty
   3. [ARTICLE] "One Law for All" — 1,500 words, sojourner laws and American immigration ideals
   ... etc.
   ```
4. Optional: Planner identifies **shared research** that feeds multiple pieces (e.g., "Research founding-era religious influences" feeds articles 1, 2, and 5). These can be separate prerequisite tasks.
5. User types `/next-task` (or "start article 1") → Router sends the **article description** to the Writer as a single-piece request
6. Writer produces the full article (using researcher→writer chain as usual)
7. User reviews, revises conversationally
8. When satisfied, `/next-task` moves to article 2
9. Context from completed articles available to downstream pieces via output_summary

**Key difference:** `/next-task` advances between **articles**, not between research/draft/revise steps within one article.

## What Changes

### Router
- No change for single-piece detection (already works)
- Plan intent should trigger on **series/multi-piece** language, not single articles
- Heuristic: "article series," "sermon series," "8 articles," "plan my project," multiple topics listed → Planner
- Single topic, single piece → Writer directly

### Planner
- Stops decomposing single articles into research/draft/revise sub-tasks
- Creates one pipeline_task per **piece** in the series
- Each task includes: title, description, word count target, audience, key themes, dependencies (which prior articles' research it can draw from)
- Can create optional shared research tasks as prerequisites
- Plan output looks like a table of contents, not a process flowchart

### Pipeline Tasks Schema
Current:
```
task_type: research | draft | review | revise
```

Refactored:
```
task_type: research | article | teaching | sermon | deep_dive
template: article | torah_portion | deep_dive | sermon  (from writer_templates.yml)
word_target: integer
dependencies: [list of task_ids whose output_summary to inject]
```

### Task Execution (`/next-task`)
- Finds next pending task
- If `task_type` is a writing type (article, teaching, sermon, deep_dive):
  - Gathers output_summaries from dependency tasks
  - Sends task_description + dependency context to Writer as a single-piece request
  - Writer runs researcher→writer chain internally
  - Stores output in output_summary
  - Marks complete
- If `task_type` is `research`:
  - Sends to Researcher as usual
  - Stores findings
  - Marks complete (these are shared research prerequisites)

### Review/Revise
- Happens **conversationally** after each piece, not as separate pipeline steps
- User reads the draft in the conversation
- Says "tighten the opening" or "add more on Adams" → Writer revises
- When user is satisfied → `/next-task` advances to next piece
- No separate review/revise pipeline_tasks needed

## What Stays the Same

- Writer agent, persona, voice calibration, templates — all unchanged
- Researcher agent and library integration — unchanged
- Planner routing and continuation detection — unchanged
- `/clear-plan` and pipeline UI — unchanged
- Single-piece workflow — unchanged (it already works correctly)

## Migration Path

1. **Phase 1 (now):** Current 5-step pipeline works. Ship it, use it, learn from it.
2. **Phase 2 (this refactor):** Planner creates per-piece tasks. `/next-task` fires single-piece workflow per task. Review is conversational.
3. **Phase 3 (future):** Auto-detect when shared research would benefit multiple pieces. Planner suggests "I'll research founding-era religious influences first since articles 1, 2, and 5 all need it."

## Example: America at 250 Series

**User:** "I want to plan my America at 250 article series. 8 articles, 1,500 words each, general audience."

**Planner response:**
```
Here's your America at 250 series plan:

1. [ARTICLE] "Covenant and Constitution" — Biblical covenant themes in founding documents
2. [ARTICLE] "Sabbath, Liberty, and Rest" — Founders' liberty and biblical Sabbath rest
3. [ARTICLE] "One Law for All" — Sojourner laws and the American ideal of equal justice
4. [ARTICLE] "Providence and the Pursuit" — Divine providence in founders' worldview
5. [ARTICLE] "Jubilee Economics" — Sabbatical/Jubilee cycles and American economic ideals
6. [ARTICLE] "The Prophet's Voice" — Prophetic tradition and American reform movements
7. [ARTICLE] "Exile and Homecoming" — Biblical exile themes and the immigrant experience
8. [ARTICLE] "City on a Hill" — Eschatological vision and American self-understanding

All articles: ~1,500 words, general audience, grounded in library sources.
Shared research: Founding-era religious influences (feeds articles 1-4).

Ready to start with shared research, or jump to Article 1?
```

**User:** `/next-task`
→ Article 1 writes as a single piece (researcher→writer chain, library sources, ~1,500 words)
→ User reviews, revises conversationally
→ `/next-task` → Article 2
→ Repeat

## Notes

- The current 5-step model isn't wasted — it validated that pipeline_tasks, execution routing, context threading, and review all work mechanically. That infrastructure carries forward.
- Per-piece tasks are simpler to track and more intuitive for the user. "I'm on article 3 of 8" is clearer than "I'm on step 14 of 40."
- The Planner's real value is **series-level decisions**: ordering, shared research, thematic arcs, cross-referencing. Not sub-task decomposition within a single piece.
