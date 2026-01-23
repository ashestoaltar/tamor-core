// src/components/RightPanel/RightPanel.jsx
import React, { useEffect, useState } from "react";
import "./RightPanel.css";
import { apiFetch } from "../../api/client";

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

function RightPanel({
  currentProjectId,
  activeConversationId,
  activeMode,
  onConversationsChanged,
}) {
  const [activeTab, setActiveTab] = useState("workspace");

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
  };

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

      <div className="rp-tabs">
        <button
          className={
            activeTab === "workspace"
              ? "rp-tab rp-tab-active"
              : "rp-tab"
          }
          type="button"
          onClick={() => setActiveTab("workspace")}
        >
          Workspace
        </button>
        <button
          className={
            activeTab === "files" ? "rp-tab rp-tab-active" : "rp-tab"
          }
          type="button"
          onClick={() => setActiveTab("files")}
        >
          Files
        </button>
        <button
          className={
            activeTab === "search" ? "rp-tab rp-tab-active" : "rp-tab"
          }
          type="button"
          onClick={() => setActiveTab("search")}
        >
          Search
        </button>
        <button
          className={
            activeTab === "viewer" ? "rp-tab rp-tab-active" : "rp-tab"
          }
          type="button"
          onClick={() => setActiveTab("viewer")}
        >
          Viewer
        </button>
        <button
          className={
            activeTab === "knowledge"
              ? "rp-tab rp-tab-active"
              : "rp-tab"
          }
          type="button"
          onClick={() => setActiveTab("knowledge")}
        >
          Knowledge
        </button>
        <button
          className={
            activeTab === "insights"
              ? "rp-tab rp-tab-active"
              : "rp-tab"
          }
          type="button"
          onClick={() => setActiveTab("insights")}
        >
          Insights
        </button>
        <button
          className={
            activeTab === "reasoning"
              ? "rp-tab rp-tab-active"
              : "rp-tab"
          }
          type="button"
          onClick={() => setActiveTab("reasoning")}
        >
          Reasoning
        </button>
        <button
          className={
            activeTab === "playlists"
              ? "rp-tab rp-tab-active"
              : "rp-tab"
          }
          type="button"
          onClick={() => setActiveTab("playlists")}
        >
          Playlists
        </button>
        <button
          className={
            activeTab === "media"
              ? "rp-tab rp-tab-active"
              : "rp-tab"
          }
          type="button"
          onClick={() => setActiveTab("media")}
        >
          Media
        </button>
        <button
          className={
            activeTab === "memory"
              ? "rp-tab rp-tab-active"
              : "rp-tab"
          }
          type="button"
          onClick={() => setActiveTab("memory")}
        >
          Memory
        </button>
        <button
          className={
            activeTab === "plugins"
              ? "rp-tab rp-tab-active"
              : "rp-tab"
          }
          type="button"
          onClick={() => setActiveTab("plugins")}
        >
          Plugins
        </button>
      </div>

      <div className="rp-body">
        {!currentProjectId && activeTab !== "playlists" && activeTab !== "memory" && (
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
          />
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
      </div>
    </div>
  );
}

export default RightPanel;

