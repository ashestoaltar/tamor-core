import "./ChatPanel.css";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { apiFetch } from "../../api/client";
import { useAuth } from "../../context/AuthContext";

const INITIAL_ASSISTANT_MESSAGE = {
  role: "assistant",
  content:
    "Shalom, I am Tamor. How can I help you think, build, or study today?",
};

export default function ChatPanel({
  setLastMemoryMatches,
  setMemoryRefreshToken,
  activeMode,
  activeConversationId,
  setActiveConversationId,
  onConversationsChanged,
}) {
  const { user } = useAuth();

  const [messages, setMessages] = useState([INITIAL_ASSISTANT_MESSAGE]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Load conversation history when activeConversationId changes
  useEffect(() => {
    async function loadHistory(conversationId) {
      if (!conversationId) {
        // No conversation selected yet: show a fresh welcome message
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
          INITIAL_ASSISTANT_MESSAGE,
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
  }, [activeConversationId]);

  const sendMessage = async () => {
    if (!input.trim() || sending) return;
    const userText = input.trim();
    setInput("");

    // Optimistically add user message
    setMessages((prev) => [...prev, { role: "user", content: userText }]);
    setSending(true);

    try {
      const data = await apiFetch("/chat", {
        method: "POST",
        body: {
          message: userText,
          mode: activeMode || "Scholar",
          conversation_id: activeConversationId, // may be null for new threads
        },
      });

      // Update active conversation id if backend created a new one
      if (
        data.conversation_id &&
        data.conversation_id !== activeConversationId
      ) {
        setActiveConversationId(data.conversation_id);
      }

      // Notify app that conversations changed (new or updated)
      if (onConversationsChanged) {
        onConversationsChanged();
      }

      const replyText = data.tamor || "(No reply text)";

      // Append assistant reply
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: replyText },
      ]);

      // Update right-panel memory matches
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

  if (!user) {
    return (
      <div className="chat-panel">
        <div className="messages">
          <div className="message assistant">
            Please log in to start chatting with Tamor.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-panel">
      <div className="messages">
        {loadingHistory && (
          <div className="message assistant">
            Loading conversation history…
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={
              msg.role === "user" ? "message user" : "message assistant"
            }
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {msg.content}
            </ReactMarkdown>
          </div>
        ))}
      </div>

      <div className="input-area">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Speak to Tamor..."
          rows={1}
        />
        <button onClick={sendMessage} disabled={sending || !input.trim()}>
          {sending ? "Sending…" : "Send"}
        </button>
      </div>
    </div>
  );
}

