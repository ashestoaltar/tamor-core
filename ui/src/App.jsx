// src/App.jsx
import "./styles/dark.css";
import { useMemo, useState } from "react";
import { useAuth } from "./context/AuthContext";
import { useBreakpoint } from "./hooks/useBreakpoint";
import { useFocusMode } from "./contexts/FocusModeContext";
import { useDevMode } from "./context/DevModeContext";

import LeftPanel from "./components/LeftPanel/LeftPanel";
import ChatPanel from "./components/ChatPanel/ChatPanel";
import RightPanel from "./components/RightPanel/RightPanel";
import LoginPanel from "./components/LoginPanel";
import Drawer from "./components/Drawer/Drawer";
import MobileNav from "./components/MobileNav/MobileNav";
import Settings from "./components/Settings/Settings";
import FocusMode from "./components/FocusMode/FocusMode";
import StatusIndicator from "./components/StatusIndicator/StatusIndicator";

function getTimeGreeting(d = new Date()) {
  const h = d.getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

function App() {
  const { user, users, loading, login, logout } = useAuth();
  const { isMobile, isTablet, isDesktop } = useBreakpoint();
  const { isFocusMode, toggleFocusMode } = useFocusMode();
  const { devMode } = useDevMode();

  // --------------------------------------------
  // Global UI + mode state
  // --------------------------------------------
  const [activeMode, setActiveMode] = useState("Auto");
  const [mobileView, setMobileView] = useState("chat"); // "chat" | "projects" | "settings"

  // --------------------------------------------
  // Drawer state (mobile)
  // --------------------------------------------
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(false);
  const [rightDrawerOpen, setRightDrawerOpen] = useState(false);
  const [rightDrawerContent, setRightDrawerContent] = useState("panels"); // "panels" | "settings"

  // --------------------------------------------
  // Tablet sidebar state
  // --------------------------------------------
  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);

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
    setLeftDrawerOpen(false);
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

  // Mobile navigation handler
  const handleMobileNav = (view) => {
    setMobileView(view);

    if (view === "projects") {
      setLeftDrawerOpen(true);
      setRightDrawerOpen(false);
    } else if (view === "settings") {
      setRightDrawerContent("settings");
      setRightDrawerOpen(true);
      setLeftDrawerOpen(false);
    } else {
      // "chat" - close all drawers
      setLeftDrawerOpen(false);
      setRightDrawerOpen(false);
    }
  };

  // Open right panel drawer (for accessing tabs on mobile)
  const handleOpenRightPanel = () => {
    setRightDrawerContent("panels");
    setRightDrawerOpen(true);
  };

  // When selecting a conversation on mobile, close drawer and go to chat
  const handleSelectConversationMobile = (conversationId) => {
    setActiveConversationId(conversationId);
    setLeftDrawerOpen(false);
    setMobileView("chat");
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
  // Focus Mode: full-screen overlay when active
  // --------------------------------------------
  if (isFocusMode) {
    return (
      <FocusMode
        projectName={currentProjectId ? `Project ${currentProjectId}` : null}
        activeConversationId={activeConversationId}
        currentProjectId={currentProjectId}
        activeMode={activeMode}
        onConversationCreated={(newId) => {
          setActiveConversationId(newId);
          setConversationRefreshToken(prev => prev + 1);
        }}
      />
    );
  }

  // --------------------------------------------
  // Shared panel props
  // --------------------------------------------
  const leftPanelProps = {
    refreshToken: memoryRefreshToken,
    activeMode: activeMode,
    setActiveMode: setActiveMode,
    activeConversationId: activeConversationId,
    onSelectConversation: isMobile ? handleSelectConversationMobile : setActiveConversationId,
    conversationRefreshToken: conversationRefreshToken,
    onNewConversation: handleNewConversation,
    onDeleteConversation: handleDeleteConversation,
    currentProjectId: currentProjectId,
    setCurrentProjectId: setCurrentProjectId,
  };

  const chatPanelProps = {
    activeMode: activeMode,
    activeConversationId: activeConversationId,
    onConversationsChanged: handleConversationsChanged,
    conversationRefreshToken: conversationRefreshToken,
    setLastMemoryMatches: setLastMemoryMatches,
    setMemoryRefreshToken: setMemoryRefreshToken,
    currentProjectId: currentProjectId,
    setCurrentProjectId: setCurrentProjectId,
    // Mobile-specific: button to open right panel
    onOpenRightPanel: isMobile ? handleOpenRightPanel : undefined,
  };

  const rightPanelProps = {
    activeMode: activeMode,
    currentProjectId: currentProjectId,
    activeConversationId: activeConversationId,
    onConversationsChanged: handleConversationsChanged,
  };

  // --------------------------------------------
  // Main application shell
  // --------------------------------------------
  return (
    <div className={`app-shell ${isMobile ? "is-mobile" : ""} ${isTablet ? "is-tablet" : ""}`}>
      <header className="app-header">
        <div className="app-header-left">
          {/* Tablet: hamburger menu for left panel */}
          {isTablet && (
            <button
              className="app-header-menu-btn"
              onClick={() => setLeftPanelCollapsed(!leftPanelCollapsed)}
              aria-label="Toggle projects panel"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 12h18M3 6h18M3 18h18" />
              </svg>
            </button>
          )}

          <span className="app-header-logo">TAMOR</span>
          {!isMobile && (
            <span className="app-header-subtitle">
              Context • Insight • Action
            </span>
          )}
        </div>

        {/* Mode selector - hidden on mobile (too cramped) */}
        {!isMobile && (
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
        )}

        {/* Focus Mode toggle */}
        <button
          className="focus-mode-toggle"
          onClick={toggleFocusMode}
          title="Enter Focus Mode"
        >
          ◉
        </button>

        <div className="app-header-user">
          {!isMobile && (
            <span className="user-greeting-label">{greeting},</span>
          )}

          {!isMobile && users && users.length > 1 ? (
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
          ) : !isMobile ? (
            <span className="user-greeting">
              {user?.display_name || user?.username || "Guest"}
            </span>
          ) : null}

          {/* Tablet: right panel toggle */}
          {isTablet && (
            <button
              className="app-header-menu-btn"
              onClick={() => setRightPanelCollapsed(!rightPanelCollapsed)}
              aria-label="Toggle insights panel"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 16v-4M12 8h.01" />
              </svg>
            </button>
          )}

          {!isMobile && (
            <div className="status-indicator-wrapper">
              <StatusIndicator showExpanded={devMode} />
            </div>
          )}

          {!isMobile && (
            <button className="logout-button" onClick={logout}>
              Logout
            </button>
          )}
        </div>
      </header>

      <main className="app-main">
        <div className="panel-row">
          {/* Left Panel - Desktop always, Tablet collapsible */}
          {isDesktop && (
            <div className="left-panel">
              <LeftPanel {...leftPanelProps} />
            </div>
          )}

          {isTablet && !leftPanelCollapsed && (
            <div className="left-panel left-panel-tablet">
              <LeftPanel {...leftPanelProps} />
            </div>
          )}

          {/* Chat Panel - Always visible */}
          <div className={`chat-panel-wrapper ${isMobile ? "chat-panel-mobile" : ""}`}>
            <ChatPanel {...chatPanelProps} />
          </div>

          {/* Right Panel - Desktop always, Tablet collapsible */}
          {isDesktop && (
            <div className="right-panel">
              <RightPanel {...rightPanelProps} />
            </div>
          )}

          {isTablet && !rightPanelCollapsed && (
            <div className="right-panel right-panel-tablet">
              <RightPanel {...rightPanelProps} />
            </div>
          )}
        </div>

        {/* Mobile: Drawers */}
        {isMobile && (
          <>
            <Drawer
              isOpen={leftDrawerOpen}
              onClose={() => {
                setLeftDrawerOpen(false);
                setMobileView("chat");
              }}
              side="left"
              title="Projects"
            >
              <LeftPanel {...leftPanelProps} />
            </Drawer>

            <Drawer
              isOpen={rightDrawerOpen}
              onClose={() => {
                setRightDrawerOpen(false);
                setMobileView("chat");
              }}
              side="right"
              title={rightDrawerContent === "settings" ? "Settings" : "Tools"}
            >
              {rightDrawerContent === "settings" ? (
                <Settings />
              ) : (
                <RightPanel {...rightPanelProps} />
              )}
            </Drawer>
          </>
        )}
      </main>

      {/* Mobile: Bottom Navigation */}
      {isMobile && (
        <MobileNav
          activeView={mobileView}
          onNavigate={handleMobileNav}
        />
      )}
    </div>
  );
}

export default App;
