// src/components/LeftPanel/ProjectsPanel.jsx
import { useEffect, useRef, useState } from "react";
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
  onDeleteConversation, // kept for compatibility, no longer required for delete
  refreshToken,
  currentProjectId,
  setCurrentProjectId,
  onNewConversation,
}) {
  const [projects, setProjects] = useState([]);
  const [convos, setConvos] = useState([]);
  const [loading, setLoading] = useState(false);

  const [editingConvId, setEditingConvId] = useState(null);
  const [editingConvTitle, setEditingConvTitle] = useState("");
  const [savingConvId, setSavingConvId] = useState(null);

  const [editingProjectId, setEditingProjectId] = useState(null);
  const [editingProjectName, setEditingProjectName] = useState("");
  const [savingProject, setSavingProject] = useState(false);
  const [deletingProjectId, setDeletingProjectId] = useState(null);

  const [openConvMenuId, setOpenConvMenuId] = useState(null);
  const [openProjectMenuId, setOpenProjectMenuId] = useState(null);

  const panelRef = useRef(null);

  // ---- Load projects + conversations ----
  async function loadAll() {
    setLoading(true);
    try {
      const [projData, convData] = await Promise.all([
        apiFetch("/projects"),
        apiFetch("/conversations"),
      ]);

      const projList = projData.projects || [];
      const convList = convData.conversations || convData || [];

      setProjects(projList);
      setConvos(convList);

      // If nothing is selected yet, default to first project or Unassigned
      if (currentProjectId === undefined) {
        if (projList.length > 0) {
          setCurrentProjectId(projList[0].id);
        } else {
          setCurrentProjectId(null);
        }
      }
    } catch (err) {
      console.error("Failed to load projects/conversations:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken]);

  // ---- Click outside to close menus ----
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (panelRef.current && !panelRef.current.contains(event.target)) {
        setOpenConvMenuId(null);
        setOpenProjectMenuId(null);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

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
      setCurrentProjectId(created.id);
    } catch (err) {
      console.error("Failed to create project:", err);
    } finally {
      setSavingProject(false);
    }
  };

  const startEditProject = (project) => {
    setEditingProjectId(project.id);
    setEditingProjectName(project.name || "");
    setOpenProjectMenuId(null);
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
          p.id === editingProjectId ? { ...p, name: data.name || trimmed } : p
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
      setOpenProjectMenuId(null);
    }
  };

  // ---- Conversation actions ----

  const startEditConversation = (conv) => {
    setEditingConvId(conv.id);
    setEditingConvTitle(conv.title || "");
    setOpenConvMenuId(null);
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

  // ✅ NEW: actually delete a conversation via API
  const deleteConversation = async (convId) => {
    if (!window.confirm("Delete this conversation? This cannot be undone.")) {
      return;
    }

    try {
      // Call the backend
      await apiFetch(`/conversations/${convId}`, { method: "DELETE" });

      // Update local state
      setConvos((prev) => prev.filter((c) => c.id !== convId));

      // If the active conversation was deleted, clear selection
      if (activeConversationId === convId) {
        onSelectConversation && onSelectConversation(null);
      }

      // Optional: inform parent (kept for compatibility)
      if (onDeleteConversation) {
        onDeleteConversation(convId);
      }
    } catch (err) {
      console.error("Failed to delete conversation:", err);
      alert(`Delete failed: ${err?.message || err}`);
    } finally {
      setOpenConvMenuId(null);
    }
  };

  // ---- Derived data: counts, selection, filtered chats ----

  const projectConversationCounts = projects.reduce((acc, p) => {
    acc[p.id] = 0;
    return acc;
  }, {});
  let unassignedCount = 0;

  for (const c of convos) {
    if (c.project_id == null) {
      unassignedCount += 1;
    } else if (projectConversationCounts[c.project_id] !== undefined) {
      projectConversationCounts[c.project_id] += 1;
    }
  }

  const selectedProjectId = currentProjectId ?? null;
  const selectedProject =
    selectedProjectId == null
      ? null
      : projects.find((p) => p.id === selectedProjectId) || null;

  const displayedConvos = convos.filter((c) =>
    selectedProjectId == null
      ? c.project_id == null
      : c.project_id === selectedProjectId
  );

  // ---- Render helpers ----

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
          <>
            <div className="conversation-main-row">
              <div className="conversation-title">
                {c.title || `Conversation ${c.id}`}
              </div>
              <button
                className="row-menu-toggle"
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setOpenProjectMenuId(null);
                  setOpenConvMenuId((prev) => (prev === c.id ? null : c.id));
                }}
              >
                ⋯
              </button>
            </div>

            {openConvMenuId === c.id && (
              <div className="row-menu" onClick={(e) => e.stopPropagation()}>
                <button
                  className="row-menu-item"
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    startEditConversation(c);
                  }}
                >
                  <span className="row-menu-icon">✏️</span>
                  <span>Rename</span>
                </button>

                <div className="row-menu-divider" />

                <div className="row-menu-subheader">Move to project</div>
                <button
                  className="row-menu-item"
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    moveConversation(c.id, "");
                    setOpenConvMenuId(null);
                  }}
                >
                  <span className="row-menu-icon">📂</span>
                  <span>Unassigned</span>
                </button>
                {projects.map((p) => (
                  <button
                    key={p.id}
                    className="row-menu-item"
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      moveConversation(c.id, String(p.id));
                      setOpenConvMenuId(null);
                    }}
                  >
                    <span className="row-menu-icon">📁</span>
                    <span>{p.name}</span>
                  </button>
                ))}

                <div className="row-menu-divider" />

                <button
                  className="row-menu-item danger"
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConversation(c.id);
                  }}
                >
                  <span className="row-menu-icon">🗑</span>
                  <span>Delete</span>
                </button>
              </div>
            )}
          </>
        )}

        {updatedLabel && !isEditing && (
          <div className="conversation-updated">{updatedLabel}</div>
        )}
      </div>
    );
  };

  // ---- Render ----

  return (
    <div className="projects-panel" ref={panelRef}>
      {/* Projects header */}
      <div className="conversation-header">
        <h3 className="panel-title">Projects</h3>
        <button
          className="new-project-btn"
          type="button"
          onClick={handleNewProject}
        >
          + New Project
        </button>
      </div>

      {/* Project list (folders + Unassigned) */}
      {loading && <div className="memory-loading">Loading…</div>}

      {!loading && (
        <>
          <div className="projects-list">
            {projects.map((p) => {
              const isEditingProj = p.id === editingProjectId;
              const isActive = currentProjectId === p.id;

              return (
                <div className="project-section" key={p.id}>
                  <div
                    className={
                      "project-header" + (isActive ? " current-workspace" : "")
                    }
                    onClick={() => {
                      setCurrentProjectId(p.id);
                      setOpenProjectMenuId(null);
                      setOpenConvMenuId(null);
                    }}
                  >
                    {isEditingProj ? (
                      <>
                        <input
                          className="project-edit-input"
                          value={editingProjectName}
                          onChange={(e) => setEditingProjectName(e.target.value)}
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
                          {projectConversationCounts[p.id] || 0} conversation
                          {projectConversationCounts[p.id] === 1 ? "" : "s"}
                        </span>
                        <button
                          className="row-menu-toggle"
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenConvMenuId(null);
                            setOpenProjectMenuId((prev) =>
                              prev === p.id ? null : p.id
                            );
                          }}
                        >
                          ⋯
                        </button>
                        {openProjectMenuId === p.id && (
                          <div
                            className="row-menu"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              className="row-menu-item"
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                startEditProject(p);
                              }}
                            >
                              <span className="row-menu-icon">✏️</span>
                              <span>Rename</span>
                            </button>
                            <div className="row-menu-divider" />
                            <button
                              className="row-menu-item danger"
                              type="button"
                              disabled={deletingProjectId === p.id}
                              onClick={(e) => {
                                e.stopPropagation();
                                deleteProject(p.id);
                              }}
                            >
                              <span className="row-menu-icon">🗑</span>
                              <span>Delete</span>
                            </button>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Unassigned pseudo-project */}
            <div className="project-section">
              <div
                className={
                  "project-header" +
                  (currentProjectId == null ? " current-workspace" : "")
                }
                onClick={() => {
                  setCurrentProjectId(null);
                  setOpenProjectMenuId(null);
                  setOpenConvMenuId(null);
                }}
              >
                <span className="project-name">Unassigned</span>
                <span className="project-count">
                  {unassignedCount} conversation
                  {unassignedCount === 1 ? "" : "s"}
                </span>
              </div>
            </div>

            {projects.length === 0 && (
              <div className="memory-empty small">
                No projects yet. Use &ldquo;+ New Project&rdquo; to create one.
              </div>
            )}
          </div>

          {/* Chats for selected project */}
          <div className="conversation-header" style={{ marginTop: "0.35rem" }}>
            <h3 className="panel-title">
              {selectedProject ? selectedProject.name : "Unassigned"}
            </h3>
            <button
              className="new-conversation-btn"
              type="button"
              onClick={() => onNewConversation && onNewConversation()}
            >
              + New Chat
            </button>
          </div>

          <div className="project-conversations">
            {displayedConvos.length > 0 ? (
              displayedConvos.map(renderConversationRow)
            ) : (
              <div className="memory-empty small">
                No conversations in this project yet.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

