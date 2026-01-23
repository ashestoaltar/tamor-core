// src/components/RightPanel/tabs/ReasoningTab.jsx
import React, { useState, useEffect } from "react";
import { apiFetch } from "../../../api/client";

function ReasoningTab({ currentProjectId }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const [activeView, setActiveView] = useState("relationships");

  useEffect(() => {
    if (currentProjectId) {
      loadReasoning(false);
    }
  }, [currentProjectId]);

  const loadReasoning = async (force = false) => {
    setLoading(true);
    setError("");
    try {
      const result = await apiFetch(
        `/projects/${currentProjectId}/reasoning${force ? "?force=true" : ""}`
      );
      setData(result);
    } catch (err) {
      console.error("Failed to load reasoning", err);
      setError(err.message || "Error loading reasoning analysis");
    } finally {
      setLoading(false);
    }
  };

  const renderRelationships = () => {
    const rel = data?.relationships;
    if (!rel) {
      return <div className="rp-info-text">No relationship data available</div>;
    }

    const relationships = rel.relationships || [];

    return (
      <div className="rp-reasoning-section">
        {rel.summary && (
          <div className="rp-reasoning-summary">{rel.summary}</div>
        )}

        {relationships.length === 0 ? (
          <div className="rp-info-text">No file relationships detected</div>
        ) : (
          <div className="rp-reasoning-list">
            {relationships.map((r, idx) => (
              <div key={idx} className="rp-reasoning-item">
                <div className="rp-reasoning-item-header">
                  <span className="rp-reasoning-file">{r.source_file}</span>
                  <span className="rp-reasoning-arrow">→</span>
                  <span className="rp-reasoning-file">{r.target_file}</span>
                  <span
                    className={`rp-tag rp-tag-${
                      r.relationship_type === "contradicts" ? "warning" : "muted"
                    }`}
                  >
                    {r.relationship_type}
                  </span>
                </div>
                <div className="rp-reasoning-description">{r.description}</div>
                {r.confidence && (
                  <div className="rp-reasoning-confidence">
                    Confidence: {Math.round(r.confidence * 100)}%
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const renderContradictions = () => {
    const cont = data?.contradictions;
    if (!cont) {
      return <div className="rp-info-text">No contradiction data available</div>;
    }

    const contradictions = cont.contradictions || [];

    return (
      <div className="rp-reasoning-section">
        {cont.summary && (
          <div className="rp-reasoning-summary">{cont.summary}</div>
        )}

        {contradictions.length === 0 ? (
          <div className="rp-info-text rp-success-text">
            No cross-file contradictions detected
          </div>
        ) : (
          <div className="rp-reasoning-list">
            {contradictions.map((c, idx) => (
              <div
                key={idx}
                className={`rp-reasoning-item rp-reasoning-item-${c.severity || "medium"}`}
              >
                <div className="rp-reasoning-item-header">
                  <span className="rp-reasoning-file">{c.file_1}</span>
                  <span className="rp-reasoning-vs">vs</span>
                  <span className="rp-reasoning-file">{c.file_2}</span>
                  <span
                    className={`rp-tag rp-tag-${
                      c.severity === "high" ? "warning" : "muted"
                    }`}
                  >
                    {c.severity}
                  </span>
                </div>
                <div className="rp-reasoning-issue">{c.issue}</div>
                <div className="rp-reasoning-positions">
                  <div className="rp-reasoning-position">
                    <strong>{c.file_1}:</strong> {c.file_1_position}
                  </div>
                  <div className="rp-reasoning-position">
                    <strong>{c.file_2}:</strong> {c.file_2_position}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const renderLogicFlow = () => {
    const logic = data?.logic_flow;
    if (!logic) {
      return <div className="rp-info-text">No logic flow data available</div>;
    }

    const coverage = logic.coverage_analysis || [];
    const issues = logic.logical_issues || [];
    const score = logic.coherence_score;

    return (
      <div className="rp-reasoning-section">
        {score !== undefined && (
          <div className="rp-reasoning-score">
            <span className="rp-reasoning-score-label">Coherence Score:</span>
            <span
              className={`rp-reasoning-score-value ${
                score >= 0.7 ? "high" : score >= 0.4 ? "medium" : "low"
              }`}
            >
              {Math.round(score * 100)}%
            </span>
          </div>
        )}

        {logic.summary && (
          <div className="rp-reasoning-summary">{logic.summary}</div>
        )}

        {coverage.length > 0 && (
          <div className="rp-reasoning-subsection">
            <h4 className="rp-reasoning-subtitle">Assumption Coverage</h4>
            <div className="rp-reasoning-list">
              {coverage.map((c, idx) => (
                <div key={idx} className="rp-reasoning-item">
                  <div className="rp-reasoning-item-header">
                    <span className="rp-reasoning-file">{c.file}</span>
                    <span
                      className={`rp-tag rp-tag-${
                        c.status === "supported"
                          ? "positive"
                          : c.status === "unsupported"
                          ? "warning"
                          : "muted"
                      }`}
                    >
                      {c.status}
                    </span>
                  </div>
                  <div className="rp-reasoning-assumption">
                    {c.assumption}
                  </div>
                  {c.supporting_files?.length > 0 && (
                    <div className="rp-reasoning-supporting">
                      Supported by: {c.supporting_files.join(", ")}
                    </div>
                  )}
                  {c.gaps?.length > 0 && (
                    <div className="rp-reasoning-gaps">
                      Gaps: {c.gaps.join("; ")}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {issues.length > 0 && (
          <div className="rp-reasoning-subsection">
            <h4 className="rp-reasoning-subtitle">Logical Issues</h4>
            <div className="rp-reasoning-list">
              {issues.map((issue, idx) => (
                <div
                  key={idx}
                  className={`rp-reasoning-item rp-reasoning-item-${issue.severity || "medium"}`}
                >
                  <div className="rp-reasoning-item-header">
                    <span
                      className={`rp-tag rp-tag-${
                        issue.severity === "high" ? "warning" : "muted"
                      }`}
                    >
                      {issue.issue_type}
                    </span>
                    <span
                      className={`rp-tag rp-tag-${
                        issue.severity === "high" ? "warning" : "muted"
                      }`}
                    >
                      {issue.severity}
                    </span>
                  </div>
                  <div className="rp-reasoning-description">
                    {issue.description}
                  </div>
                  {issue.affected_files?.length > 0 && (
                    <div className="rp-reasoning-affected">
                      Affects: {issue.affected_files.join(", ")}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {coverage.length === 0 && issues.length === 0 && (
          <div className="rp-info-text">No logical issues identified</div>
        )}
      </div>
    );
  };

  return (
    <div className="rp-tab-content">
      {/* Controls */}
      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">Cross-File Reasoning</h3>
          <div className="rp-header-actions">
            <button
              className="rp-button subtle"
              onClick={() => loadReasoning(true)}
              disabled={loading}
            >
              {loading ? "Analyzing..." : "Analyze"}
            </button>
          </div>
        </div>
        <div className="rp-section-body">
          <div className="rp-reasoning-controls">
            <button
              className={`rp-button-pill ${
                activeView === "relationships" ? "rp-button-pill-active" : ""
              }`}
              onClick={() => setActiveView("relationships")}
            >
              Relationships
            </button>
            <button
              className={`rp-button-pill ${
                activeView === "contradictions" ? "rp-button-pill-active" : ""
              }`}
              onClick={() => setActiveView("contradictions")}
            >
              Contradictions
            </button>
            <button
              className={`rp-button-pill ${
                activeView === "logic" ? "rp-button-pill-active" : ""
              }`}
              onClick={() => setActiveView("logic")}
            >
              Logic Flow
            </button>
          </div>
        </div>
      </div>

      {error && <div className="rp-error-text">{error}</div>}

      {loading && (
        <div className="rp-section">
          <div className="rp-section-body">
            <div className="rp-info-text">
              Running cross-file analysis... This may take a moment.
            </div>
          </div>
        </div>
      )}

      {!loading && !data && !error && (
        <div className="rp-empty-state">
          <div className="rp-empty-title">No analysis yet</div>
          <div className="rp-empty-text">
            Click "Analyze" to run cross-file reasoning on your project files.
            This will identify relationships, contradictions, and logical flow
            across documents.
          </div>
        </div>
      )}

      {!loading && data && (
        <div className="rp-section">
          <div className="rp-section-body">
            {activeView === "relationships" && renderRelationships()}
            {activeView === "contradictions" && renderContradictions()}
            {activeView === "logic" && renderLogicFlow()}
          </div>
        </div>
      )}
    </div>
  );
}

export default ReasoningTab;
