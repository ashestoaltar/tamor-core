# Phase 3.4.1 UI Audit Report

**Date**: 2026-01-23
**Status**: Complete

---

## Component Categorization Table

| Component | Path | Category | Reasoning |
|-----------|------|----------|-----------|
| **App.jsx** | `ui/src/App.jsx` | Essential | Core application shell with three-panel layout, mobile view switching, header. Required for all users. |
| **ChatPanel.jsx** | `ui/src/components/ChatPanel/ChatPanel.jsx` | Essential | Core conversational interface. Primary interaction point for all users including voice-first users. |
| **TaskPill.jsx** | `ui/src/components/ChatPanel/TaskPill.jsx` | Essential | Displays tasks/memories inline in chat. Part of core chat experience. |
| **LeftPanel.jsx** | `ui/src/components/LeftPanel/LeftPanel.jsx` | Essential | Main navigation with project/conversation switching. Tabs for Conversations vs Tasks. |
| **ProjectsPanel.jsx** | `ui/src/components/LeftPanel/ProjectsPanel.jsx` | Essential | Project list and management. Core organizational feature. |
| **ConversationList.jsx** | `ui/src/components/LeftPanel/ConversationList.jsx` | Essential | Conversation history browser. Core navigation feature. |
| **LoginPanel.jsx** | `ui/src/components/LoginPanel.jsx` | Essential | Authentication UI. Required for all users. |
| **RightPanel.jsx** | `ui/src/components/RightPanel/RightPanel.jsx` | Essential | Right sidebar container with tab navigation (11 tabs currently). |
| **WorkspaceTab.jsx** | `ui/src/components/RightPanel/tabs/WorkspaceTab.jsx` | Essential | Project notes + pipeline panel. Core project management. |
| **FilesTab.jsx** | `ui/src/components/RightPanel/tabs/FilesTab.jsx` | Essential | File management with search, summaries, actions. Core research feature. |
| **MemoryTab.jsx** | `ui/src/components/RightPanel/tabs/MemoryTab.jsx` | Essential | Memory management with settings, filtering, creation. Governed memory interface. |
| **SearchTab.jsx** | `ui/src/components/RightPanel/tabs/SearchTab.jsx` | Power User | Semantic search wrapper. Useful for research but not core chat flow. |
| **InsightsTab.jsx** | `ui/src/components/RightPanel/tabs/InsightsTab.jsx` | Power User | Auto-generated insights (themes, contradictions, assumptions). Research feature. |
| **ReasoningTab.jsx** | `ui/src/components/RightPanel/tabs/ReasoningTab.jsx` | Power User | Cross-file reasoning analysis. Advanced research feature. |
| **KnowledgeTab.jsx** | `ui/src/components/RightPanel/tabs/KnowledgeTab.jsx` | Power User | Knowledge symbol search (entities, citations). Advanced feature. |
| **MediaTab.jsx** | `ui/src/components/RightPanel/tabs/MediaTab.jsx` | Power User | Video transcription via YouTube URL. Niche but useful. |
| **ViewerTab.jsx** | `ui/src/components/RightPanel/tabs/ViewerTab.jsx` | Power User | File preview iframe. Useful for document review. |
| **PluginsTab.jsx** | `ui/src/components/RightPanel/tabs/PluginsTab.jsx` | Power User | Plugin management (importers, exporters, references). Advanced feature. |
| **PlaylistsTab.jsx** | `ui/src/components/RightPanel/tabs/PlaylistsTab.jsx` | Power User | Stremio addon integration for movie playlist management. Not currently voice-controllable; flagged as candidate for voice integration in Phase 3.4.3. |
| **FileList.jsx** | `ui/src/components/RightPanel/components/FileList.jsx` | Power User | File list with actions (summarize, structure, rewrite). Used by FilesTab. |
| **PipelinePanel.jsx** | `ui/src/components/RightPanel/components/PipelinePanel.jsx` | Power User | Workflow pipeline management. Advanced project feature. |
| **SemanticSearchPanel.jsx** | `ui/src/components/RightPanel/components/SemanticSearchPanel.jsx` | Power User | Semantic search UI with chunks/files views. Used by SearchTab. |
| **ProjectSummaryPanel.jsx** | `ui/src/components/RightPanel/components/ProjectSummaryPanel.jsx` | Power User | Project summary generation. Used by WorkspaceTab. |
| **StructurePanel.jsx** | `ui/src/components/RightPanel/components/StructurePanel.jsx` | Developer Only | File structure display marked as "(beta)". Raw JSON output. |
| **TasksPanel.jsx** | `ui/src/components/LeftPanel/TasksPanel.jsx` | Developer Only | Task filtering/management with inline styles, technical filters (priority, status). Developer debugging feel. Feature is useful, implementation is developer-focused. Flag for Phase 3.5 redesign as user-friendly task management UI. TaskPill.jsx remains Essential for inline task display in chat. |
| **MemoryList.jsx** | `ui/src/components/LeftPanel/MemoryList.jsx` | Developer Only | Older memory browser with category filters. Superseded by MemoryTab.jsx. |
| **MemoryCard.jsx** | `ui/src/components/LeftPanel/MemoryCard.jsx` | Developer Only | Memory display card. Only used by MemoryList.jsx (deprecated). |

