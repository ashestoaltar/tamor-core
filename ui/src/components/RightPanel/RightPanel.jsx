// src/components/RightPanel/RightPanel.jsx
import React, { useEffect, useState } from "react";
import "./RightPanel.css";
import { apiFetch } from "../../api/client";
import { useBreakpoint } from "../../hooks/useBreakpoint";
import { useReaderContext } from "../../context/ReaderContext";
import { ReaderView } from "../Reader";

import WorkspaceTab from "./tabs/WorkspaceTab.jsx";
import FilesTab from "./tabs/FilesTab.jsx";
import SearchTab from "./tabs/SearchTab.jsx";
import KnowledgeTab from "./tabs/KnowledgeTab.jsx";
import InsightsTab from "./tabs/InsightsTab.jsx";
import ReasoningTab from "./tabs/ReasoningTab.jsx";
import PlaylistsTab from "./tabs/PlaylistsTab.jsx";
import ViewerTab from "./tabs/ViewerTab.jsx";
import MediaTab from "./tabs/MediaTab.jsx";
import MemoryTab from "./tabs/MemoryTab.jsx";
import PluginsTab from "./tabs/PluginsTab.jsx";
import ReferencesTab from "./tabs/ReferencesTab.jsx";
import LibraryTab from "./tabs/LibraryTab.jsx";

// Tab grouping configuration
const TAB_GROUPS = {
  essential: {
    id: "essential",
    tabs: ["workspace", "files", "library", "memory", "references"],
  },
  research: {
    id: "research",
    label: "Research",
    tabs: ["search", "insights", "reasoning", "knowledge"],
  },
  tools: {
    id: "tools",
    label: "Tools",
    tabs: ["media", "viewer", "plugins", "playlists"],
  },
};

// Tab labels for display
const TAB_LABELS = {
  workspace: "Workspace",
  files: "Files",
  library: "Library",
  memory: "Memory",
  references: "Scripture",
  search: "Search",
  insights: "Insights",
  reasoning: "Reasoning",
  knowledge: "Knowledge",
  media: "Media",
  viewer: "Viewer",
  plugins: "Plugins",
  playlists: "Playlists",
};

// Helper to find which group a tab belongs to
function getGroupForTab(tabId) {
  if (TAB_GROUPS.research.tabs.includes(tabId)) return "research";
  if (TAB_GROUPS.tools.tabs.includes(tabId)) return "tools";
  return null;
}

// Storage keys for remembering last tab in each group
const STORAGE_KEYS = {
  research: "tamor_rp_last_research_tab",
  tools: "tamor_rp_last_tools_tab",
};

