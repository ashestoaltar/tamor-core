// src/components/RightPanel/tabs/InsightsTab.jsx
import React, { useState, useEffect } from "react";
import { apiFetch } from "../../../api/client";

function InsightsTab({ currentProjectId }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [aggregated, setAggregated] = useState(null);
  const [fileInsights, setFileInsights] = useState([]);
  const [viewMode, setViewMode] = useState("aggregated"); // "aggregated" | "by-file"
  const [expandedFile, setExpandedFile] = useState(null);

  useEffect(() => {
    if (currentProjectId) {
      loadInsights();
    }
  }, [currentProjectId]);

  const loadInsights = async () => {
    setLoading(true);
    setError("");
    try {
      // Load both aggregated and per-file views
      const [aggData, filesData] = await Promise.all([
        apiFetch(`/projects/${currentProjectId}/insights?aggregate=true`),
        apiFetch(`/projects/${currentProjectId}/insights?aggregate=false`),
      ]);
      setAggregated(aggData);
      setFileInsights(filesData.files || []);
    } catch (err) {
      console.error("Failed to load insights", err);
      setError("Error loading insights");
    } finally {
      setLoading(false);
    }
  };

  const renderInsightsList = (items, emptyText) => {
    if (!items || items.length === 0) {
      return <div className="rp-info-text">{emptyText}</div>;
    }
    return (
      <ul className="rp-insights-list">
        {items.map((item, idx) => (
          <li key={idx} className="rp-insights-item">
            <span className="rp-insights-text">
              {typeof item === "string" ? item : item.text}
            </span>
            {item.file && (
              <span className="rp-insights-file">{item.file}</span>
            )}
          </li>
        ))}
      </ul>
    );
  };

  const renderAggregatedView = () => {
    if (!aggregated) return null;

    const { file_count, themes, contradictions, missing_info, assumptions } =
      aggregated;

    return (
      <>
        <div className="rp-section">
          <div className="rp-section-header">
            <h3 className="rp-section-title">Themes</h3>
            <span className="rp-tag rp-tag-muted">
              {themes?.length || 0}
            </span>
          </div>
          <div className="rp-section-body">
            {renderInsightsList(themes, "No themes identified yet")}
          </div>
        </div>

        <div className="rp-section">
          <div className="rp-section-header">
            <h3 className="rp-section-title">Contradictions</h3>
            <span className="rp-tag rp-tag-warning">
              {contradictions?.length || 0}
            </span>
          </div>
          <div className="rp-section-body">
            {renderInsightsList(
              contradictions,
              "No contradictions detected"
            )}
          </div>
        </div>

        <div className="rp-section">
          <div className="rp-section-header">
            <h3 className="rp-section-title">Missing Information</h3>
            <span className="rp-tag rp-tag-muted">
              {missing_info?.length || 0}
            </span>
          </div>
          <div className="rp-section-body">
            {renderInsightsList(missing_info, "No gaps identified")}
          </div>
        </div>

        <div className="rp-section">
          <div className="rp-section-header">
            <h3 className="rp-section-title">Assumptions</h3>
            <span className="rp-tag rp-tag-muted">
              {assumptions?.length || 0}
            </span>
          </div>
          <div className="rp-section-body">
            {renderInsightsList(assumptions, "No assumptions identified")}
          </div>
        </div>
      </>
    );
  };

  const renderFileView = () => {
    if (fileInsights.length === 0) {
      return (
        <div className="rp-empty-state">
          <div className="rp-empty-title">No insights generated</div>
          <div className="rp-empty-text">
            Insights are automatically generated when files are processed.
            Upload files to your project to see insights.
          </div>
        </div>
      );
    }

    return fileInsights.map((file) => {
      const isExpanded = expandedFile === file.file_id;
      const insights = file.insights || {};
      const totalCount =
        (insights.themes?.length || 0) +
        (insights.contradictions?.length || 0) +
        (insights.missing_info?.length || 0) +
        (insights.assumptions?.length || 0);

      return (
        <div key={file.file_id} className="rp-section">
          <div
            className="rp-section-header rp-clickable"
            onClick={() =>
              setExpandedFile(isExpanded ? null : file.file_id)
            }
          >
            <div className="rp-file-header-info">
              <h3 className="rp-section-title">{file.filename}</h3>
              {file.summary && (
                <div className="rp-file-summary-text">{file.summary}</div>
              )}
            </div>
            <span className="rp-tag rp-tag-muted">
              {totalCount} insight{totalCount !== 1 ? "s" : ""}
            </span>
          </div>

          {isExpanded && (
            <div className="rp-section-body rp-insights-expanded">
              {insights.themes?.length > 0 && (
                <div className="rp-insights-category">
                  <div className="rp-insights-category-title">Themes</div>
                  {renderInsightsList(insights.themes, "")}
                </div>
              )}
              {insights.contradictions?.length > 0 && (
                <div className="rp-insights-category">
                  <div className="rp-insights-category-title">
                    Contradictions
                  </div>
                  {renderInsightsList(insights.contradictions, "")}
                </div>
              )}
              {insights.missing_info?.length > 0 && (
                <div className="rp-insights-category">
                  <div className="rp-insights-category-title">
                    Missing Info
                  </div>
                  {renderInsightsList(insights.missing_info, "")}
                </div>
              )}
              {insights.assumptions?.length > 0 && (
                <div className="rp-insights-category">
                  <div className="rp-insights-category-title">
                    Assumptions
                  </div>
                  {renderInsightsList(insights.assumptions, "")}
                </div>
              )}
              {totalCount === 0 && (
                <div className="rp-info-text">
                  No insights for this file
                </div>
              )}
            </div>
          )}
        </div>
      );
    });
  };

  return (
    <div className="rp-tab-content">
      {/* Controls */}
      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">Auto-Insights</h3>
          <div className="rp-header-actions">
            <button
              className="rp-button subtle"
              onClick={loadInsights}
              disabled={loading}
            >
              {loading ? "Loading..." : "Refresh"}
            </button>
          </div>
        </div>
        <div className="rp-section-body">
          <div className="rp-insights-controls">
            <button
              className={`rp-button-pill ${
                viewMode === "aggregated" ? "rp-button-pill-active" : ""
              }`}
              onClick={() => setViewMode("aggregated")}
            >
              Summary
            </button>
            <button
              className={`rp-button-pill ${
                viewMode === "by-file" ? "rp-button-pill-active" : ""
              }`}
              onClick={() => setViewMode("by-file")}
            >
              By File ({fileInsights.length})
            </button>
          </div>
          {aggregated && (
            <div className="rp-insights-meta">
              {aggregated.file_count} file
              {aggregated.file_count !== 1 ? "s" : ""} analyzed
            </div>
          )}
        </div>
      </div>

      {error && <div className="rp-error-text">{error}</div>}

      {loading && (
        <div className="rp-section">
          <div className="rp-section-body">
            <div className="rp-info-text">Loading insights...</div>
          </div>
        </div>
      )}

      {!loading && viewMode === "aggregated" && renderAggregatedView()}
      {!loading && viewMode === "by-file" && renderFileView()}
    </div>
  );
}

export default InsightsTab;
