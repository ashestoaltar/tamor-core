import "./ChatPanel.css";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { apiFetch } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import TaskPill from "./TaskPill";

const EMPTY_STATE_TEXT = "My name is Tamor. How can I help you today?";

function getFileEmoji(filename, mimeType) {
  const name = (filename || "").toLowerCase();
  const mime = (mimeType || "").toLowerCase();

  if (name.endsWith(".pdf") || mime === "application/pdf") return "📄";
  if (name.match(/\.(png|jpe?g|gif|webp|svg)$/) || mime.startsWith("image/")) return "🖼️";
  if (name.match(/\.(mp4|mov|mkv|webm)$/) || mime.startsWith("video/")) return "🎬";
  if (name.match(/\.(mp3|wav|flac|m4a)$/) || mime.startsWith("audio/")) return "🎵";
  if (name.match(/\.(xls|xlsx|csv)$/)) return "📊";
  if (name.match(/\.(doc|docx)$/)) return "📝";
  if (name.match(/\.(zip|rar|7z)$/)) return "🖜️";
  if (name.match(/\.(js|ts|jsx|tsx|py|rb|go|java|c|cpp|cs|php|html|css|json|yml|yaml|lisp)$/)) return "💻";
  return "📁";
}

function isTextLikeFile(file) {
  const mime = (file?.mime_type || "").toLowerCase();
  const name = (file?.filename || "").toLowerCase();
  if (mime.startsWith("text/")) return true;

  const textExts = [
    ".txt", ".md", ".markdown", ".json", ".js", ".ts", ".jsx", ".tsx",
    ".py", ".lisp", ".html", ".css", ".csv", ".yml", ".yaml"
  ];
  return textExts.some((ext) => name.endsWith(ext));
}

