// src/components/RightPanel/components/FileList.jsx
import React, { useState } from "react";
import { API_BASE } from "../../../api/client";

function FileList({
  files,
  filesLoading,
  filesError,
  fileSummaries,
  fileSummaryLoadingId,
  fileSummaryErrorId,
  structureFileId,
  structureLoading,
  activeConversationId,
  onSummarize,
  onSelectStructure,
  onSendSummaryToChat,
  onFileAction,
  fileActionLoading,
  fileActionResults,
}) {
  const [expandedActionsFileId, setExpandedActionsFileId] = useState(null);
  const [selectedRewriteMode, setSelectedRewriteMode] = useState("improve");

  const rewriteModes = [
    { value: "simplify", label: "Simplify" },
    { value: "expand", label: "Expand" },
    { value: "improve", label: "Improve" },
    { value: "restructure", label: "Restructure" },
    { value: "technical", label: "Technical" },
    { value: "executive", label: "Executive" },
  ];

  const handleToggleActions = (fileId) => {
    setExpandedActionsFileId(
      expandedActionsFileId === fileId ? null : fileId
    );
  };
  return (
    <div className="rp-section">
      <div className="rp-section-header">
        <h3 className="rp-section-title">Project files</h3>
        {filesLoading && (
          <span className="rp-tag rp-tag-muted">Loading…</span>
        )}
      </div>
      {filesError && (
        <div className="rp-section-body rp-error">{filesError}</div>
      )}
      {!filesLoading && files.length === 0 && (
        <div className="rp-section-body rp-small-text">
          No files uploaded yet. Try dragging a file into the chat
          area or using the file upload button.
        </div>
      )}
      {files.length > 0 && (
        <div className="rp-section-body rp-file-list">
          {files.map((f) => (
            <div key={f.id} className="rp-file-row">
              <div className="rp-file-main">
                <div className="rp-file-title">{f.filename}</div>
                <div className="rp-file-meta">
                  {f.mime_type && (
                    <span className="rp-tag rp-tag-muted">
                      {f.mime_type}
                    </span>
                  )}
                  {typeof f.size_bytes === "number" && (
                    <span className="rp-tag rp-tag-muted">
                      {(f.size_bytes / 1024).toFixed(1)} KB
                    </span>
                  )}
                  {f.has_text && (
                    <span className="rp-tag rp-tag-positive">
                      text indexed
                    </span>
                  )}
                  {f.parser && (
                    <span className="rp-tag rp-tag-muted">
                      {f.parser}
                    </span>
                  )}
                  {Array.isArray(f.warnings) &&
                    f.warnings.map((w, idx) => (
                      <span
                        key={idx}
                        className="rp-tag rp-tag-warning"
                      >
                        {w}
                      </span>
                    ))}
                </div>
              </div>
              <div className="rp-file-actions">
                <button
                  className="rp-button subtle"
                  type="button"
                  onClick={() => onSummarize(f.id)}
                  disabled={fileSummaryLoadingId === f.id}
                >
                  {fileSummaryLoadingId === f.id
                    ? "Summarizing…"
                    : "Summarize"}
                </button>
                <button
                  className="rp-button subtle"
                  type="button"
                  onClick={() => onSelectStructure(f.id)}
                  disabled={structureLoading && structureFileId === f.id}
                >
                  Structure
                </button>
                {onFileAction && (
                  <button
                    className={`rp-button ${
                      expandedActionsFileId === f.id ? "primary" : "subtle"
                    }`}
                    type="button"
                    onClick={() => handleToggleActions(f.id)}
                  >
                    Actions
                  </button>
                )}
                <a
                  className="rp-button subtle"
                  href={`${API_BASE}/files/${f.id}/download`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Open
                </a>
              </div>
              {/* File Actions Panel */}
              {expandedActionsFileId === f.id && onFileAction && (
                <div className="rp-file-actions-panel">
                  <div className="rp-file-actions-row">
                    <div className="rp-file-action-group">
                      <span className="rp-file-action-label">Rewrite:</span>
                      <select
                        className="rp-select"
                        value={selectedRewriteMode}
                        onChange={(e) => setSelectedRewriteMode(e.target.value)}
                      >
                        {rewriteModes.map((m) => (
                          <option key={m.value} value={m.value}>
                            {m.label}
                          </option>
                        ))}
                      </select>
                      <button
                        className="rp-button subtle"
                        onClick={() =>
                          onFileAction(f.id, "rewrite", {
                            mode: selectedRewriteMode,
                          })
                        }
                        disabled={fileActionLoading === f.id}
                      >
                        {fileActionLoading === f.id ? "..." : "Go"}
                      </button>
                    </div>
                    <button
                      className="rp-button subtle"
                      onClick={() => onFileAction(f.id, "generate-spec")}
                      disabled={fileActionLoading === f.id}
                    >
                      Generate Spec
                    </button>
                    <button
                      className="rp-button subtle"
                      onClick={() => onFileAction(f.id, "extract-parameters")}
                      disabled={fileActionLoading === f.id}
                    >
                      Extract Params
                    </button>
                  </div>
                  {fileActionLoading === f.id && (
                    <div className="rp-info-text">Processing...</div>
                  )}
                </div>
              )}
              {/* File Action Results */}
              {fileActionResults?.[f.id] && (
                <div className="rp-file-action-result">
                  <div className="rp-file-action-result-header">
                    <span className="rp-tag rp-tag-muted">
                      {fileActionResults[f.id].action}
                    </span>
                    <button
                      className="rp-button-compact"
                      onClick={() => {
                        navigator.clipboard.writeText(
                          fileActionResults[f.id].result
                        );
                      }}
                    >
                      Copy
                    </button>
                  </div>
                  <pre className="rp-file-action-result-content">
                    {fileActionResults[f.id].result}
                  </pre>
                </div>
              )}
              {fileSummaries[f.id] && (
                <div className="rp-file-summary">
                  <pre>{fileSummaries[f.id]}</pre>
                  {activeConversationId && (
                    <button
                      className="rp-button subtle"
                      type="button"
                      onClick={() => onSendSummaryToChat(f.id)}
                    >
                      Send summary to chat
                    </button>
                  )}
                </div>
              )}
              {fileSummaryErrorId === f.id && (
                <div className="rp-file-summary rp-error">
                  Error summarizing this file.
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default FileList;
