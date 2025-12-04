import "./ChatPanel.css";
import { useEffect, useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { apiFetch } from "../../api/client";
import { useAuth } from "../../context/AuthContext";

const INITIAL_ASSISTANT_MESSAGE = {
  role: "assistant",
  content: "Shalom, I am Tamor. How can I help you think, build, or study today?",
};

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

  const scrollRef = useRef(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const scrollToBottom = (behavior = "auto") => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior });
    }
  };

  // Load conversation history whenever the active conversation (or refresh token) changes
  useEffect(() => {
    async function loadHistory(conversationId) {
      if (!conversationId) {
        setMessages([INITIAL_ASSISTANT_MESSAGE]);
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
            role,
            content: m.content || "",
          };
        });

        if (mapped.length === 0) {
          setMessages([INITIAL_ASSISTANT_MESSAGE]);
        } else {
          setMessages(mapped);
        }
      } catch (err) {
        console.error("Failed to load conversation history:", err);
        setMessages([
          {
            role: "assistant",
            content: `(Error loading conversation history: ${err.message})`,
          },
        ]);
      } finally {
        setLoadingHistory(false);
      }
    }

    loadHistory(activeConversationId);
  }, [activeConversationId, conversationRefreshToken]);

  useEffect(() => {
    scrollToBottom("smooth");
  }, [messages, activeConversationId]);

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    setSending(true);
    setUploadError("");

    // Optimistically append the user message
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");

    try {
      const data = await apiFetch("/chat", {
        method: "POST",
        body: {
          message: trimmed,
          mode: activeMode,
          conversation_id: activeConversationId,
          // if this is a new conversation, attach it to the current project
          project_id: activeConversationId ? null : currentProjectId || null,
        },
      });

      if (data.conversation_id && data.conversation_id !== activeConversationId) {
        setActiveConversationId(data.conversation_id);
      }

      if (onConversationsChanged) {
        onConversationsChanged();
      }

      const replyText = data.tamor || "(No reply text)";

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: replyText },
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

  // ---- File attach from chat ------------------------------------------------

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
    if (fileInputRef.current && !uploadingFile) {
      fileInputRef.current.click();
    }
  };

  const handleFileSelected = async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    // allow re-selecting same file later
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

      const response = await fetch("/api/files/upload", {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(
          errData.error || `Upload failed with status ${response.status}`
        );
      }

      const data = await response.json();
      const uploaded = data.file || data;

      const fileId = uploaded.id;
      const filename = uploaded.filename || file.name;

      // Markdown link straight to the file
      const injectedText =
        `Here’s the file I just attached to this project: ` +
        `[${filename}](/api/files/${fileId}).\n\n` +
        `You can also summarize or search it from the Files tab.`;

      await apiFetch("/chat/inject", {
        method: "POST",
        body: {
          conversation_id: activeConversationId,
          message: injectedText,
          mode: activeMode,
        },
      });

      if (onConversationsChanged) {
        onConversationsChanged();
      }
    } catch (err) {
      console.error("Chat file upload error:", err);
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

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={
              msg.role === "user" ? "chat-message user" : "chat-message tamor"
            }
          >
            <div className="chat-bubble">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {msg.content}
              </ReactMarkdown>
            </div>
          </div>
        ))}

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

