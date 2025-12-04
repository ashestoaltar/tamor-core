// src/components/LeftPanel/ProjectsPanel.jsx
import { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";

function formatDateLabel(value) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function ProjectsPanel({
  activeConversationId,
  onSelectConversation,
  onDeleteConversation,
  refreshToken,
  currentProjectId,
  setCurrentProjectId,
  onNewConversation,
}) {
  const [projects, setProjects] = useState([]);
  const [convos, setConvos] = useState([]);
  const [loading, setLoading] = useState(false);

  const [expandedProjects, setExpandedProjects] = useState({});
  const [unassignedExpanded, setUnassignedExpanded] = useState(true);

  const [editingConvId, setEditingConvId] = useState(null);
  const [editingConvTitle, setEditingConvTitle] = useState("");
  const [savingConvId, setSavingConvId] = useState(null);

  const [editingProjectId, setEditingProjectId] = useState(null);
  const [editingProjectName, setEditingProjectName] = useState("");
  const [savingProject, setSavingProject] = useState(false);
  const [deletingProjectId, setDeletingProjectId] = useState(null);

  async function loadAll() {
    setLoading(true);
    try {
      const [projData, convData] = await Promise.all([
        apiFetch("/projects"),
        apiFetch("/conversations"),
      ]);

      const projList = projData.projects || [];
      const convList = convData.conversations || convData || [];

      console.log("DEBUG /projects ->", projList);
      console.log("DEBUG /conversations ->", convList);

      setProjects(projList);
      setConvos(convList);

      // Expand all projects by default the first time
      if (Object.keys(expandedProjects).length === 0) {
        const initial = {};
        for (const p of projList) {
          initial[p.id] = true;
        }
        setExpandedProjects(initial);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken]);

  // ---- Project actions ----

  const handleNewProject = async () => {
    const name = window.prompt("Project name?");
    if (!name) return;

    try {
      setSavingProject(true);
      const data = await apiFetch("/projects", {
        method: "POST",
        body: { name },
      });

      const created = data.project || data;
      setProjects((prev) => [...prev, created]);

      setExpandedProjects((prev) => ({
        ...prev,
        [created.id]: true,
      }));
    } catch (err) {
      console.error("Failed to create project:", err);
    } finally {
      setSavingProject(false);
    }
  };

  const startEditProject = (project) => {
    setEditingProjectId(project.id);
    setEditingProjectName(project.name || "");
  };

  const cancelEditProject = () => {
    setEditingProjectId(null);
    setEditingProjectName("");
  };

  const saveProjectName = async () => {
    const trimmed = editingProjectName.trim();
    if (!trimmed || !editingProjectId) return;

    try {
      setSavingProject(true);
      const data = await apiFetch(`/projects/${editingProjectId}`, {
        method: "PUT",
        body: { name: trimmed },
      });

      setProjects((prev) =>
        prev.map((p) =>
          p.id === editingProjectId ? { ...p, name: data.name } : p
        )
      );
      cancelEditProject();
    } catch (err) {
      console.error("Failed to rename project:", err);
    } finally {
      setSavingProject(false);
    }
  };

  const deleteProject = async (projectId) => {
    if (!window.confirm("Delete this project and its associations?")) return;

    try {
      setDeletingProjectId(projectId);
      await apiFetch(`/projects/${projectId}`, {
        method: "DELETE",
      });

      setProjects((prev) => prev.filter((p) => p.id !== projectId));

      // Any conversations that belonged to this project become unassigned
      setConvos((prev) =>
        prev.map((c) =>
          c.project_id === projectId ? { ...c, project_id: null } : c
        )
      );

      if (currentProjectId === projectId) {
        setCurrentProjectId(null);
      }
    } catch (err) {
      console.error("Failed to delete project:", err);
    } finally {
      setDeletingProjectId(null);
    }
  };

  const toggleProjectExpanded = (projectId) => {
    setExpandedProjects((prev) => ({
      ...prev,
      [projectId]: !prev[projectId],
    }));
  };

  const toggleUnassignedExpanded = () => {
    setUnassignedExpanded((prev) => !prev);
  };

  // ---- Conversation actions ----

  const startEditConversation = (conv) => {
    setEditingConvId(conv.id);
    setEditingConvTitle(conv.title || "");
  };

  const cancelEditConversation = () => {
    setEditingConvId(null);
    setEditingConvTitle("");
  };

  const saveConversationTitle = async (convId) => {
    const trimmed = editingConvTitle.trim();
    if (!trimmed) return;

    try {
      setSavingConvId(convId);
      const data = await apiFetch(`/conversations/${convId}`, {
        method: "PUT",
        body: { title: trimmed },
      });

      setConvos((prev) =>
        prev.map((c) =>
          c.id === convId ? { ...c, title: data.title || trimmed } : c
        )
      );
      cancelEditConversation();
    } catch (err) {
      console.error("Failed to rename conversation:", err);
    } finally {
      setSavingConvId(null);
    }
  };

  const moveConversation = async (convId, newProjectId) => {
    const project_id = newProjectId === "" ? null : Number(newProjectId);

    try {
      const data = await apiFetch(`/conversations/${convId}`, {
        method: "PUT",
        body: { project_id },
      });

      const updatedProjectId =
        data.project_id !== undefined ? data.project_id : project_id;

      setConvos((prev) =>
        prev.map((c) =>
          c.id === convId ? { ...c, project_id: updatedProjectId } : c
        )
      );
    } catch (err) {
      console.error("Failed to move conversation:", err);
    }
  };

  // ---- Group data ----

  const byProject = {};
  const unassigned = [];
  for (const c of convos) {
    if (c.project_id == null) {
      unassigned.push(c);
    } else {
      if (!byProject[c.project_id]) {
        byProject[c.project_id] = [];
      }
      byProject[c.project_id].push(c);
    }
  }

  const renderConversationRow = (c) => {
    const isActive = c.id === activeConversationId;
    const isEditing = editingConvId === c.id;
    const updatedLabel = formatDateLabel(c.updated_at);

    return (
      <div
        key={c.id}
        className={"conversation-item" + (isActive ? " active" : "")}
        onClick={() =>
          !isEditing && onSelectConversation && onSelectConversation(c.id)
        }
      >
        {isEditing ? (
          <div className="conversation-edit-row">
            <input
              className="conversation-edit-input"
              value={editingConvTitle}
              onChange={(e) => setEditingConvTitle(e.target.value)}
              onClick={(e) => e.stopPropagation()}
            />
            <div className="conversation-edit-controls">
              <button
                className="conversation-save-btn"
                type="button"
                disabled={savingConvId === c.id}
                onClick={(e) => {
                  e.stopPropagation();
                  saveConversationTitle(c.id);
                }}
              >
                {savingConvId === c.id ? "Saving…" : "Save"}
              </button>
              <button
                className="conversation-cancel-btn"
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  cancelEditConversation();
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="conversation-main-row">
            <div className="conversation-title">
              {c.title || `Conversation ${c.id}`}
            </div>
            <div className="conversation-actions">
              <select
                className="conversation-project-select"
                value={c.project_id || ""}
                onClick={(e) => e.stopPropagation()}
                onChange={(e) => moveConversation(c.id, e.target.value)}
              >
                <option value="">Unassigned</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <button
                className="conversation-rename-btn"
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  startEditConversation(c);
                }}
              >
                ✎
              </button>
              <button
                className="conversation-delete-btn"
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteConversation && onDeleteConversation(c.id);
                }}
              >
                🗑
              </button>
            </div>
          </div>
        )}

        {updatedLabel && !isEditing && (
          <div className="conversation-updated">{updatedLabel}</div>
        )}
      </div>
    );
  };

  // ---- Render ----

  return (
    <div className="projects-panel">
      <div className="conversation-header">
        <h3 className="panel-title">Projects</h3>
        <button
          className="new-conversation-btn"
          type="button"
          onClick={() => onNewConversation && onNewConversation()}
        >
          + New Chat
        </button>
      </div>

      <div className="projects-controls">
        <button
          className="new-project-btn"
          type="button"
          onClick={handleNewProject}
        >
          + New Project
        </button>
      </div>

      {loading && <div className="memory-loading">Loading…</div>}

      {!loading && (
        <>
          {projects.map((p) => {
            const projectConvos = byProject[p.id] || [];
            const expanded = expandedProjects[p.id] ?? true;

            const isEditingProj = p.id === editingProjectId;

            return (
              <div className="project-section" key={p.id}>
                <div
                  className={
                    "project-header" +
                    (currentProjectId === p.id ? " current-workspace" : "")
                  }
                  onClick={() => {
                    toggleProjectExpanded(p.id);
                    setCurrentProjectId(p.id);
                  }}
                >
                  <span className="project-toggle">
                    {expanded ? "▼" : "▶"}
                  </span>

                  {isEditingProj ? (
                    <>
                      <input
                        className="project-edit-input"
                        value={editingProjectName}
                        onChange={(e) =>
                          setEditingProjectName(e.target.value)
                        }
                        onClick={(e) => e.stopPropagation()}
                      />
                      <button
                        className="project-edit-save"
                        type="button"
                        disabled={savingProject}
                        onClick={(e) => {
                          e.stopPropagation();
                          saveProjectName();
                        }}
                      >
                        {savingProject ? "Saving…" : "Save"}
                      </button>
                      <button
                        className="project-edit-cancel"
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          cancelEditProject();
                        }}
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <span className="project-name">{p.name}</span>
                      <span className="project-count">
                        {projectConvos.length} conversation
                        {projectConvos.length === 1 ? "" : "s"}
                      </span>
                      <button
                        className="project-edit-save"
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          startEditProject(p);
                        }}
                      >
                        ✎
                      </button>
                      <button
                        className="project-delete-btn"
                        type="button"
                        disabled={deletingProjectId === p.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteProject(p.id);
                        }}
                      >
                        🗑
                      </button>
                    </>
                  )}
                </div>

                {expanded && projectConvos.length > 0 && (
                  <div className="project-conversations">
                    {projectConvos.map(renderConversationRow)}
                  </div>
                )}

                {expanded && projectConvos.length === 0 && (
                  <div className="memory-empty small">
                    No conversations in this project yet.
                  </div>
                )}
              </div>
            );
          })}

          {/* Unassigned section */}
          <div className="project-section">
            <div
              className={
                "project-header" +
                (currentProjectId === null ? " current-workspace" : "")
              }
              onClick={() => {
                toggleUnassignedExpanded();
                setCurrentProjectId(null);
              }}
            >
              <span className="project-toggle">
                {unassignedExpanded ? "▼" : "▶"}
              </span>
              <span className="project-name">Unassigned</span>
              <span className="project-count">
                {unassigned.length} conversation
                {unassigned.length === 1 ? "" : "s"}
              </span>
            </div>
            {unassignedExpanded && unassigned.length > 0 && (
              <div className="project-conversations">
                {unassigned.map(renderConversationRow)}
              </div>
            )}
            {unassignedExpanded && unassigned.length === 0 && (
              <div className="memory-empty small">
                No unassigned conversations.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

