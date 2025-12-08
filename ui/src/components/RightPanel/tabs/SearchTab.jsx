// src/components/RightPanel/tabs/SearchTab.jsx
import React from "react";
import SemanticSearchPanel from "../components/SemanticSearchPanel.jsx";

function SearchTab({
  currentProjectId,
  activeConversationId,
  activeMode,
  onConversationsChanged,
  onOpenInViewer,
}) {
  if (!currentProjectId) {
    return (
      <div className="rp-tab-content">
        <div className="rp-empty-state">
          <div className="rp-empty-title">No project selected</div>
          <div className="rp-empty-text">
            Choose a project to run semantic search across its files.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rp-tab-content">
      <SemanticSearchPanel
        currentProjectId={currentProjectId}
        activeConversationId={activeConversationId}
        activeMode={activeMode}
        onConversationsChanged={onConversationsChanged}
        onOpenInViewer={onOpenInViewer}
      />
    </div>
  );
}

export default SearchTab;

