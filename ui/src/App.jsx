// src/App.jsx
import "./styles/dark.css";
import { useMemo, useState } from "react";
import { useAuth } from "./context/AuthContext";

import LeftPanel from "./components/LeftPanel/LeftPanel";
import ChatPanel from "./components/ChatPanel/ChatPanel";
import RightPanel from "./components/RightPanel/RightPanel";
import LoginPanel from "./components/LoginPanel";

function getTimeGreeting(d = new Date()) {
  const h = d.getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

function App() {
  const { user, users, loading, login, logout } = useAuth();

  // --------------------------------------------
  // Global UI + mode state
  // --------------------------------------------
  const [activeMode, setActiveMode] = useState("Auto");
  const [mobileView, setMobileView] = useState("chat"); // "chat" | "left" | "right"

  // --------------------------------------------
  // Conversation + project authority (Phase 3.2)
  // --------------------------------------------
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [currentProjectId, setCurrentProjectId] = useState(null);

  // --------------------------------------------
  // Refresh orchestration
  // --------------------------------------------
  const [conversationRefreshToken, setConversationRefreshToken] = useState(0);
  const [memoryRefreshToken, setMemoryRefreshToken] = useState(0);

  // --------------------------------------------
  // Right panel context
  // --------------------------------------------
  const [lastMemoryMatches, setLastMemoryMatches] = useState([]);

  // --------------------------------------------
  // Greeting (local time)
  // --------------------------------------------
  const greeting = useMemo(() => getTimeGreeting(new Date()), []);

  // --------------------------------------------
  // Intent handlers
  // --------------------------------------------

  // Explicit "new chat" intent: clears conversation selection
  const handleNewConversation = () => {
    setActiveConversationId(null);
    setMobileView("chat");
  };

  // ChatPanel reports a server-created or updated conversation
  const handleConversationsChanged = (event) => {
    // event may be undefined (legacy callers)
    setConversationRefreshToken((prev) => prev + 1);

    // Accept server-created conversation ID only if no conversation is selected
    if (
      event?.type === "message_sent" &&
      event.conversation_id &&
      activeConversationId === null
    ) {
      setActiveConversationId(event.conversation_id);
    }
  };

  const handleDeleteConversation = (deletedId) => {
    if (activeConversationId === deletedId) {
      setActiveConversationId(null);
    }
    setConversationRefreshToken((prev) => prev + 1);
  };

  // --------------------------------------------
  // Auth boundary
  // --------------------------------------------
  if (loading) {
    return (
      <div className="app-shell">
        <header className="app-header">
          <div className="app-header-left">
            <span className="app-header-logo">TAMOR</span>
            <span className="app-header-subtitle">
              Context • Insight • Action
            </span>
          </div>
          <div className="app-header-mode">
            <span>Loading…</span>
          </div>
        </header>
        <main className="app-main">
          <div className="auth-panel-wrapper">
            <div className="auth-panel-card">Checking session…</div>
          </div>
        </main>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="app-shell">
        <header className="app-header">
          <div className="app-header-left">
            <span className="app-header-logo">TAMOR</span>
            <span className="app-header-subtitle">
              Context • Insight • Action
            </span>
          </div>
        </header>
        <main className="app-main auth-only">
          <LoginPanel users={users} onLogin={login} />
        </main>
      </div>
    );
  }

  // --------------------------------------------
  // Main application shell
  // --------------------------------------------
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-left">
          <span className="app-header-logo">TAMOR</span>
          <span className="app-header-subtitle">
            Context • Insight • Action
          </span>
        </div>

        <div className="app-header-mode">
          <span>Mode:</span>
          <select
            value={activeMode}
            onChange={(e) => setActiveMode(e.target.value)}
          >
            <option value="Auto">Auto</option>
            <option value="Forge">Forge</option>
            <option value="Scholar">Scholar</option>
            <option value="System">System</option>
            <option value="Anchor">Anchor</option>
            <option value="Path">Path</option>
            <option value="Creative">Creative</option>
          </select>
        </div>

        <div className="app-header-user">
          <span className="user-greeting-label">{greeting},</span>

          {users && users.length > 1 ? (
            <select
              value={user.username}
              onChange={(e) => {
                const selectedUsername = e.target.value;
                if (selectedUsername !== user.username) {
                  login(selectedUsername);
                }
              }}
            >
              {users.map((u) => (
                <option key={u.id} value={u.username}>
                  {u.display_name || u.username}
                </option>
              ))}
            </select>
          ) : (
            <span className="user-greeting">
              {user?.display_name || user?.username || "Guest"}
            </span>
          )}

          <button className="logout-button" onClick={logout}>
            Logout
          </button>
        </div>
      </header>

      <main className={`app-main view-${mobileView}`}>
        {/* Mobile navigation */}
        <div className="mobile-nav">
          <button
            className={mobileView === "chat" ? "active" : ""}
            onClick={() => setMobileView("chat")}
          >
            Chat
          </button>
          <button
            className={mobileView === "left" ? "active" : ""}
            onClick={() => setMobileView("left")}
          >
            Projects
          </button>
          <button
            className={mobileView === "right" ? "active" : ""}
            onClick={() => setMobileView("right")}
          >
            Insights
          </button>
        </div>

        <div className="panel-row">
          <div className="left-panel">
            <LeftPanel
              refreshToken={memoryRefreshToken}
              activeMode={activeMode}
              setActiveMode={setActiveMode}
              activeConversationId={activeConversationId}
              onSelectConversation={setActiveConversationId}
              conversationRefreshToken={conversationRefreshToken}
              onNewConversation={handleNewConversation}
              onDeleteConversation={handleDeleteConversation}
              currentProjectId={currentProjectId}
              setCurrentProjectId={setCurrentProjectId}
            />
          </div>

          <div className="chat-panel-wrapper">
            <ChatPanel
              activeMode={activeMode}
              activeConversationId={activeConversationId}
              onConversationsChanged={handleConversationsChanged}
              conversationRefreshToken={conversationRefreshToken}
              setLastMemoryMatches={setLastMemoryMatches}
              setMemoryRefreshToken={setMemoryRefreshToken}
              currentProjectId={currentProjectId}
              setCurrentProjectId={setCurrentProjectId}
            />
          </div>

          <div className="right-panel">
            <RightPanel
              lastMemoryMatches={lastMemoryMatches}
              activeMode={activeMode}
              currentProjectId={currentProjectId}
              conversationRefreshToken={conversationRefreshToken}
              activeConversationId={activeConversationId}
              onConversationsChanged={handleConversationsChanged}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;

