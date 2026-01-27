// src/components/LeftPanel/ProjectsPanel.jsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiFetch } from "../../api/client";
import { formatUtcTimestamp } from "../../utils/formatUtc";



function getConversationTitleFromResponse(data, fallback) {
  if (!data) return fallback;
  if (typeof data.title === "string" && data.title.trim()) return data.title.trim();
  if (typeof data.name === "string" && data.name.trim()) return data.name.trim();
  if (data.conversation) {
    const c = data.conversation;
    if (typeof c.title === "string" && c.title.trim()) return c.title.trim();
    if (typeof c.name === "string" && c.name.trim()) return c.name.trim();
  }
  return fallback;
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
  // ----------------------------
  // State
  // ----------------------------
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
  const isMountedRef = useRef(true);

  // ----------------------------
  // Helpers
  // ----------------------------
  const closeMenus = useCallback(() => {
    setOpenConvMenuId(null);
    setOpenProjectMenuId(null);
  }, []);

  const cancelEditConversation = useCallback(() => {
    setEditingConvId(null);
    setEditingConvTitle("");
  }, []);

  const cancelEditProject = useCallback(() => {
    setEditingProjectId(null);
    setEditingProjectName("");
  }, []);

  // ----------------------------
  // Load data
  // ----------------------------
  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [projData, convData] = await Promise.all([
        apiFetch("/projects"),
        apiFetch("/conversations"),
      ]);

      const projList = projData?.projects || [];
      const convList = convData?.conversations || convData || [];

      if (!isMountedRef.current) return;

      setProjects(projList);
      setConvos(convList);

      // Phase 3.2: do not auto-select defaults here.
      // Selection should be owned by App.jsx.
    } catch (err) {
      console.error("ProjectsPanel: failed to load projects/conversations:", err);
    } finally {
      if (isMountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll, refreshToken]);

  // Close menus when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (panelRef.current && !panelRef.current.contains(event.target)) {
        closeMenus();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [closeMenus]);

  // ----------------------------
  // Derived data
  // ----------------------------
  const projectConversationCounts = useMemo(() => {
    const counts = projects.reduce((acc, p) => {
      acc[p.id] = 0;
      return acc;
    }, {});
    for (const c of convos) {
      if (c.project_id != null && counts[c.project_id] !== undefined) {
        counts[c.project_id] += 1;
      }
    }
    return counts;
  }, [projects, convos]);

  const unassignedCount = useMemo(() => {
    let n = 0;
    for (const c of convos) if (c.project_id == null) n += 1;
    return n;
  }, [convos]);

  const selectedProjectId = currentProjectId ?? null;

  const selectedProject = useMemo(() => {
    if (selectedProjectId == null) return null;
    return projects.find((p) => p.id === selectedProjectId) || null;
  }, [projects, selectedProjectId]);

  const displayedConvos = useMemo(() => {
    return convos.filter((c) =>
      selectedProjectId == null ? c.project_id == null : c.project_id === selectedProjectId
    );
  }, [convos, selectedProjectId]);

  // ----------------------------
  // Project actions
  // ----------------------------
  const handleNewProject = async () => {
    const name = window.prompt("Project name?");
    if (!name) return;

    try {
      setSavingProject(true);
      const data = await apiFetch("/projects", { method: "POST", body: { name } });
      const created = data?.project || data;

      setProjects((prev) => [...prev, created]);
      setCurrentProjectId?.(created.id);
      closeMenus();
    } catch (err) {
      console.error("ProjectsPanel: failed to create project:", err);
      alert(`Create project failed: ${err?.message || err}`);
    } finally {
      setSavingProject(false);
    }
  };

  const startEditProject = (project) => {
    setEditingProjectId(project.id);
    setEditingProjectName(project.name || "");
    setOpenProjectMenuId(null);
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
        prev.map((p) => (p.id === editingProjectId ? { ...p, name: data?.name || trimmed } : p))
      );
      cancelEditProject();
    } catch (err) {
      console.error("ProjectsPanel: failed to rename project:", err);
      alert(`Rename project failed: ${err?.message || err}`);
    } finally {
      setSavingProject(false);
    }
  };

  const deleteProject = async (projectId) => {
    if (!window.confirm("Delete this project and its associations?")) return;

    try {
      setDeletingProjectId(projectId);
      await apiFetch(`/projects/${projectId}`, { method: "DELETE" });

      setProjects((prev) => prev.filter((p) => p.id !== projectId));
      setConvos((prev) => prev.map((c) => (c.project_id === projectId ? { ...c, project_id: null } : c)));

      if (currentProjectId === projectId) setCurrentProjectId?.(null);
    } catch (err) {
      console.error("ProjectsPanel: failed to delete project:", err);
      alert(`Delete project failed: ${err?.message || err}`);
    } finally {
      setDeletingProjectId(null);
      closeMenus();
    }
  };

  // ----------------------------
  // Conversation actions
  // ----------------------------
  const startEditConversation = (conv) => {
    setEditingConvId(conv.id);
    setEditingConvTitle(conv.title || conv.name || "");
    setOpenConvMenuId(null);
  };

  const saveConversationTitle = async (convId) => {
    const trimmed = editingConvTitle.trim();
    if (!trimmed) return;

    try {
      setSavingConvId(convId);

      // Backend allows PATCH (OPTIONS shows: OPTIONS, PATCH, DELETE)
      const data = await apiFetch(`/conversations/${convId}`, {
        method: "PATCH",
        body: { title: trimmed, name: trimmed },
      });

      const finalTitle = getConversationTitleFromResponse(data, trimmed);

      setConvos((prev) =>
        prev.map((c) => (c.id === convId ? { ...c, title: finalTitle, name: finalTitle } : c))
      );

      cancelEditConversation();
    } catch (err) {
      console.error("ProjectsPanel: failed to rename conversation:", err);
      alert(`Rename failed: ${err?.message || err}`);
    } finally {
      setSavingConvId(null);
    }
  };

  const moveConversation = async (convId, newProjectId) => {
    const project_id = newProjectId === "" ? null : Number(newProjectId);

    try {
      const data = await apiFetch(`/conversations/${convId}/project`, {
        method: "PATCH",
        body: { project_id },
      });

      const updatedProjectId =
        data?.project_id !== undefined ? data.project_id : project_id;

      setConvos((prev) =>
        prev.map((c) =>
          c.id === convId ? { ...c, project_id: updatedProjectId } : c
        )
      );
    } catch (err) {
      console.error("ProjectsPanel: failed to move conversation:", err);
      alert(`Move failed: ${err?.message || err}`);
    } finally {
      setOpenConvMenuId(null);
    }
  };


  const deleteConversation = async (convId) => {
    if (!window.confirm("Delete this conversation? This cannot be undone.")) return;

    try {
      await apiFetch(`/conversations/${convId}`, { method: "DELETE" });
      setConvos((prev) => prev.filter((c) => c.id !== convId));

      if (activeConversationId === convId) onSelectConversation?.(null);
      onDeleteConversation?.(convId);
    } catch (err) {
      console.error("ProjectsPanel: failed to delete conversation:", err);
      alert(`Delete failed: ${err?.message || err}`);
    } finally {
      setOpenConvMenuId(null);
    }
  };

  // ----------------------------
  // Render helpers
  // ----------------------------
  const renderConversationRow = (c) => {
    const isActive = c.id === activeConversationId;
    const isEditing = editingConvId === c.id;
    const updatedLabel = formatUtcTimestamp(c.updated_at || c.created_at);

    return (
      <div
        key={c.id}
        className={"conversation-item" + (isActive ? " active" : "")}
        onClick={() => {
          if (isEditing) return;
          onSelectConversation?.(c.id);
        }}
      >
        {isEditing ? (
          <div className="conversation-edit-row">
            <input
              className="conversation-edit-input"
              value={editingConvTitle}
              onChange={(e) => setEditingConvTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveConversationTitle(c.id);
                if (e.key === "Escape") cancelEditConversation();
              }}
              onClick={(e) => e.stopPropagation()}
              autoFocus
            />
            <div className="conversation-edit-controls">
              <button
                className="conversation-save-btn"
                type="button"
                disabled={savingConvId === c.id || !editingConvTitle.trim()}
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
              <div className="conversation-title">{c.title || c.name || `Conversation ${c.id}`}</div>
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
                <button className="row-menu-item" type="button" onClick={() => startEditConversation(c)}>
                  <span className="row-menu-icon">✏️</span>
                  <span>Rename</span>
                </button>

                <div className="row-menu-divider" />
                <div className="row-menu-subheader">Move to project</div>

                <button className="row-menu-item" type="button" onClick={() => moveConversation(c.id, "")}>
                  <span className="row-menu-icon">📂</span>
                  <span>Unassigned</span>
                </button>

                {projects.map((p) => (
                  <button
                    key={p.id}
                    className="row-menu-item"
                    type="button"
                    onClick={() => moveConversation(c.id, String(p.id))}
                  >
                    <span className="row-menu-icon">📁</span>
                    <span>{p.name}</span>
                  </button>
                ))}

                <div className="row-menu-divider" />

                <button className="row-menu-item danger" type="button" onClick={() => deleteConversation(c.id)}>
                  <span className="row-menu-icon">🗑</span>
                  <span>Delete</span>
                </button>
              </div>
            )}
          </>
        )}

        {updatedLabel && !isEditing && <div className="conversation-updated">{updatedLabel}</div>}
      </div>
    );
  };

  // ----------------------------
  // Render
  // ----------------------------
  return (
    <div className="projects-panel" ref={panelRef}>
      <div className="conversation-header">
        <h3 className="panel-title">Projects</h3>
        <button className="new-project-btn" type="button" onClick={handleNewProject} disabled={savingProject}>
          + New Project
        </button>
      </div>

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
                    className={"project-header" + (isActive ? " current-workspace" : "")}
                    onClick={() => {
                      setCurrentProjectId?.(p.id);
                      closeMenus();
                    }}
                  >
                    {isEditingProj ? (
                      <>
                        <input
                          className="project-edit-input"
                          value={editingProjectName}
                          onChange={(e) => setEditingProjectName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") saveProjectName();
                            if (e.key === "Escape") cancelEditProject();
                          }}
                          onClick={(e) => e.stopPropagation()}
                          autoFocus
                        />
                        <button
                          className="project-edit-save"
                          type="button"
                          disabled={savingProject || !editingProjectName.trim()}
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
                          {(projectConversationCounts[p.id] || 0) === 1 ? "" : "s"}
                        </span>
                        <button
                          className="row-menu-toggle"
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenConvMenuId(null);
                            setOpenProjectMenuId((prev) => (prev === p.id ? null : p.id));
                          }}
                        >
                          ⋯
                        </button>

                        {openProjectMenuId === p.id && (
                          <div className="row-menu" onClick={(e) => e.stopPropagation()}>
                            <button className="row-menu-item" type="button" onClick={() => startEditProject(p)}>
                              <span className="row-menu-icon">✏️</span>
                              <span>Rename</span>
                            </button>

                            <div className="row-menu-divider" />

                            <button
                              className="row-menu-item danger"
                              type="button"
                              disabled={deletingProjectId === p.id}
                              onClick={() => deleteProject(p.id)}
                            >
                              <span className="row-menu-icon">🗑</span>
                              <span>{deletingProjectId === p.id ? "Deleting…" : "Delete"}</span>
                            </button>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}

            <div className="project-section">
              <div
                className={"project-header" + (currentProjectId == null ? " current-workspace" : "")}
                onClick={() => {
                  setCurrentProjectId?.(null);
                  closeMenus();
                }}
              >
                <span className="project-name">Unassigned</span>
                <span className="project-count">
                  {unassignedCount} conversation{unassignedCount === 1 ? "" : "s"}
                </span>
              </div>
            </div>

            {projects.length === 0 && (
              <div className="memory-empty small">No projects yet. Use “+ New Project” to create one.</div>
            )}
          </div>

          <div className="conversation-header" style={{ marginTop: "0.35rem" }}>
            <h3 className="panel-title">{selectedProject ? selectedProject.name : "Unassigned"}</h3>
            <button
              className="new-conversation-btn"
              type="button"
              onClick={() => onNewConversation?.({ project_id: currentProjectId ?? null })}
            >
              + New Chat
            </button>
          </div>

          <div className="project-conversations">
            {displayedConvos.length > 0 ? (
              displayedConvos.map(renderConversationRow)
            ) : (
              <div className="memory-empty small">No conversations in this project yet.</div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