function RightPanel({
  currentProjectId,
  activeConversationId,
  activeMode,
  onConversationsChanged,
}) {
  const { isMobile, isTablet, isDesktop } = useBreakpoint();
  const isMobileOrTablet = isMobile || isTablet;

  // Reader mode
  const { isReaderOpen, readerContent, closeReader } = useReaderContext();

  const [activeTab, setActiveTab] = useState("workspace");
  const [expandedGroup, setExpandedGroup] = useState(null); // "research" | "tools" | null

  // Project list for header
  const [projects, setProjects] = useState([]);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [projectsError, setProjectsError] = useState("");

  // cross-tab state: what Viewer should show
  const [viewerSelectedFileId, setViewerSelectedFileId] = useState(null);
  const [viewerSelectedPage, setViewerSelectedPage] = useState(null);

  useEffect(() => {
    const fetchProjects = async () => {
      setProjectsLoading(true);
      setProjectsError("");
      try {
        const data = await apiFetch("/projects");
        setProjects(data.projects || []);
      } catch (err) {
        console.error("Failed to fetch projects", err);
        setProjectsError("Error loading projects");
      } finally {
        setProjectsLoading(false);
      }
    };

    fetchProjects();
  }, []);

  const currentProject =
    projects.find((p) => p.id === currentProjectId) || null;

  const handleOpenInViewerFromSearch = (fileId, page) => {
    if (!fileId) return;
    setViewerSelectedFileId(fileId);
    setViewerSelectedPage(
      typeof page === "number" && page > 0 ? page : null
    );
    setActiveTab("viewer");
    // Expand tools group if on mobile since viewer is in tools
    if (isMobileOrTablet) {
      setExpandedGroup("tools");
    }
  };

  // Handle tab selection with group memory
  const handleTabSelect = (tabId) => {
    setActiveTab(tabId);

    // Remember last-used tab in each group
    const group = getGroupForTab(tabId);
    if (group && STORAGE_KEYS[group]) {
      try {
        localStorage.setItem(STORAGE_KEYS[group], tabId);
      } catch {
        // ignore storage errors
      }
    }
  };

  // Handle group toggle (mobile/tablet)
  const handleGroupToggle = (groupId) => {
    if (expandedGroup === groupId) {
      // Collapse the group
      setExpandedGroup(null);
    } else {
      // Expand the group and select last-used tab (or first tab)
      setExpandedGroup(groupId);

      const group = TAB_GROUPS[groupId];
      if (group) {
        let lastTab = null;
        try {
          lastTab = localStorage.getItem(STORAGE_KEYS[groupId]);
        } catch {
          // ignore
        }

        // If last tab is valid for this group, use it; otherwise use first tab
        const targetTab = lastTab && group.tabs.includes(lastTab)
          ? lastTab
          : group.tabs[0];
        setActiveTab(targetTab);
      }
    }
  };

  // Check if a group contains the active tab
  const groupContainsActiveTab = (groupId) => {
    const group = TAB_GROUPS[groupId];
    return group && group.tabs.includes(activeTab);
  };

  // Render a single tab button
  const renderTab = (tabId, isSubTab = false) => (
    <button
      key={tabId}
      className={`rp-tab ${activeTab === tabId ? "rp-tab-active" : ""} ${isSubTab ? "rp-tab-sub" : ""}`}
      type="button"
      onClick={() => handleTabSelect(tabId)}
    >
      {TAB_LABELS[tabId]}
    </button>
  );

  // Render a group toggle button (mobile/tablet)
  const renderGroupToggle = (groupId) => {
    const group = TAB_GROUPS[groupId];
    const isExpanded = expandedGroup === groupId;
    const isActive = groupContainsActiveTab(groupId);

    return (
      <button
        key={groupId}
        className={`rp-tab rp-tab-group ${isExpanded ? "rp-tab-group-expanded" : ""} ${isActive ? "rp-tab-group-active" : ""}`}
        type="button"
        onClick={() => handleGroupToggle(groupId)}
        aria-expanded={isExpanded}
      >
        {group.label}
        <svg
          className="rp-tab-group-chevron"
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
    );
  };

  // When reader is open, render reader mode
  if (isReaderOpen && readerContent.contentType && readerContent.contentId) {
    return (
      <div className="right-panel right-panel-reader-mode">
        <ReaderView
          contentType={readerContent.contentType}
          contentId={readerContent.contentId}
          initialMode={readerContent.mode}
          onClose={closeReader}
        />
      </div>
    );
  }

  return (
    <div className="right-panel">
      <div className="rp-header">
        <div className="rp-header-main">
          <div className="rp-header-title">Workspace</div>
          <div className="rp-header-subtitle">
            {projectsLoading && (
              <span className="rp-tag rp-tag-muted">
                Loading projects…
              </span>
            )}
            {!projectsLoading && currentProject && (
              <span className="rp-header-project-name">
                {currentProject.name}
              </span>
            )}
            {!projectsLoading && !currentProject && (
              <span className="rp-header-project-name rp-muted">
                No project selected
              </span>
            )}
            {projectsError && (
              <span
                className="rp-header-project-name rp-error"
                style={{ marginLeft: 8 }}
              >
                {projectsError}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Desktop: show all tabs */}
      {isDesktop && (
        <div className="rp-tabs">
          {renderTab("workspace")}
          {renderTab("files")}
          {renderTab("library")}
          {renderTab("references")}
          {renderTab("search")}
          {renderTab("viewer")}
          {renderTab("knowledge")}
          {renderTab("insights")}
          {renderTab("reasoning")}
          {renderTab("playlists")}
          {renderTab("media")}
          {renderTab("memory")}
          {renderTab("plugins")}
        </div>
      )}

      {/* Mobile/Tablet: grouped tabs */}
      {isMobileOrTablet && (
        <div className="rp-tabs rp-tabs-grouped">
          {/* Essential tabs (always visible) */}
          <div className="rp-tabs-row rp-tabs-essential">
            {renderTab("workspace")}
            {renderTab("files")}
            {renderTab("library")}
            {renderTab("memory")}
            {renderTab("references")}
            {renderGroupToggle("research")}
            {renderGroupToggle("tools")}
          </div>

          {/* Research sub-tabs (expandable) */}
          {expandedGroup === "research" && (
            <div className="rp-tabs-row rp-tabs-subtabs">
              {TAB_GROUPS.research.tabs.map((tabId) => renderTab(tabId, true))}
            </div>
          )}

          {/* Tools sub-tabs (expandable) */}
          {expandedGroup === "tools" && (
            <div className="rp-tabs-row rp-tabs-subtabs">
              {TAB_GROUPS.tools.tabs.map((tabId) => renderTab(tabId, true))}
            </div>
          )}
        </div>
      )}

      <div className="rp-body">
        {!currentProjectId && activeTab !== "playlists" && activeTab !== "memory" && activeTab !== "references" && activeTab !== "library" && (
          <div className="rp-empty-state">
            <div className="rp-empty-title">
              Select or create a project
            </div>
            <div className="rp-empty-text">
              The right panel becomes your project workspace once a
              project is selected.
            </div>
          </div>
        )}

        {currentProjectId && activeTab === "workspace" && (
          <WorkspaceTab currentProjectId={currentProjectId} />
        )}

        {currentProjectId && activeTab === "files" && (
          <FilesTab
            currentProjectId={currentProjectId}
            activeConversationId={activeConversationId}
            activeMode={activeMode}
            onConversationsChanged={onConversationsChanged}
            onOpenLibrary={() => handleTabSelect("library")}
          />
        )}

        {activeTab === "library" && (
          <LibraryTab projectId={currentProjectId} />
        )}

        {currentProjectId && activeTab === "search" && (
          <SearchTab
            currentProjectId={currentProjectId}
            activeConversationId={activeConversationId}
            activeMode={activeMode}
            onConversationsChanged={onConversationsChanged}
            onOpenInViewer={handleOpenInViewerFromSearch}
          />
        )}

        {currentProjectId && activeTab === "viewer" && (
          <ViewerTab
            currentProjectId={currentProjectId}
            viewerSelectedFileId={viewerSelectedFileId}
            viewerSelectedPage={viewerSelectedPage}
          />
        )}

        {currentProjectId && activeTab === "knowledge" && (
          <KnowledgeTab
            currentProjectId={currentProjectId}
            activeConversationId={activeConversationId}
            activeMode={activeMode}
            onConversationsChanged={onConversationsChanged}
          />
        )}

        {currentProjectId && activeTab === "insights" && (
          <InsightsTab currentProjectId={currentProjectId} />
        )}

        {currentProjectId && activeTab === "reasoning" && (
          <ReasoningTab currentProjectId={currentProjectId} />
        )}

        {activeTab === "playlists" && <PlaylistsTab />}

        {currentProjectId && activeTab === "media" && (
          <MediaTab currentProjectId={currentProjectId} />
        )}

        {activeTab === "memory" && <MemoryTab />}

        {currentProjectId && activeTab === "plugins" && (
          <PluginsTab currentProjectId={currentProjectId} />
        )}

        {activeTab === "references" && <ReferencesTab />}
      </div>
    </div>
  );
}

export default RightPanel;

