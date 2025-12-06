import "./ChatPanel.css";
import { useEffect, useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { apiFetch, API_BASE } from "../../api/client";
import { useAuth } from "../../context/AuthContext";

const INITIAL_ASSISTANT_MESSAGE = {
  role: "assistant",
  content: "Shalom, I am Tamor. How can I help you think, build, or study today?",
};

function getFileEmoji(filename, mimeType) {
  const name = (filename || "").toLowerCase();
  const mime = (mimeType || "").toLowerCase();

  if (name.endsWith(".pdf") || mime === "application/pdf") return "📄";
  if (name.match(/\.(png|jpe?g|gif|webp|svg)$/) || mime.startsWith("image/")) {
    return "🖼️";
  }
  if (name.match(/\.(mp4|mov|mkv|webm)$/) || mime.startsWith("video/")) {
    return "🎬";
  }
  if (name.match(/\.(mp3|wav|flac|m4a)$/) || mime.startsWith("audio/")) {
    return "🎵";
  }
  if (name.match(/\.(xls|xlsx|csv)$/)) return "📊";
  if (name.match(/\.(doc|docx)$/)) return "📝";
  if (name.match(/\.(zip|rar|7z)$/)) return "🗜️";
  if (
    name.match(
      /\.(js|ts|jsx|tsx|py|rb|go|java|c|cpp|cs|php|html|css|json|yml|yaml|lisp)$/
    )
  ) {
    return "💻";
  }

  return "📁";
}

function isTextLikeFile(file) {
  const mime = (file?.mime_type || "").toLowerCase();
  const name = (file?.filename || "").toLowerCase();

  if (mime.startsWith("text/")) return true;

  const textExts = [
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".py",
    ".lisp",
    ".html",
    ".css",
    ".csv",
    ".yml",
    ".yaml",
  ];

  return textExts.some((ext) => name.endsWith(ext));
}

/**
 * One file badge that can:
 *  - Scroll to file in the Files tab (for any file)
 *  - For text/code files, toggle a small inline preview in the chat
 */
function FileBadgeWithPreview({ file }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [text, setText] = useState("");

  const fileId = file.file_id || file.id;
  const textLike = isTextLikeFile(file);

  const handleClick = async () => {
    if (!fileId) return;

    // Non-text files: just scroll to Files tab + highlight
    if (!textLike) {
      window.dispatchEvent(
        new CustomEvent("tamor-scroll-to-file", {
          detail: { fileId },
        })
      );
      return;
    }

    // Text/code files: toggle preview and lazy-load the snippet
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
        className={
          "chat-file-badge" + (loading ? " chat-file-badge-loading" : "")
        }
        onClick={handleClick}
        title={
          textLike
            ? "Click to toggle inline preview (and scroll to file in Files tab)."
            : "Click to jump to this file in the Files tab."
        }
      >
        <span className="chat-file-badge-icon">
          {getFileEmoji(file.filename, file.mime_type)}
        </span>
        <span className="chat-file-badge-name">{file.filename}</span>
      </button>

      {open && textLike && (
        <div className="chat-file-preview">
          {loading && (
            <div className="chat-file-preview-header">Loading preview…</div>
          )}
          {error && (
            <div className="chat-file-preview-header chat-file-preview-error">
              {error}
            </div>
          )}
          {!loading && !error && (
            <>
              <div className="chat-file-preview-header">
                Inline preview (first ~800 characters)
              </div>
              <pre>{text}</pre>
            </>
          )}
        </div>
      )}
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
  conversationRefreshToken,
}) {
  const { user } = useAuth();

  const [messages, setMessages] = useState([INITIAL_ASSISTANT_MESSAGE]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const [uploadingFile, setUploadingFile] = useState(false);
  const [uploadError, setUploadError] = useState("");

  // message.id -> [fileRef, ... ]
  const [fileRefsByMessageId, setFileRefsByMessageId] = useState({});

  const scrollRef = useRef(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const scrollToBottom = (behavior = "auto") => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior });
    }
  };

  // Load conversation history when active conversation changes
  useEffect(() => {
    async function loadHistory(conversationId) {
      if (!conversationId) {
        setMessages([INITIAL_ASSISTANT_MESSAGE]);
        setFileRefsByMessageId({});
        return;
      }

      try {
        setLoadingHistory(true);
        const data = await apiFetch(`/conversations/${conversationId}/messages`);

        const rawMessages = data.messages || data || [];

        const mapped = rawMessages.map((m) => {
          const sender = m.sender || m.role || "assistant";
          const role = sender === "user" ? "user" : "assistant";
          return {
            id: m.id,
            role,
            sender,
            content: m.content || "",
            created_at: m.created_at || null,
          };
        });

        if (mapped.length === 0) {
          setMessages([INITIAL_ASSISTANT_MESSAGE]);
          setFileRefsByMessageId({});
        } else {
          setMessages(mapped);
          // Clear file refs cache; they’ll be lazily reloaded
          setFileRefsByMessageId({});
        }
      } catch (err) {
        console.error("Failed to load conversation history:", err);
        setMessages([
          {
            role: "assistant",
            content: `(Error loading conversation history: ${err.message})`,
          },
        ]);
        setFileRefsByMessageId({});
      } finally {
        setLoadingHistory(false);
      }
    }

    loadHistory(activeConversationId);
  }, [activeConversationId, conversationRefreshToken]);

  // Auto-scroll when messages change
  useEffect(() => {
    scrollToBottom("smooth");
  }, [messages]);

  // Lazy load file refs for assistant messages
  useEffect(() => {
    let cancelled = false;

    async function loadMissingFileRefs() {
      const idsToFetch = messages
        .filter((m) => m.id && m.role === "assistant")
        .map((m) => m.id)
        .filter((id) => !(id in fileRefsByMessageId));

      if (idsToFetch.length === 0) return;

      const newRefs = {};

      for (const msgId of idsToFetch) {
        try {
          const data = await apiFetch(`/messages/${msgId}/file-refs`);
          if (cancelled) return;
          newRefs[msgId] = data.files || [];
        } catch (err) {
          console.error("Failed to load file refs for message", msgId, err);
          if (cancelled) return;
          newRefs[msgId] = [];
        }
      }

      if (!cancelled && Object.keys(newRefs).length > 0) {
        setFileRefsByMessageId((prev) => ({
          ...prev,
          ...newRefs,
        }));
      }
    }

    loadMissingFileRefs();

    return () => {
      cancelled = true;
    };
  }, [messages, fileRefsByMessageId]);

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    setSending(true);
    setUploadError("");

    // Optimistically append the user message (no id yet)
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");

    try {
      const data = await apiFetch("/chat", {
        method: "POST",
        body: {
          message: trimmed,
          mode: activeMode,
          conversation_id: activeConversationId,
          project_id: activeConversationId ? null : currentProjectId || null,
        },
      });

      // If backend created a new conversation, adopt it
      if (data.conversation_id && data.conversation_id !== activeConversationId) {
        setActiveConversationId(data.conversation_id);
      }

      if (onConversationsChanged) {
        onConversationsChanged();
      }

      const replyText = data.tamor || "(No reply text)";

      const assistantMessageId =
        data.message_ids && data.message_ids.assistant
          ? data.message_ids.assistant
          : undefined;
      const userMessageId =
        data.message_ids && data.message_ids.user
          ? data.message_ids.user
          : undefined;

      // Patch the last user message with its DB id if we got one
      if (userMessageId) {
        setMessages((prev) => {
          const copy = [...prev];
          const idx = copy.length - 1;
          if (idx >= 0 && copy[idx].role === "user" && !copy[idx].id) {
            copy[idx] = { ...copy[idx], id: userMessageId };
          }
          return copy;
        });
      }

      // Append assistant message with id for file refs
      setMessages((prev) => [
        ...prev,
        {
          id: assistantMessageId,
          role: "assistant",
          sender: "assistant",
          content: replyText,
        },
      ]);

      if (data.memory_matches) {
        setLastMemoryMatches(data.memory_matches);
        setMemoryRefreshToken((prev) => prev + 1);
      }
    } catch (err) {
      console.error("Chat error:", err);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `(Error talking to Tamor: ${err.message})`,
        },
      ]);
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

  // ---- File attach from chat ----------------------------------------------

  const handleAttachClick = () => {
    setUploadError("");
    if (!currentProjectId) {
      setUploadError("Select a project before attaching files.");
      return;
    }
    if (!activeConversationId) {
      setUploadError("Start or select a conversation, then attach files.");
      return;
    }

    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileSelected = async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    // allow picking the same file again later
    e.target.value = "";

    if (!currentProjectId || !activeConversationId) {
      setUploadError("Select a project and conversation first.");
      return;
    }

    setUploadingFile(true);
    setUploadError("");

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("project_id", String(currentProjectId));
      formData.append("conversation_id", String(activeConversationId));

      const uploadResponse = await fetch(`${API_BASE}/files/upload`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      if (!uploadResponse.ok) {
        const errData = await uploadResponse.json().catch(() => ({}));
        throw new Error(
          errData.error || `Upload failed with status ${uploadResponse.status}`
        );
      }

      const uploadData = await uploadResponse.json();
      const uploaded = uploadData.file || uploadData;

      const fileId = uploaded.id;
      const filename = uploaded.filename || file.name;

      // Inject small assistant message referencing the file
      const injectedText =
        `I’ve attached the file **${filename}** to this project and conversation.\n\n` +
        `You can also work with it from the Files tab.`;

      const injectResp = await apiFetch("/chat/inject", {
        method: "POST",
        body: {
          conversation_id: activeConversationId,
          message: injectedText,
          mode: activeMode,
        },
      });

      const injectedMessage = injectResp.message || {};
      const injectedMessageId = injectedMessage.id;

      // Attach file to that message so badges + previews show up
      if (injectedMessageId && fileId) {
        try {
          await apiFetch(`/messages/${injectedMessageId}/attach-file`, {
            method: "POST",
            body: { file_id: fileId },
          });
        } catch (err) {
          console.error("Failed to attach file to message:", err);
        }
      }

      if (onConversationsChanged) {
        onConversationsChanged();
      }
    } catch (err) {
      console.error("File upload error:", err);
      setUploadError(err.message || "File upload failed.");
    } finally {
      setUploadingFile(false);
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
      <div className="messages" ref={scrollRef}>
        {loadingHistory && (
          <div className="chat-message tamor">
            <div className="chat-bubble">Loading conversation history…</div>
          </div>
        )}

        {messages.map((msg, idx) => {
          const isUser = msg.role === "user";
          const fileRefs =
            msg.id && fileRefsByMessageId[msg.id]
              ? fileRefsByMessageId[msg.id]
              : [];

          return (
            <div
              key={msg.id || idx}
              className={isUser ? "chat-message user" : "chat-message tamor"}
            >
              <div className="chat-bubble">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.content}
                </ReactMarkdown>
              </div>

              {/* File badges + inline previews under assistant messages */}
              {!isUser && fileRefs.length > 0 && (
                <div className="chat-file-badges">
                  {fileRefs.map((file) => (
                    <FileBadgeWithPreview
                      key={file.id || file.file_id}
                      file={file}
                    />
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
        />
        <div className="input-actions">
          <button
            type="button"
            onClick={handleAttachClick}
            disabled={uploadingFile}
            title="Attach a file to this project & conversation"
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

