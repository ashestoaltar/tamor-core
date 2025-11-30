import "./LeftPanel.css";
import ProjectsPanel from "./ProjectsPanel";

export default function LeftPanel({
  refreshToken,
  activeMode,
  setActiveMode,
  activeConversationId,
  onSelectConversation,
  conversationRefreshToken,
  onNewConversation,
  onDeleteConversation,
}) {
  const modes = ["Scholar", "Forge", "Path", "Anchor", "Creative", "System"];

  return (
    <div className="left-panel">
      {/* Identity / logo */}
      <div className="identity">
        <h1 className="logo">TAMOR</h1>
        <div className="subtitle">Wholeness • Light • Insight</div>
      </div>

      {/* PROJECTS + CONVERSATIONS SECTION – middle, scrolls */}
      <div className="section memory-section">
        <ProjectsPanel
          activeConversationId={activeConversationId}
          onSelectConversation={onSelectConversation}
          refreshToken={conversationRefreshToken}
          onNewConversation={onNewConversation}
          onDeleteConversation={onDeleteConversation}
        />
      </div>

      {/* MODES SECTION – bottom */}
      <div className="section mode-section">
        <h2>Modes</h2>
        <ul className="mode-list">
          {modes.map((mode) => (
            <li
              key={mode}
              className={mode === activeMode ? "mode active" : "mode"}
              onClick={() => setActiveMode(mode)}
            >
              {mode}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

