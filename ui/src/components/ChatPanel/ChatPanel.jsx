import "./ChatPanel.css";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { apiFetch } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import TaskPill from "./TaskPill";

const EMPTY_STATE_TEXT =
  "My name is Tamor. How can I help you today?";

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

  const textExts = [".txt", ".md", ".markdown", ".json", ".js", ".ts", ".jsx", ".tsx", ".py", ".lisp", ".html", ".css", ".csv", ".yml", ".yaml"];
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
        const snippet = fullText.length > maxChars ? fullText.slice(0, maxChars) + "\n\n[... truncated ...]" : fullText;
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
        title={textLike ? "Click to toggle inline preview (and scroll to file in Files tab)." : "Click to jump to this file in the Files tab."}
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

// Merge server messages into client state without losing client-only fields (like detected_task)
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

  // ✅ Preserve optimistic/pending messages with no id (last few only)
  const pending = (prev || []).filter((m) => m?.id == null && m?.content);
  for (const p of pending.slice(-4)) {
    const already = out.some(
      (m) => m?.id == null && m?.role === p.role && m?.content === p.content
    );
    if (!already) out.push(p);
  }

  return out;
}


export default function ChatPanel({
  setLastMemoryMatches,
  setMemoryRefreshToken,
  activeMode,
  activeConversationId,
  setActiveConversationId,
  onConversationsChanged,
  currentProjectId,
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
  const lastLoadedConversationIdRef = useRef(null); // ← NEW REF

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

  // ---- Task hydration: task.message_id is the USER message id; attach pill to the NEXT assistant message
  const hydrateTasksForConversation = async (convId) => {
    if (!convId) return;

    try {
      // Backend supports /tasks?limit=... (no conversation_id filter); filter client-side
      const taskData = await apiFetch(`/tasks?limit=200`);
      const tasks = (taskData?.tasks || []).filter((t) => t?.conversation_id === convId);

      if (!tasks.length) return;

      // Map by user message_id
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

          // Fallback: sometimes tasks might be stored against assistant id (older rows)
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

  // PATCHED loadConversationHistory
  const loadConversationHistory = async (convId) => {
    // 🔒 Never wipe just because convId is temporarily missing
    if (!convId) return;

    // ✅ If the user actually switched conversations, clear the UI immediately
    if (lastLoadedConversationIdRef.current !== convId) {
      lastLoadedConversationIdRef.current = convId;
      setMessages([]);                 // show empty state if no messages
      setFileRefsByMessageId({});
      lastSeenMessageIdRef.current = 0;
    }

    setLoadingHistory(true);
    try {
      const data = await apiFetch(`/conversations/${convId}/messages`);
      const msgs = data.messages || [];

      // ✅ Server tells us exactly what messages exist
      setMessages(msgs);
      lastSeenMessageIdRef.current = msgs.length ? (msgs[msgs.length - 1]?.id || 0) : 0;

      // file refs…
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
      // 🔒 Keep current UI on transient failure (don’t wipe)
    } finally {
      setLoadingHistory(false);
    }
  };

  // Load history when conversation changes
  useEffect(() => {
    if (!user) return;
    loadConversationHistory(activeConversationId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeConversationId, conversationRefreshToken, user]);

  // Poll for executor-inserted messages
  useEffect(() => {
    if (!user || !activeConversationId) return;

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

          // ✅ merge (don’t wipe detected_task)
          setMessages((prev) => mergeMessages(prev, msgs));

          // ✅ rehydrate tasks after poll merge
          setTimeout(() => hydrateTasksForConversation(activeConversationId), 120);

          setTimeout(() => scrollToBottom("smooth"), 40);
        }
      } catch {
        // ignore transient failures
      }
    };

    poll();
    const interval = setInterval(poll, 2500);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    
  }, [user, activeConversationId]);

  // Auto-scroll on new message count
  useEffect(() => {
    setTimeout(() => scrollToBottom("auto"), 30);
    
  }, [messages.length]);

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    setSending(true);

    // optimistic user message
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
        },
      });

      const returnedConvId = data?.conversation_id || activeConversationId;

      if (data?.conversation_id && !activeConversationId) {
        setActiveConversationId(data.conversation_id);
      }

      // Update the last optimistic user message with the real server id (critical for task linking)
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

      // Append assistant message
      const assistantText =
        (data?.reply ?? data?.tamor ?? data?.reply_text ?? "").toString();

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

      // ✅ hydrate tasks (will attach needs_confirmation pill to the assistant message)
      setTimeout(() => hydrateTasksForConversation(returnedConvId), 180);

      if (data?.memory_matches && setLastMemoryMatches) setLastMemoryMatches(data.memory_matches);
      if (data?.memory_refresh && setMemoryRefreshToken) setMemoryRefreshToken((x) => x + 1);

      onConversationsChanged?.();
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

  const handleAttachClick = () => {
    setUploadError("");
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

      const uploaded = await apiFetch(
        `/files/upload?project_id=${currentProjectId || ""}&conversation_id=${activeConversationId || ""}`,
        { method: "POST", body: form, isFormData: true }
      );

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
          const fileRefs = msg.id && fileRefsByMessageId[msg.id] ? fileRefsByMessageId[msg.id] : [];
          const dt = !isUser ? msg.detected_task : null;

          return (
            <div key={msg.id ?? `tmp-${idx}`} className={isUser ? "chat-message user" : "chat-message tamor"}>
              <div className="chat-bubble">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>

                {/* TaskPill (primary UI) */}
                {!isUser && dt && (
                  <TaskPill
                    task={dt}
                    onAppendMessage={(m) => {
                      setMessages((prev) => appendUnique(prev, { ...m, detected_task: null }));
                      if (m?.id) lastSeenMessageIdRef.current = Math.max(lastSeenMessageIdRef.current || 0, m.id);
                      setTimeout(() => scrollToBottom("smooth"), 40);
                      // refresh task statuses across panels
                      window.dispatchEvent(new Event("tamor:tasks-updated"));
                    }}
                  />
                )}
              </div>

              {/* File badges */}
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
          <button type="button" onClick={handleAttachClick} disabled={uploadingFile} title="Attach a file">
            {uploadingFile ? "Attaching…" : "📎"}
          </button>
          <button onClick={sendMessage} disabled={sending || !input.trim()}>
            {sending ? "Sending…" : "Send"}
          </button>
        </div>

        <input type="file" ref={fileInputRef} style={{ display: "none" }} onChange={handleFileSelected} />
      </div>

      {uploadError && (
        <div className="chat-status error" style={{ marginTop: "0.25rem" }}>
          {uploadError}
        </div>
      )}
    </div>
  );
}
