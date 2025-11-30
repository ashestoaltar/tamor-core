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
  const [activeMode, setActiveMode] = useState("Scholar");

  // For tablet/phone: which panel is visible?  "chat" | "left" | "right"
  const [mobileView, setMobileView] = useState("chat");

  // Which conversation is active?
  const [activeConversationId, setActiveConversationId] = useState(null);

  // When this increments, LeftPanel reloads conversation list
  const [conversationRefreshToken, setConversationRefreshToken] = useState(0);

  const handleNewConversation = () => {
    // Clear active conversation so ChatPanel shows a fresh welcome
    setActiveConversationId(null);
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
    // Also bump refresh token so LeftPanel reloads from server
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
            Mode: <span>{activeMode}</span>
          </div>
        </header>
        <main className="app-main">
          <div className="panel-row">
            <div className="loading-screen">Checking session…</div>
          </div>
        </main>
      </div>
    );
  }

  // If no user yet, show login/register UI only
  if (!user) {
    return <LoginPanel />;
  }

  // Once logged in, show the normal Tamor layout
  return (
    <div className="app-shell">
      {/* Header */}
      <header className="app-header">
        <div className="app-header-left">
          <span className="app-header-logo">TAMOR</span>
          <span className="app-header-subtitle">
            Wholeness • Light • Insight
          </span>
        </div>

        <div className="app-header-center">
          Mode: <span>{activeMode}</span>
        </div>

        <div className="app-header-right">
          <span className="user-greeting">Shalom,</span>

          {users && users.length > 0 ? (
            <select
              className="user-select"
              value={user?.username || ""}
              onChange={(e) => {
                const username = e.target.value;
                if (username) {
                  // Backend ignores password now, so empty string is fine
                  login(username, "");
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
            Conversations
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
            />
          </div>

          <div className="right-panel">
            <RightPanel
              lastMemoryMatches={lastMemoryMatches}
              activeMode={activeMode}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;

