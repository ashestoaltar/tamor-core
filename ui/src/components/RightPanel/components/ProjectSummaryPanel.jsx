// src/components/RightPanel/components/ProjectSummaryPanel.jsx
import React from "react";

function ProjectSummaryPanel({
  projectSummaryPrompt,
  setProjectSummaryPrompt,
  projectSummaryLoading,
  projectSummaryError,
  projectSummaryText,
  activeConversationId,
  onSummarize,
  onSendSummaryToChat,
}) {
  return (
    <div className="rp-section">
      <div className="rp-section-header">
        <h3 className="rp-section-title">Project summary</h3>
      </div>
      <div className="rp-section-body">
        <label className="rp-label">
          Custom instructions for this summary (optional)
        </label>
        <textarea
          className="rp-notes-textarea rp-small"
          value={projectSummaryPrompt}
          onChange={(e) => setProjectSummaryPrompt(e.target.value)}
        />
        <div className="rp-section-footer">
          <button
            className="rp-button"
            type="button"
            onClick={onSummarize}
            disabled={projectSummaryLoading}
          >
            {projectSummaryLoading ? "Summarizing…" : "Summarize project"}
          </button>
        </div>
        {projectSummaryError && (
          <div className="rp-error">{projectSummaryError}</div>
        )}
        {projectSummaryText && (
          <div className="rp-summary-preview">
            <pre>{projectSummaryText}</pre>
            {activeConversationId && (
              <button
                className="rp-button subtle"
                type="button"
                onClick={onSendSummaryToChat}
              >
                Send summary to chat
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ProjectSummaryPanel;
