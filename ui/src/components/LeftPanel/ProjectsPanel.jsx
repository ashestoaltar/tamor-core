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
  refreshToken,
  onNewConversation,
  onDeleteConversation,
}) {
  const [projects, setProjects] = useState([]);
  const [convos, setConvos] = useState([]);
  const [loading, setLoading] = useState(true);

  const [expandedProjects, setExpandedProjects] = useState({});
  const [unassignedExpanded, setUnassignedExpanded] = useState(true);

  const [editingProjectId, setEditingProjectId] = useState(null);
  const [editingProjectName, setEditingProjectName] = useState("");
  const [savingProject, setSavingProject] = useState(false);

  const [editingConvId, setEditingConvId] = useState(null);
  const [editingConvTitle, setEditingConvTitle] = useState("");
  const [savingConv, setSavingConv] = useState(false);
  const [deletingConvId, setDeletingConvId] = useState(null);
  const [deletingProjectId, setDeletingProjectId] = useState(null);

    async function loadAll() {
    setLoading(true);
    try {
      // Fetch projects + conversations independently so one failing
      // doesn't blow away the other.
      const projPromise = apiFetch("/projects").catch((err) => {
        console.error("Failed to load projects:", err);
        return { projects: [] };
      });

      const convPromise = apiFetch("/conversations").catch((err) => {
        console.error("Failed to load conversations:", err);
        return { conversations: [] };
      });

      const [projData, convData] = await Promise.all([projPromise, convPromise]);

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
    const name = window.prompt("Project name:");
    if (!name || !name.trim()) return;

    try {
      const data = await apiFetch("/projects", {
        method: "POST",
        body: { name: name.trim() },
      });
      setProjects((prev) => [
        { id: data.id, name: data.name, created_at: null, updated_at: null },
        ...prev,
      ]);
      setExpandedProjects((prev) => ({ ...prev, [data.id]: true }));
    } catch (err) {
      console.error("Failed to create project:", err);
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

  const saveEditProject = async () => {
    if (!editingProjectId || !editingProjectName.trim()) {
      cancelEditProject();
      return;
    }
    try {
      setSavingProject(true);
      const data = await apiFetch(`/projects/${editingProjectId}`, {
        method: "PATCH",
        body: { name: editingProjectName.trim() },
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
    if (
      !window.confirm(
        "Delete this project? Its conversations will become Unassigned."
      )
    ) {
      return;
    }
    try {
      setDeletingProjectId(projectId);
      await apiFetch(`/projects/${projectId}`, {
        method: "DELETE",
      });
      // Remove project from list
      setProjects((prev) => prev.filter((p) => p.id !== projectId));
      // Unassign conversations locally
      setConvos((prev) =>
        prev.map((c) =>
          c.project_id === projectId ? { ...c, project_id: null } : c
        )
      );
      setExpandedProjects((prev) => {
        const copy = { ...prev };
        delete copy[projectId];
        return copy;
      });
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

  const saveEditConversation = async () => {
    if (!editingConvId || !editingConvTitle.trim()) {
      cancelEditConversation();
      return;
    }
    try {
      setSavingConv(true);
      const data = await apiFetch(`/conversations/${editingConvId}`, {
        method: "PATCH",
        body: { title: editingConvTitle.trim() },
      });
      setConvos((prev) =>
        prev.map((c) =>
          c.id === editingConvId ? { ...c, title: data.title } : c
        )
      );
      cancelEditConversation();
    } catch (err) {
      console.error("Failed to rename conversation:", err);
    } finally {
      setSavingConv(false);
    }
  };

  const deleteConversation = async (convId) => {
    if (!window.confirm("Delete this conversation? This cannot be undone.")) {
      return;
    }
    try {
      setDeletingConvId(convId);
      await apiFetch(`/conversations/${convId}`, {
        method: "DELETE",
      });
      setConvos((prev) => prev.filter((c) => c.id !== convId));
      if (onDeleteConversation) {
        onDeleteConversation(convId);
      }
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    } finally {
      setDeletingConvId(null);
    }
  };

  const moveConversation = async (convId, projectIdValue) => {
    // projectIdValue is string from <select>, we convert ""->null or numeric
    const project_id =
      projectIdValue === "" ? null : parseInt(projectIdValue, 10);

    try {
      await apiFetch(`/conversations/${convId}/project`, {
        method: "PATCH",
        body: { project_id },
      });
      setConvos((prev) =>
        prev.map((c) =>
          c.id === convId ? { ...c, project_id: project_id } : c
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
      if (!byProject[c.project_id]) byProject[c.project_id] = [];
      byProject[c.project_id].push(c);
    }
  }

  const renderConversationRow = (c) => {
    const isActive = c.id === activeConversationId;
    const isEditing = c.id === editingConvId;

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
            <button
              className="conversation-edit-save"
              type="button"
              disabled={savingConv}
              onClick={(e) => {
                e.stopPropagation();
                saveEditConversation();
              }}
            >
              Save
            </button>
            <button
              className="conversation-edit-cancel"
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                cancelEditConversation();
              }}
            >
              Cancel
            </button>
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
                disabled={deletingConvId === c.id}
                onClick={(e) => {
                  e.stopPropagation();
                  deleteConversation(c.id);
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
          {/* Unassigned section */}
          <div className="project-section">
            <div
              className="project-header"
              onClick={toggleUnassignedExpanded}
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

          {/* Projects sections */}
          {projects.map((p) => {
            const projectConvos = byProject[p.id] || [];
            const expanded = expandedProjects[p.id] ?? true;

            const isEditingProj = p.id === editingProjectId;
            const updatedLabel = formatDateLabel(p.updated_at);

            return (
              <div className="project-section" key={p.id}>
                <div
                  className="project-header"
                  onClick={() => toggleProjectExpanded(p.id)}
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
                          saveEditProject();
                        }}
                      >
                        Save
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
                        className="project-rename-btn"
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

                  {updatedLabel && !isEditingProj && (
                    <span className="project-updated">{updatedLabel}</span>
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
        </>
      )}
    </div>
  );
}
