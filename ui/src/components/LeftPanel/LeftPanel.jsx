// ui/src/components/LeftPanel/LeftPanel.jsx
import "./LeftPanel.css";
import { useState } from "react";
import ProjectsPanel from "./ProjectsPanel";
import TasksPanel from "./TasksPanel";

export default function LeftPanel({
  activeMode,
  setActiveMode,
  activeConversationId,
  onSelectConversation,
  conversationRefreshToken,
  onNewConversation,
  onDeleteConversation,
  currentProjectId,
  setCurrentProjectId,
}) {
  const modes = ["Scholar", "Forge", "Path", "Anchor", "Creative", "System"];

  // Conversations | Tasks tab
  const [activeTab, setActiveTab] = useState("conversations"); // "conversations" | "tasks"

  // --- Search ---
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState({
    conversations: [],
    projects: [],
    memories: [],
  });
  const [searchLoading, setSearchLoading] = useState(false);

  const resetResults = () => {
    setSearchResults({
      conversations: [],
      projects: [],
      memories: [],
    });
  };

  const runSearch = async (q) => {
    const trimmed = q.trim();
    if (!trimmed) {
      resetResults();
      setSearchLoading(false);
      return;
    }
    setSearchLoading(true);
    try {
      // NOTE: LeftPanel originally used apiFetch; if you prefer that, re-add the import:
      // import { apiFetch } from "../../api/client";
      const res = await fetch(`/api/search?q=${encodeURIComponent(trimmed)}`, {
        credentials: "include",
      });
      const data = await res.json();

      setSearchResults({
        conversations: data.conversations || [],
        projects: data.projects || [],
        memories: data.memories || [],
      });
    } catch (err) {
      console.error("Search failed:", err);
      resetResults();
    } finally {
      setSearchLoading(false);
    }
  };

  const handleSearchChange = (e) => {
    const v = e.target.value;
    setSearchTerm(v);
    runSearch(v);
  };

  const clearSearch = () => {
    setSearchTerm("");
    resetResults();
    setSearchLoading(false);
  };

  const inSearchMode = searchTerm.trim().length > 0;

  const hasAnyResults =
    (searchResults.conversations?.length || 0) +
      (searchResults.projects?.length || 0) +
      (searchResults.memories?.length || 0) >
    0;

  return (
    <div className="left-panel">
      <div className="identity">
        <h1 className="logo">TAMOR</h1>
        <div className="subtitle">Wholeness • Light • Insight</div>
      </div>

      {/* Search bar */}
      <div className="left-search-bar">
        <input
          className="left-search-input"
          type="text"
          placeholder="Search workspace…"
          value={searchTerm}
          onChange={handleSearchChange}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.preventDefault();
              clearSearch();
            }
          }}
        />
        {searchTerm && (
          <button className="left-search-clear" onClick={clearSearch}>
            ×
          </button>
        )}
      </div>

      {/* Conversations / Tasks tabs (hidden during search) */}
      {!inSearchMode && (
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button
            type="button"
            className={activeTab === "conversations" ? "left-tab active" : "left-tab"}
            onClick={() => setActiveTab("conversations")}
          >
            Conversations
          </button>
          <button
            type="button"
            className={activeTab === "tasks" ? "left-tab active" : "left-tab"}
            onClick={() => setActiveTab("tasks")}
          >
            Tasks
          </button>
        </div>
      )}

      {/* Middle section */}
      <div className="section memory-section">
        {inSearchMode ? (
          <div className="search-results">
            {searchLoading && <div className="search-loading">Searching…</div>}

            {!searchLoading && !hasAnyResults && <div className="search-empty">No results.</div>}

            {/* Conversations */}
            {searchResults.conversations?.length > 0 && (
              <div className="search-group">
                <div className="search-group-title">Conversations</div>
                {searchResults.conversations.map((c) => (
                  <div
                    key={c.id}
                    className="search-result-item"
                    onClick={() => {
                      onSelectConversation(c.id);
                      setCurrentProjectId(c.project_id || null);
                      clearSearch();
                    }}
                  >
                    <div className="search-result-title">{c.title || `Conversation ${c.id}`}</div>
                    <div className="search-result-meta">
                      {new Date(c.updated_at || c.created_at).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Projects */}
            {searchResults.projects?.length > 0 && (
              <div className="search-group">
                <div className="search-group-title">Projects</div>
                {searchResults.projects.map((p) => (
                  <div
                    key={p.id}
                    className="search-result-item"
                    onClick={() => {
                      setCurrentProjectId(p.id);
                      clearSearch();
                    }}
                  >
                    <div className="search-result-title">{p.name || `Project ${p.id}`}</div>
                    {p.description && <div className="search-result-meta">{p.description}</div>}
                  </div>
                ))}
              </div>
            )}

            {/* Memories (global knowledge store) */}
            {searchResults.memories?.length > 0 && (
              <div className="search-group">
                <div className="search-group-title">Memories</div>
                {searchResults.memories.map((m) => (
                  <div key={m.id} className="search-result-item">
                    <div className="search-result-title">
                      {m.content.length > 80 ? m.content.slice(0, 80) + "…" : m.content}
                    </div>
                    <div className="search-result-meta">
                      Score: {m.score.toFixed(2)} • #{m.id}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : activeTab === "tasks" ? (
          <TasksPanel
            onOpenConversation={(cid) => {
              onSelectConversation(cid);
            }}
          />
        ) : (
          <ProjectsPanel
            activeConversationId={activeConversationId}
            onSelectConversation={onSelectConversation}
            refreshToken={conversationRefreshToken}
            onNewConversation={onNewConversation}
            onDeleteConversation={onDeleteConversation}
            currentProjectId={currentProjectId}
            setCurrentProjectId={setCurrentProjectId}
          />
        )}
      </div>

      {/* Modes */}
      <div className="section mode-section">
        <h2>Modes</h2>
        <ul className="mode-list">
          {modes.map((mode) => (
            <li
              key={mode}
              className={mode === activeMode ? "mode active" : "mode"}
              onClick={() => setActiveMode(mode)}
            >
              {mode}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