function FileBadgeWithPreview({ file }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [text, setText] = useState("");

  const fileId = file.file_id || file.id;
  const textLike = isTextLikeFile(file);

  const handleClick = async () => {
    if (!fileId) return;

    if (!textLike) {
      window.dispatchEvent(new CustomEvent("tamor-scroll-to-file", { detail: { fileId } }));
      return;
    }

    if (!open && !text && !loading) {
      setLoading(true);
      setError("");
      try {
        const data = await apiFetch(`/files/${fileId}/content`);
        const fullText = data.text || "";
        const maxChars = 800;
        const snippet =
          fullText.length > maxChars
            ? fullText.slice(0, maxChars) + "\n\n[... truncated ...]"
            : fullText;
        setText(snippet || "[File is empty or could not be read]");
      } catch (err) {
        console.error("Failed to load inline file preview:", err);
        setError(err.message || "Failed to load preview");
      } finally {
        setLoading(false);
      }
    }

    setOpen((prev) => !prev);
  };

  return (
    <div className="chat-file-badge-row">
      <button
        type="button"
        className={"chat-file-badge" + (loading ? " chat-file-badge-loading" : "")}
        onClick={handleClick}
        title={
          textLike
            ? "Click to toggle inline preview (and scroll to file in Files tab)."
            : "Click to jump to this file in the Files tab."
        }
      >
        <span className="chat-file-badge-icon">{getFileEmoji(file.filename, file.mime_type)}</span>
        <span className="chat-file-badge-name">{file.filename}</span>
      </button>

      {open && textLike && (
        <div className="chat-file-preview">
          {loading && <div className="chat-file-preview-header">Loading preview…</div>}
          {error && <div className="chat-file-preview-header chat-file-preview-error">{error}</div>}
          {!loading && !error && (
            <>
              <div className="chat-file-preview-header">Inline preview (first ~800 characters)</div>
              <pre>{text}</pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Toast({ text }) {
  if (!text) return null;
  return (
    <div
      style={{
        position: "absolute",
        right: 16,
        top: 14,
        padding: "10px 12px",
        borderRadius: 10,
        background: "rgba(20,20,20,0.92)",
        border: "1px solid rgba(255,255,255,0.10)",
        color: "#fff",
        fontSize: 14,
        zIndex: 9999,
        boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
        maxWidth: 340,
      }}
    >
      {text}
    </div>
  );
}

function appendUnique(prev, msg) {
  if (!msg) return prev;
  if (msg.id && prev.some((x) => x?.id === msg.id)) return prev;
  return [...prev, msg];
}

function mergeMessages(prev, serverMsgs) {
  const byId = new Map();
  for (const m of prev || []) {
    if (m?.id != null) byId.set(String(m.id), m);
  }

  const out = [];
  for (const sm of serverMsgs || []) {
    const key = sm?.id != null ? String(sm.id) : null;
    if (!key) {
      out.push(sm);
      continue;
    }
    const existing = byId.get(key);
    const merged = existing ? { ...existing, ...sm } : sm;
    out.push(merged);
  }

  const pending = (prev || []).filter((m) => m?.id == null && m?.content);
  for (const p of pending.slice(-4)) {
    const already = out.some(
      (m) => m?.id == null && m?.role === p.role && m?.content === p.content
    );
    if (!already) out.push(p);
  }

  return out;
}

// -----------------------------
// Project Required Modal
// -----------------------------
function ProjectRequiredModal({
  open,
  loading,
  error,
  projects,
  selectedProjectId,
  setSelectedProjectId,
  newProjectName,
  setNewProjectName,
  onCreateProject,
  onConfirm,
  onClose,
}) {
  if (!open) return null;

  return (
    <div
      className="modal-backdrop"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: 16,
      }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal-card"
        style={{
          width: "min(720px, 100%)",
          borderRadius: 14,
          background: "rgba(18,18,18,0.97)",
          border: "1px solid rgba(255,255,255,0.12)",
          boxShadow: "0 20px 60px rgba(0,0,0,0.45)",
          padding: 16,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>Choose where to attach this file</div>
            <div style={{ marginTop: 4, opacity: 0.85, fontSize: 13 }}>
              Select an existing project or create a new one, then we’ll attach your file there.
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            title="Close"
            style={{
              background: "transparent",
              border: "1px solid rgba(255,255,255,0.14)",
              color: "#fff",
              borderRadius: 10,
              padding: "6px 10px",
              cursor: "pointer",
              height: 34,
            }}
          >
            ✕
          </button>
        </div>

        <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "1fr", gap: 12 }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>Select project</div>

            {loading && <div style={{ opacity: 0.85, fontSize: 13 }}>Loading projects…</div>}
            {error && (
              <div style={{ color: "#ffb4b4", fontSize: 13, whiteSpace: "pre-wrap" }}>{error}</div>
            )}

            {!loading && (
              <select
                value={selectedProjectId ?? ""}
                onChange={(e) => setSelectedProjectId(e.target.value ? Number(e.target.value) : null)}
                style={{
                  width: "100%",
                  borderRadius: 10,
                  padding: "10px 12px",
                  background: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  color: "#fff",
                  colorScheme: "dark",
                }}
              >
                <option value="">— Choose a project —</option>
                {(projects || []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name ?? `Project ${p.id}`}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: 10, alignItems: "end", }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>Create new project</div>
              <input
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                placeholder="New project name…"
                style={{
                  width: "100%",
                  minWidth: 0,
                  borderRadius: 10,
                  padding: "10px 12px",
                  background: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  color: "#fff",
                }}
              />
            </div>
            <button
              type="button"
              onClick={onCreateProject}
              disabled={!newProjectName.trim()}
              style={{
                alignSelf: "end",
                width: 96,
                borderRadius: 10,
                padding: "10px 12px",
                border: "1px solid rgba(255,255,255,0.14)",
                background: !newProjectName.trim()
                  ? "rgba(255,255,255,0.06)"
                  : "rgba(255,255,255,0.10)",
                color: "#fff",
                cursor: !newProjectName.trim() ? "not-allowed" : "pointer",
                height: 42,
              }}
            >
              Create
            </button>
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 16 }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              borderRadius: 10,
              padding: "10px 12px",
              border: "1px solid rgba(255,255,255,0.14)",
              background: "transparent",
              color: "#fff",
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={!selectedProjectId}
            style={{
              borderRadius: 10,
              padding: "10px 12px",
              border: "1px solid rgba(255,255,255,0.14)",
              background: selectedProjectId ? "rgba(255,255,255,0.12)" : "rgba(255,255,255,0.06)",
              color: "#fff",
              cursor: selectedProjectId ? "pointer" : "not-allowed",
            }}
          >
            Use selected project
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ChatPanel({
  setLastMemoryMatches,
  setMemoryRefreshToken,
  activeMode,
  activeConversationId,
  setActiveConversationId,
  onConversationsChanged,
  currentProjectId,
  setCurrentProjectId, // ✅ NEW (optional) - from App
  conversationRefreshToken,
}) {
  const { user } = useAuth();

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const [uploadingFile, setUploadingFile] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const [fileRefsByMessageId, setFileRefsByMessageId] = useState({});

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const lastSeenMessageIdRef = useRef(0);
  const lastLoadedConversationIdRef = useRef(null);

  const [toastText, setToastText] = useState("");
  const toastTimerRef = useRef(null);
  const showToast = (txt, ms = 2500) => {
    setToastText(txt);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToastText(""), ms);
  };

  const scrollToBottom = (behavior = "auto") => {
    if (messagesEndRef.current) messagesEndRef.current.scrollIntoView({ behavior });
  };

  // ---- Project required modal state ----
  const LAST_PROJECT_KEY = "tamor_last_project_id";
  const [showProjectModal, setShowProjectModal] = useState(false);
  const [projectModalLoading, setProjectModalLoading] = useState(false);
  const [projectModalError, setProjectModalError] = useState("");
  const [projectChoices, setProjectChoices] = useState([]);
  const [pendingAttachProjectId, setPendingAttachProjectId] = useState(null);
  const [newProjectName, setNewProjectName] = useState("");
  const [attachTargetProjectId, setAttachTargetProjectId] = useState(null);

  const loadProjectsForModal = async () => {
    setProjectModalLoading(true);
    setProjectModalError("");
    try {
      const data = await apiFetch(`/projects`);
      const projects = data?.projects || [];
      setProjectChoices(projects);
      return projects;
    } catch (err) {
      setProjectModalError(err?.message || "Failed to load projects.");
      setProjectChoices([]);
      return [];
    } finally {
      setProjectModalLoading(false);
    }
  };

  const openProjectRequiredModal = async () => {
    setShowProjectModal(true);

    const last = Number(localStorage.getItem(LAST_PROJECT_KEY) || "0") || null;
    setPendingAttachProjectId(last);

    const projects = await loadProjectsForModal();

    if (last && !projects.some((p) => p?.id === last)) {
      setPendingAttachProjectId(projects?.[0]?.id ?? null);
    }
  };

  const createProjectFromModal = async () => {
    const name = newProjectName.trim();
    if (!name) return;

    setProjectModalLoading(true);
    setProjectModalError("");
    try {
      const created = await apiFetch(`/projects`, { method: "POST", body: { name } });
      const projId = created?.id;

      const projects = await loadProjectsForModal();
      if (projId) setPendingAttachProjectId(projId);
      else setPendingAttachProjectId(projects?.[0]?.id ?? null);

      setNewProjectName("");
      // Let side panels refresh if they listen to this
      window.dispatchEvent(new Event("tamor:projects-updated"));
    } catch (err) {
      setProjectModalError(err?.message || "Failed to create project.");
    } finally {
      setProjectModalLoading(false);
    }
  };

  const confirmProjectForAttach = () => {
    if (!pendingAttachProjectId) return;

    localStorage.setItem(LAST_PROJECT_KEY, String(pendingAttachProjectId));
    setAttachTargetProjectId(pendingAttachProjectId);

    // If App passed setter, update global project context too
    if (typeof setCurrentProjectId === "function") {
      setCurrentProjectId(pendingAttachProjectId);
    }

    setShowProjectModal(false);

    setTimeout(() => {
      if (fileInputRef.current) fileInputRef.current.click();
    }, 0);
  };

  // ---- Task hydration ----
  const hydrateTasksForConversation = async (convId) => {
    if (!convId) return;

    try {
      const taskData = await apiFetch(`/tasks?limit=200`);
      const tasks = (taskData?.tasks || []).filter((t) => t?.conversation_id === convId);
      if (!tasks.length) return;

      const byUserMsgId = new Map();
      for (const t of tasks) {
        if (t?.message_id != null) byUserMsgId.set(String(t.message_id), t);
      }

      setMessages((prev) => {
        if (!Array.isArray(prev) || prev.length < 2) return prev;

        const next = [...prev];

        for (let i = 0; i < next.length - 1; i++) {
          const m = next[i];
          const a = next[i + 1];

          if (!m || !a) continue;
          if (m.role !== "user") continue;
          if (a.role !== "assistant") continue;

          const t = m?.id != null ? byUserMsgId.get(String(m.id)) : null;
          const t2 = !t && a?.id != null ? byUserMsgId.get(String(a.id)) : null;
          const task = t || t2;
          if (!task) continue;

          const cur = a.detected_task;
          const same = cur?.id === task.id && cur?.status === task.status;
          if (same) continue;

          next[i + 1] = { ...a, detected_task: task };
        }

        return next;
      });
    } catch {
      // ignore
    }
  };

  const loadConversationHistory = async (convId) => {
    if (!convId) return;

    if (lastLoadedConversationIdRef.current !== convId) {
      lastLoadedConversationIdRef.current = convId;
      setMessages([]);
      setFileRefsByMessageId({});
      lastSeenMessageIdRef.current = 0;
    }

    setLoadingHistory(true);
    try {
      const data = await apiFetch(`/conversations/${convId}/messages`);
      const msgs = data.messages || [];

      setMessages(msgs);
      lastSeenMessageIdRef.current = msgs.length ? (msgs[msgs.length - 1]?.id || 0) : 0;

      if (msgs.length) {
        try {
          const refs = await apiFetch(`/messages/file_refs?conversation_id=${convId}`);
          setFileRefsByMessageId(refs.by_message_id || {});
        } catch {
          // ignore
        }
      } else {
        setFileRefsByMessageId({});
      }

      setTimeout(() => hydrateTasksForConversation(convId), 120);
      setTimeout(() => scrollToBottom("auto"), 40);
    } catch (err) {
      console.error("Failed to load conversation:", err);
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    if (!user) return;

    if (!activeConversationId) {
      lastLoadedConversationIdRef.current = null;
      lastSeenMessageIdRef.current = 0;
      setMessages([]);
      setFileRefsByMessageId({});
      setLoadingHistory(false);
      return;
    }

    loadConversationHistory(activeConversationId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeConversationId, conversationRefreshToken, user]);

  useEffect(() => {
    if (!user || !activeConversationId || loadingHistory) return;

    let cancelled = false;

    const poll = async () => {
      try {
        const data = await apiFetch(`/conversations/${activeConversationId}/messages`);
        if (cancelled) return;

        const msgs = data.messages || [];
        const latestId = msgs.length ? msgs[msgs.length - 1].id : 0;

        if (latestId && latestId > (lastSeenMessageIdRef.current || 0)) {
          const prevLast = lastSeenMessageIdRef.current || 0;
          lastSeenMessageIdRef.current = latestId;

          const newOnes = msgs.filter((m) => (m?.id || 0) > prevLast);
          const reminderHit = newOnes.some((m) => String(m?.content || "").startsWith("⏰ Reminder:"));
          if (reminderHit) showToast("🔔 Reminder triggered");

          setMessages((prev) => mergeMessages(prev, msgs));
          setTimeout(() => hydrateTasksForConversation(activeConversationId), 120);
          setTimeout(() => scrollToBottom("smooth"), 40);
        }
      } catch {
        // ignore
      }
    };

    poll();
    const interval = setInterval(poll, 2500);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [user, activeConversationId]);

  useEffect(() => {
    setTimeout(() => scrollToBottom("auto"), 30);
  }, [messages.length]);

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    setSending(true);

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");

    try {
      const data = await apiFetch(`/chat`, {
        method: "POST",
        body: {
          message: trimmed,
          mode: activeMode,
          conversation_id: activeConversationId,
          project_id: currentProjectId,
          tz_name: Intl.DateTimeFormat().resolvedOptions().timeZone,
          tz_offset_minutes: new Date().getTimezoneOffset(),
        },
      });

      const returnedConvId = data?.conversation_id || activeConversationId;

      
      const userMsgId = data?.message_ids?.user;
      if (userMsgId) {
        setMessages((prev) => {
          const next = [...prev];
          for (let i = next.length - 1; i >= 0; i--) {
            if (next[i]?.role === "user" && !next[i]?.id && next[i]?.content === trimmed) {
              next[i] = { ...next[i], id: userMsgId };
              break;
            }
          }
          return next;
        });
      }

      const assistantText = (data?.reply ?? data?.tamor ?? data?.reply_text ?? "").toString();

      const assistantMsg = {
        id: data?.message_ids?.assistant,
        role: "assistant",
        sender: "tamor",
        content: assistantText || "(No reply returned.)",
        detected_task: data?.detected_task || null,
        meta: data?.meta || null,
      };

      setMessages((prev) => appendUnique(prev, assistantMsg));

      if (assistantMsg?.id) {
        lastSeenMessageIdRef.current = Math.max(lastSeenMessageIdRef.current || 0, assistantMsg.id);
      }

      setTimeout(() => hydrateTasksForConversation(returnedConvId), 180);

      if (data?.memory_matches && typeof setLastMemoryMatches === "function") {
        setLastMemoryMatches(data.memory_matches);
      } 

      if (data?.memory_refresh && typeof setMemoryRefreshToken === "function") {
        setMemoryRefreshToken((x) => x + 1);
      }


      if (typeof onConversationsChanged === "function") {
        onConversationsChanged({
          type: "message_sent",
          conversation_id: returnedConvId,
        });
      }

    } catch (err) {
      console.error("Send failed:", err);
      setMessages((prev) =>
        appendUnique(prev, {
          role: "assistant",
          sender: "tamor",
          content: `(Error talking to Tamor: ${err.message || "API error"})`,
        })
      );
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // --------------------------------------------
// NOTE (Phase 3.2):
// ChatPanel temporarily owns file-attachment
// project selection UX. This will be lifted
// into a shared ProjectContext in Phase 3.3.
// --------------------------------------------

  
  const handleAttachClick = async () => {
    setUploadError("");

    if (!currentProjectId) {
      await openProjectRequiredModal();
      return;
    }

    if (fileInputRef.current) fileInputRef.current.click();
  };

  const handleFileSelected = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingFile(true);
    setUploadError("");

    try {
      const form = new FormData();
      form.append("file", file);

      if (activeConversationId) {
        form.append("conversation_id", activeConversationId);
      }

      const projectIdForUpload = currentProjectId || attachTargetProjectId;
      if (!projectIdForUpload) {
        throw new Error("No project selected for upload.");
      }

      const uploaded = await apiFetch(`/projects/${projectIdForUpload}/files`, {
        method: "POST",
        body: form,
        isFormData: true,
      });

      setMessages((prev) =>
        appendUnique(prev, {
          role: "assistant",
          sender: "tamor",
          content: `✅ Attached: ${uploaded?.filename || file.name}`,
        })
      );
    } catch (err) {
      console.error("File upload error:", err);
      setUploadError(err.message || "File upload failed.");
    } finally {
      setUploadingFile(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  if (!user) {
    return (
      <div className="chat-panel">
        <div className="chat-message tamor">
          <div className="chat-bubble">Please log in to use Tamor.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-panel">
      <Toast text={toastText} />

      <ProjectRequiredModal
        open={showProjectModal}
        loading={projectModalLoading}
        error={projectModalError}
        projects={projectChoices}
        selectedProjectId={pendingAttachProjectId}
        setSelectedProjectId={setPendingAttachProjectId}
        newProjectName={newProjectName}
        setNewProjectName={setNewProjectName}
        onCreateProject={createProjectFromModal}
        onConfirm={confirmProjectForAttach}
        onClose={() => setShowProjectModal(false)}
      />

      <div className="messages">
        {loadingHistory && (
          <div className="chat-message tamor">
            <div className="chat-bubble">Loading conversation history…</div>
          </div>
        )}

        {!loadingHistory && messages.length === 0 && (
          <div className="chat-empty-state">{EMPTY_STATE_TEXT}</div>
        )}

        {messages.map((msg, idx) => {
          const isUser = msg.role === "user";
          const fileRefs =
            msg.id && fileRefsByMessageId[msg.id] ? fileRefsByMessageId[msg.id] : [];
          const dt = !isUser ? msg.detected_task : null;

          return (
            <div
              key={msg.id ?? `tmp-${idx}`}
              className={isUser ? "chat-message user" : "chat-message tamor"}
            >
              <div className="chat-bubble">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>

                {!isUser && dt && (
                  <TaskPill
                    task={dt}
                    onAppendMessage={(m) => {
                      setMessages((prev) => appendUnique(prev, { ...m, detected_task: null }));
                      if (m?.id)
                        lastSeenMessageIdRef.current = Math.max(
                          lastSeenMessageIdRef.current || 0,
                          m.id
                        );
                      setTimeout(() => scrollToBottom("smooth"), 40);
                      window.dispatchEvent(new Event("tamor:tasks-updated"));
                    }}
                  />
                )}
              </div>

              {!isUser && fileRefs.length > 0 && (
                <div className="chat-file-badges">
                  {fileRefs.map((file) => (
                    <FileBadgeWithPreview key={file.id || file.file_id} file={file} />
                  ))}
                </div>
              )}
            </div>
          );
        })}

        <div ref={messagesEndRef} />
      </div>

      <div className="input-area">
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Speak to Tamor..."
          rows={3}
          disabled={sending}
        />
        <div className="input-actions">
          <button
            type="button"
            onClick={handleAttachClick}
            disabled={uploadingFile}
            title="Attach a file"
          >
            {uploadingFile ? "Attaching…" : "📎"}
          </button>
          <button onClick={sendMessage} disabled={sending || !input.trim()}>
            {sending ? "Sending…" : "Send"}
          </button>
        </div>

        <input
          type="file"
          ref={fileInputRef}
          style={{ display: "none" }}
          onChange={handleFileSelected}
        />
      </div>

      {uploadError && (
        <div className="chat-status error" style={{ marginTop: "0.25rem" }}>
          {uploadError}
        </div>
      )}
    </div>
  );
}

