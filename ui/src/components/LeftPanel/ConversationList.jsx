// src/components/LeftPanel/ConversationList.jsx
import { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";

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

  async function loadConversations() {
    try {
      setLoading(true);
      const data = await apiFetch("/conversations");
      setConvos(data.conversations || []);
    } catch (err) {
      console.error("Failed to load conversations:", err);
      setConvos([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadConversations();
  }, [refreshToken]);

  const startEdit = (conv) => {
    setEditingId(conv.id);
    setEditingTitle(conv.title || "");
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditingTitle("");
  };

  const saveEdit = async () => {
    if (!editingId || !editingTitle.trim()) {
      cancelEdit();
      return;
    }
    try {
      setSaving(true);
      const data = await apiFetch(`/conversations/${editingId}`, {
        method: "PATCH",
        body: { title: editingTitle.trim() },
      });
      setConvos((prev) =>
        prev.map((c) =>
          c.id === editingId ? { ...c, title: data.title } : c
        )
      );
      cancelEdit();
    } catch (err) {
      console.error("Failed to rename conversation:", err);
    } finally {
      setSaving(false);
    }
  };

  const deleteConv = async (convId) => {
    if (!window.confirm("Delete this conversation? This cannot be undone.")) {
      return;
    }
    try {
      setDeletingId(convId);
      await apiFetch(`/conversations/${convId}`, {
        method: "DELETE",
      });
      // Remove from local list
      setConvos((prev) => prev.filter((c) => c.id !== convId));
      // Inform parent if needed
      if (onDeleteConversation) {
        onDeleteConversation(convId);
      }
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="conversation-list">
      <div className="conversation-header">
        <h3 className="panel-title">Conversations</h3>
        <button
          className="new-conversation-btn"
          type="button"
          onClick={() => onNewConversation && onNewConversation()}
        >
          + New
        </button>
      </div>

      {loading && <div className="memory-loading">Loading...</div>}

      {!loading && convos.length === 0 && (
        <div className="memory-empty">No conversations yet.</div>
      )}

      {!loading &&
        convos.map((c) => {
          const isActive = c.id === activeConversationId;
          const isEditing = c.id === editingId;

          let updatedLabel = "";
          if (c.updated_at) {
            try {
              updatedLabel = new Date(c.updated_at).toLocaleString();
            } catch {
              updatedLabel = c.updated_at;
            }
          }

          return (
            <div
              key={c.id}
              className={
                "conversation-item" + (isActive ? " active" : "")
              }
              onClick={() => !isEditing && onSelect && onSelect(c.id)}
            >
              {isEditing ? (
                <div className="conversation-edit-row">
                  <input
                    className="conversation-edit-input"
                    value={editingTitle}
                    onChange={(e) => setEditingTitle(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                  />
                  <button
                    className="conversation-edit-save"
                    type="button"
                    disabled={saving}
                    onClick={(e) => {
                      e.stopPropagation();
                      saveEdit();
                    }}
                  >
                    Save
                  </button>
                  <button
                    className="conversation-edit-cancel"
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      cancelEdit();
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
                    <button
                      className="conversation-rename-btn"
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        startEdit(c);
                      }}
                    >
                      ✎
                    </button>
                    <button
                      className="conversation-delete-btn"
                      type="button"
                      disabled={deletingId === c.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteConv(c.id);
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
        })}
    </div>
  );
}

