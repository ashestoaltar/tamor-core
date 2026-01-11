// src/App.jsx
import "./styles/dark.css";
import { useState } from "react";
import { useAuth } from "./context/AuthContext";

import LeftPanel from "./components/LeftPanel/LeftPanel";
import ChatPanel from "./components/ChatPanel/ChatPanel";
import RightPanel from "./components/RightPanel/RightPanel";
import LoginPanel from "./components/LoginPanel";

function App() {
  const { user, users, loading, login, logout } = useAuth();

  const [lastMemoryMatches, setLastMemoryMatches] = useState([]);
  const [memoryRefreshToken, setMemoryRefreshToken] = useState(0);
  const [activeMode, setActiveMode] = useState("Auto");

  // For tablet/phone: which panel is visible?  "chat" | "left" | "right"
  const [mobileView, setMobileView] = useState("chat");

  // Which conversation is active?
  const [activeConversationId, setActiveConversationId] = useState(null);

  // Which project is currently selected in the workspace?
  const [currentProjectId, setCurrentProjectId] = useState(null);

  // When this increments, side panels reload conversation lists / stats
  const [conversationRefreshToken, setConversationRefreshToken] = useState(0);

  const handleNewConversation = () => {
    setActiveConversationId(null);
    setMobileView("chat");
  };


  const handleConversationsChanged = () => {
    // Called when ChatPanel creates/updates a conversation
    setConversationRefreshToken((prev) => prev + 1);
  };

  const handleDeleteConversation = (deletedId) => {
    // If we just deleted the active conversation, reset chat
    if (activeConversationId === deletedId) {
      setActiveConversationId(null);
    }
    // Also bump refresh token so LeftPanel / RightPanel reload from server
    setConversationRefreshToken((prev) => prev + 1);
  };

  // While we're checking /api/me
  if (loading) {
    return (
      <div className="app-shell">
        <header className="app-header">
          <div className="app-header-left">
            <span className="app-header-logo">TAMOR</span>
            <span className="app-header-subtitle">
              Wholeness • Light • Insight
            </span>
          </div>
          <div className="app-header-mode">
            <span>Loading…</span>
          </div>
          <div className="app-header-user" />
        </header>
        <main className="app-main">
          <div className="auth-panel-wrapper">
            <div className="auth-panel-card">Checking session…</div>
          </div>
        </main>
      </div>
    );
  }

  // If not logged in, show login panel only
  if (!user) {
    return (
      <div className="app-shell">
        <header className="app-header">
          <div className="app-header-left">
            <span className="app-header-logo">TAMOR</span>
            <span className="app-header-subtitle">
              Wholeness • Light • Insight
            </span>
          </div>
        </header>
        <main className="app-main auth-only">
          <LoginPanel users={users} onLogin={login} />
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-left">
          <span className="app-header-logo">TAMOR</span>
          <span className="app-header-subtitle">
            Wholeness • Light • Insight
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
          <span className="user-greeting-label">Shalom,</span>

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
        {/* Mobile / tablet nav (hidden on desktop via CSS) */}
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

        {/* Main panel row (desktop: 3 columns, mobile: 1 at a time) */}
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
              // workspace project selection
              currentProjectId={currentProjectId}
              setCurrentProjectId={setCurrentProjectId}
            />
          </div>

          <div className="chat-panel-wrapper">
            <ChatPanel
              setLastMemoryMatches={setLastMemoryMatches}
              setMemoryRefreshToken={setMemoryRefreshToken}
              activeMode={activeMode}
              activeConversationId={activeConversationId}
              setActiveConversationId={setActiveConversationId}
              onConversationsChanged={handleConversationsChanged}
              conversationRefreshToken={conversationRefreshToken}
              // attach new conversations to the current project
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

