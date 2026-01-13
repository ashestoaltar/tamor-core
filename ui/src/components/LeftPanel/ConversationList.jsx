// src/components/LeftPanel/ConversationList.jsx
import { useEffect, useRef, useState } from "react";
import { apiFetch } from "../../api/client";
import { formatUtcTimestamp } from "../../utils/formatUtc";

export default function ConversationList({
  activeConversationId,
  onSelect,
  onNewConversation,
  refreshToken,
  onDeleteConversation,
}) {
  const [convos, setConvos] = useState([]);
  const [loading, setLoading] = useState(true);

  const [editingId, setEditingId] = useState(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  const [openMenuId, setOpenMenuId] = useState(null);
  const listRef = useRef(null);

  async function loadConversations() {
    try {
      setLoading(true);
      const data = await apiFetch("/conversations");
      setConvos(data.conversations || []);
    } catch (err) {
      console.error("ConversationList: failed to load conversations:", err);
      setConvos([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadConversations();
  }, [refreshToken]);

  useEffect(() => {
    const onDocMouseDown = (e) => {
      if (!openMenuId) return;
      if (!listRef.current) return;
      if (!listRef.current.contains(e.target)) setOpenMenuId(null);
    };

    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        setOpenMenuId(null);
        if (editingId) cancelEdit();
      }
    };

    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [openMenuId, editingId]);

  const startEdit = (conv) => {
    setOpenMenuId(null);
    setEditingId(conv.id);
    setEditingTitle(conv.title || conv.name || "");
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditingTitle("");
  };

  const saveEdit = async () => {
    if (!editingId) return;

    const nextTitle = editingTitle.trim();
    if (!nextTitle) {
      cancelEdit();
      return;
    }

    try {
      setSaving(true);

      const data = await apiFetch(`/conversations/${editingId}`, {
        method: "PATCH",
        body: { title: nextTitle, name: nextTitle },
      });

      const finalTitle = data?.title || data?.name || nextTitle;

      setConvos((prev) => prev.map((c) => (c.id === editingId ? { ...c, title: finalTitle, name: finalTitle } : c)));
      cancelEdit();
    } catch (err) {
      console.error("ConversationList: failed to rename conversation:", err);
      alert(`Rename failed: ${err?.message || err}`);
    } finally {
      setSaving(false);
    }
  };

  const deleteConv = async (convId) => {
    setOpenMenuId(null);

    if (!window.confirm("Delete this conversation? This cannot be undone.")) return;

    try {
      setDeletingId(convId);

      await apiFetch(`/conversations/${convId}`, { method: "DELETE" });
      setConvos((prev) => prev.filter((c) => c.id !== convId));

      if (activeConversationId === convId) onSelect?.(null);
      if (typeof onDeleteConversation === "function") onDeleteConversation(convId);
    } catch (err) {
      console.error("ConversationList: failed to delete conversation:", err);
      alert(`Delete failed: ${err?.message || err}`);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="conversation-list" ref={listRef}>
      <div className="conversation-header">
        <h3 className="panel-title">Conversations</h3>
        <button className="new-conversation-btn" type="button" onClick={() => onNewConversation?.()}>
          + New
        </button>
      </div>

      {loading && <div className="memory-loading">Loading…</div>}
      {!loading && convos.length === 0 && <div className="memory-empty">No conversations yet.</div>}

      {!loading &&
        convos.map((c) => {
          const isActive = c.id === activeConversationId;
          const isEditing = c.id === editingId;
          const isMenuOpen = c.id === openMenuId;

          const ts = c.updated_at || c.created_at || "";
          const updatedLabel = formatUtcTimestamp(ts);

          return (
            <div
              key={c.id}
              className={"conversation-item" + (isActive ? " active" : "")}
              onClick={() => {
                if (!isEditing) onSelect?.(c.id);
              }}
            >
              {isEditing ? (
                <div className="conversation-edit-row" onClick={(e) => e.stopPropagation()}>
                  <input
                    className="conversation-edit-input"
                    value={editingTitle}
                    onChange={(e) => setEditingTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") saveEdit();
                      if (e.key === "Escape") cancelEdit();
                    }}
                    autoFocus
                  />

                  <div className="conversation-edit-controls">
                    <button
                      className="conversation-save-btn"
                      type="button"
                      disabled={saving || !editingTitle.trim()}
                      onClick={saveEdit}
                    >
                      {saving ? "Saving…" : "Save"}
                    </button>
                    <button className="conversation-cancel-btn" type="button" onClick={cancelEdit}>
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="conversation-main-row">
                  <div className="conversation-title">{c.title || c.name || `Conversation ${c.id}`}</div>

                  <button
                    className="row-menu-toggle"
                    type="button"
                    aria-label="Conversation menu"
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenMenuId((prev) => (prev === c.id ? null : c.id));
                    }}
                  >
                    ⋯
                  </button>

                  {isMenuOpen && (
                    <div className="row-menu" onClick={(e) => e.stopPropagation()}>
                      <button className="row-menu-item" type="button" onClick={() => startEdit(c)}>
                        <span className="row-menu-icon">✎</span>
                        Rename
                      </button>

                      <div className="row-menu-divider" />

                      <button
                        className="row-menu-item danger"
                        type="button"
                        disabled={deletingId === c.id}
                        onClick={() => deleteConv(c.id)}
                      >
                        <span className="row-menu-icon">🗑</span>
                        {deletingId === c.id ? "Deleting…" : "Delete"}
                      </button>
                    </div>
                  )}
                </div>
              )}

              {updatedLabel && !isEditing && <div className="conversation-updated">{updatedLabel}</div>}
            </div>
          );
        })}
    </div>
  );
}