---

## Dead/Unused Components

| Component | Issue | Recommendation |
|-----------|-------|----------------|
| **MemoryList.jsx** | Superseded by MemoryTab.jsx which has fuller functionality (settings, governed memory integration) | Remove or archive |
| **MemoryCard.jsx** | Only used by MemoryList.jsx | Remove with MemoryList |
| **StructurePanel.jsx** | Displays raw JSON, marked "(beta)", minimal UI | Hide from non-developer users or complete implementation |

---

## CSS Consolidation Opportunities

| Issue | Files Involved | Recommendation |
|-------|---------------|----------------|
| **Duplicate memory styles** | `memory.css` (310 lines) + `.rp-memory-*` in `RightPanel.css` (~150 lines) | Consolidate into single memory module in RightPanel.css since MemoryList is deprecated |
| **Tag styles duplication** | `.tag-*` in `memory.css`, `.rp-tag-*` in `RightPanel.css` | Unify tag classes into shared design tokens |
| **Button style variations** | `.rp-button`, `.rp-btn`, `.rp-button-pill`, `.rp-button-compact`, `.rp-button-secondary` in RightPanel.css | Reduce to 3 variants: primary, secondary, ghost |
| **Mobile touch targets** | Repeated `@media (max-width: 899px)` and `@media (max-width: 599px)` blocks in 5 CSS files | Extract shared mobile mixins or CSS custom properties |

---

## Duplicate Functionality

| Feature | Implementations | Recommendation |
|---------|-----------------|----------------|
| **Memory browsing** | MemoryList.jsx (LeftPanel, older) vs MemoryTab.jsx (RightPanel, current) | Keep MemoryTab, remove MemoryList |
| **Semantic search** | SemanticSearchPanel.jsx component + SearchTab.jsx wrapper | Fine - good separation of concerns |
| **File actions** | FileList.jsx actions (rewrite, spec, params) duplicates some FilesTab controls | Consider merging or clarifying scope |

---

## Tab Proliferation (RightPanel)

Current tabs: **Workspace, Files, Search, Knowledge, Insights, Reasoning, Media, Viewer, Memory, Plugins, Playlists** (11 tabs)

| Recommendation | Tabs |
|----------------|------|
| **Essential (always visible)** | Workspace, Files, Memory |
| **Research (collapsible group)** | Search, Insights, Reasoning, Knowledge |
| **Tools (collapsible group)** | Media, Plugins, Viewer, Playlists |

---

## Mobile/Voice Considerations

| Observation | Impact |
|-------------|--------|
| Good: All CSS files have `@media (max-width: 899px)` touch target fixes (44px minimum) | Mobile-ready |
| Good: App.jsx has mobile view switching (view-left, view-chat, view-right) | Single-panel mode works |
| Issue: 11 tabs in RightPanel would be overwhelming on mobile | Need tab consolidation |
| Issue: No visible voice input integration yet | Phase 3.4.3 scope |
| Issue: TasksPanel inline styles and developer-oriented filters | Not suitable for non-technical users |

---

## Summary Statistics

- **Total Components Audited**: 27
- **Essential**: 11 (41%)
- **Power User**: 12 (44%)
- **Developer Only**: 4 (15%)
- **Recommended for Removal**: 3 components (MemoryList, MemoryCard, StructurePanel)
- **CSS Files**: 6 (dark.css, ChatPanel.css, LeftPanel.css, RightPanel.css, memory.css, MemoryList.css)
- **CSS Lines Total**: ~2,800 lines
- **Consolidation Savings Estimate**: ~300-400 lines

---

## Deferred Work

| Item | Target Phase | Description |
|------|--------------|-------------|
| TasksPanel redesign | Phase 3.5 | Redesign task management UI for non-technical users. Current implementation has developer-oriented filters and inline styles. |
| PlaylistsTab voice control | Phase 3.4.3+ | Enable voice commands like "Add Home Alone to Christmas playlist" once voice input is implemented. |
| StructurePanel completion | TBD | Either complete with proper UI or remove entirely. Raw JSON display not useful. |

---

## Next Steps (Refined)

1. **Create DevModeContext** — Infrastructure for toggling developer UI visibility
2. **Remove dead components** — MemoryList.jsx, MemoryCard.jsx, consolidate memory.css
3. **Wrap TasksPanel in dev mode** — Keep TaskPill visible for inline task display
4. **Proceed to Phase 3.4.2** — Mobile layout with tab grouping, drawer navigation
