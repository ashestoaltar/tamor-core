import "./ChatPanel.css";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { apiFetch } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import TaskPill from "./TaskPill";

const INITIAL_ASSISTANT_MESSAGE = {
  role: "assistant",
  content: "Shalom, I am Tamor. How can I help you think, build, or study today?",
};

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

  const [messages, setMessages] = useState([INITIAL_ASSISTANT_MESSAGE]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const [uploadingFile, setUploadingFile] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const [fileRefsByMessageId, setFileRefsByMessageId] = useState({});

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const lastSeenMessageIdRef = useRef(0);

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

  // ---- Task hydration: attach tasks to messages by message_id ----
  const hydrateTasksForConversation = async (convId) => {
    if (!convId) return;
    try {
      const taskData = await apiFetch(`/tasks?conversation_id=${convId}&limit=200`);
      const tasks = taskData?.tasks || [];
      const byMessageId = {};
      for (const t of tasks) {
        if (t?.message_id != null) byMessageId[String(t.message_id)] = t;
      }

      setMessages((prev) =>
        prev.map((m) => {
          if (!m?.id) return m;
          if (m.detected_task) return m;
          const t = byMessageId[String(m.id)];
          if (!t) return m;
          return { ...m, detected_task: t };
        })
      );
    } catch {
      // ignore
    }
  };

  const loadConversationHistory = async (convId) => {
    if (!convId) {
      setMessages([INITIAL_ASSISTANT_MESSAGE]);
      lastSeenMessageIdRef.current = 0;
      return;
    }

    setLoadingHistory(true);
    try {
      const data = await apiFetch(`/conversations/${convId}/messages`);
      const msgs = data.messages || [];

      if (msgs.length === 0) {
        setMessages([INITIAL_ASSISTANT_MESSAGE]);
        lastSeenMessageIdRef.current = 0;
      } else {
        setMessages(msgs);
        lastSeenMessageIdRef.current = msgs[msgs.length - 1]?.id || 0;
      }

      // hydrate file refs (best-effort)
      const ids = (msgs || []).map((m) => m.id).filter((x) => typeof x === "number");
      if (ids.length) {
        try {
          const refs = await apiFetch(`/messages/file_refs?conversation_id=${convId}`);
          setFileRefsByMessageId(refs.by_message_id || {});
        } catch {
          // ignore
        }
      } else {
        setFileRefsByMessageId({});
      }

      // ✅ hydrate tasks shortly after messages render
      setTimeout(() => hydrateTasksForConversation(convId), 80);

      setTimeout(() => scrollToBottom("auto"), 40);
    } catch (err) {
      console.error("Failed to load conversation:", err);
      setMessages([INITIAL_ASSISTANT_MESSAGE]);
      lastSeenMessageIdRef.current = 0;
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

          // canonical replace
          setMessages(msgs.length ? msgs : [INITIAL_ASSISTANT_MESSAGE]);

          // ✅ rehydrate tasks after poll replace
          setTimeout(() => hydrateTasksForConversation(activeConversationId), 80);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, activeConversationId]);

  // Auto-scroll on new message count
  useEffect(() => {
    setTimeout(() => scrollToBottom("auto"), 30);
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

      if (data?.conversation_id && !activeConversationId) {
        setActiveConversationId(data.conversation_id);
      }

      // Your chat_api currently returns: { tamor, detected_task, message_ids }
      // So we append a single assistant message object here:
      const assistantMsg = {
        id: data?.message_ids?.assistant,
        role: "assistant",
        sender: "tamor",
        content: data?.tamor || "",
        detected_task: data?.detected_task || null,
      };

      setMessages((prev) => appendUnique(prev, assistantMsg));

      if (assistantMsg?.id) {
        lastSeenMessageIdRef.current = Math.max(lastSeenMessageIdRef.current || 0, assistantMsg.id);
      }

      // ✅ in case detected_task is missing, hydrate shortly after
      const cid = data?.conversation_id || activeConversationId;
      setTimeout(() => hydrateTasksForConversation(cid), 120);

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

        {messages.map((msg, idx) => {
          const isUser = msg.role === "user";
          const fileRefs = msg.id && fileRefsByMessageId[msg.id] ? fileRefsByMessageId[msg.id] : [];

          const dt = !isUser ? msg.detected_task : null;

          return (
            <div key={msg.id || idx} className={isUser ? "chat-message user" : "chat-message tamor"}>
              <div className="chat-bubble">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>

                {/* TaskPill (primary UI) */}
                {!isUser && dt && (
                  <TaskPill
                    task={dt}
                    onAppendMessage={(m) => {
                      // if TaskPill appends messages, dedupe
                      setMessages((prev) => appendUnique(prev, { ...m, detected_task: null }));
                      if (m?.id) lastSeenMessageIdRef.current = Math.max(lastSeenMessageIdRef.current || 0, m.id);
                      setTimeout(() => scrollToBottom("smooth"), 40);
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

