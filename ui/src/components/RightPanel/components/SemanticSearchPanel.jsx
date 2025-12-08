// src/components/RightPanel/components/SemanticSearchPanel.jsx
import React, { useEffect, useMemo, useState } from "react";
import useSemanticSearch from "../hooks/useSemanticSearch";

function shortenSnippet(text, maxLen = 160) {
  if (!text) return "";
  const trimmed = text.trim().replace(/\s+/g, " ");
  if (trimmed.length <= maxLen) return trimmed;
  return trimmed.slice(0, maxLen - 3) + "...";
}

function SemanticSearchPanel({
  currentProjectId,
  activeConversationId,
  activeMode,
  onConversationsChanged,
  onOpenInViewer, // optional callback
}) {
  const {
    semanticQuery,
    setSemanticQuery,
    semanticLoading,
    semanticError,
    semanticResults,
    semanticAnswer,
    handleSemanticSearch,
    handleInjectSemanticAnswerToChat,
  } = useSemanticSearch({
    currentProjectId,
    activeConversationId,
    activeMode,
    onConversationsChanged,
  });

  const [semanticViewMode, setSemanticViewMode] = useState("chunks");
  const [selectedSemanticHit, setSelectedSemanticHit] = useState(null);

  useEffect(() => {
    // reset preview whenever results change
    setSelectedSemanticHit(null);
  }, [semanticResults]);

  const groupedSemanticResults = useMemo(() => {
    if (semanticViewMode !== "files") return null;
    if (!semanticResults || semanticResults.length === 0) return null;

    const byFile = {};

    for (const hit of semanticResults) {
      const fileId = hit.file_id;
      if (!byFile[fileId]) {
        byFile[fileId] = {
          file_id: fileId,
          filename: hit.filename,
          hits: [],
        };
      }
      byFile[fileId].hits.push(hit);
    }

    const groups = Object.values(byFile);
    groups.sort((a, b) => (a.filename || "").localeCompare(b.filename || ""));

    for (const group of groups) {
      group.hits.sort((h1, h2) => {
        const p1 = typeof h1.page === "number" ? h1.page : 9999;
        const p2 = typeof h2.page === "number" ? h2.page : 9999;
        if (p1 !== p2) return p1 - p2;
        return (h2.score || 0) - (h1.score || 0);
      });
    }

    return groups;
  }, [semanticViewMode, semanticResults]);

  const handleOpenInViewerClick = (hit) => {
    if (!onOpenInViewer || !hit) return;
    const page =
      typeof hit.page === "number" && hit.page > 0 ? hit.page : null;
    onOpenInViewer(hit.file_id, page);
  };

  return (
    <div className="rp-section">
      <div className="rp-section-header">
        <h3 className="rp-section-title">Semantic search</h3>
      </div>
      <div className="rp-section-body">
        <div className="rp-search-row">
          <input
            className="rp-input"
            placeholder="Ask in your own words (semantic search)…"
            value={semanticQuery}
            onChange={(e) => setSemanticQuery(e.target.value)}
          />
          <button
            className="rp-button"
            type="button"
            onClick={handleSemanticSearch}
            disabled={semanticLoading}
          >
            {semanticLoading ? "Searching…" : "Ask"}
          </button>
        </div>
        {semanticError && <div className="rp-error">{semanticError}</div>}

        {semanticResults.length > 0 && (
          <div
            className="rp-section-subheader"
            style={{ marginTop: "0.5rem" }}
          >
            <span style={{ marginRight: "0.5rem" }}>View:</span>
            <button
              type="button"
              className={
                semanticViewMode === "chunks"
                  ? "rp-button-pill rp-button-pill-active"
                  : "rp-button-pill"
              }
              onClick={() => setSemanticViewMode("chunks")}
            >
              Chunks
            </button>
            <button
              type="button"
              className={
                semanticViewMode === "files"
                  ? "rp-button-pill rp-button-pill-active"
                  : "rp-button-pill"
              }
              onClick={() => setSemanticViewMode("files")}
              style={{ marginLeft: "0.25rem" }}
            >
              Files
            </button>
          </div>
        )}

        {/* CHUNKS VIEW */}
        {semanticResults.length > 0 && semanticViewMode === "chunks" && (
          <div className="rp-section-sublist">
            {semanticResults.map((hit, idx) => (
              <div key={idx} className="rp-hit-row">
                <div className="rp-hit-title">
                  {hit.filename}
                  {typeof hit.page === "number"
                    ? ` (p. ${hit.page})`
                    : ` (chunk ${hit.chunk_index})`}
                </div>
                <div className="rp-hit-meta">
                  <span className="rp-tag rp-tag-muted">
                    score {hit.score.toFixed(3)}
                  </span>
                  <button
                    className="rp-button-secondary"
                    type="button"
                    onClick={() => setSelectedSemanticHit(hit)}
                    style={{ marginLeft: "0.5rem" }}
                  >
                    Preview
                  </button>
                  {onOpenInViewer && (
                    <button
                      className="rp-button-secondary"
                      type="button"
                      onClick={() => handleOpenInViewerClick(hit)}
                      style={{ marginLeft: "0.5rem" }}
                    >
                      Open in Viewer
                    </button>
                  )}
                </div>
                <div className="rp-hit-snippet">{hit.text}</div>
              </div>
            ))}
          </div>
        )}

        {/* FILES / GROUPED VIEW */}
        {groupedSemanticResults && semanticViewMode === "files" && (
          <div className="rp-section-sublist">
            {groupedSemanticResults.map((group) => (
              <div key={group.file_id} className="rp-hit-group">
                <div className="rp-hit-title">
                  {group.filename}
                  <button
                    className="rp-button-secondary"
                    type="button"
                    onClick={() =>
                      setSelectedSemanticHit(group.hits[0])
                    }
                    style={{ marginLeft: "0.5rem" }}
                  >
                    Preview
                  </button>
                  {onOpenInViewer && group.hits[0] && (
                    <button
                      className="rp-button-secondary"
                      type="button"
                      onClick={() =>
                        handleOpenInViewerClick(group.hits[0])
                      }
                      style={{ marginLeft: "0.5rem" }}
                    >
                      Open in Viewer
                    </button>
                  )}
                </div>
                <div className="rp-hit-meta">
                  <span className="rp-tag rp-tag-muted">
                    {group.hits.length} hit
                    {group.hits.length !== 1 ? "s" : ""} in this file
                  </span>
                  {group.hits.length > 0 && (
                    <span className="rp-hit-mini-summary">
                      {" · "}
                      {shortenSnippet(group.hits[0].text, 90)}
                      {group.hits[1]
                        ? " | " +
                          shortenSnippet(group.hits[1].text, 60)
                        : ""}
                    </span>
                  )}
                </div>

                <ul className="rp-hit-group-list">
                  {group.hits.map((hit, idx) => (
                    <li key={idx} className="rp-hit-group-item">
                      <div className="rp-hit-group-line">
                        <span className="rp-hit-group-page">
                          {typeof hit.page === "number"
                            ? `p. ${hit.page}`
                            : `chunk ${hit.chunk_index}`}
                        </span>
                        <button
                          type="button"
                          className="rp-button-secondary rp-button-compact"
                          onClick={() => {
                            const base = `/api/files/${hit.file_id}/download`;
                            const pagePart =
                              typeof hit.page === "number"
                                ? `#page=${hit.page}${
                                    semanticQuery
                                      ? `&search=${encodeURIComponent(
                                          semanticQuery
                                        )}`
                                      : ""
                                  }`
                                : "";
                            window.open(base + pagePart, "_blank");
                          }}
                          style={{ marginLeft: "0.5rem" }}
                        >
                          Open at hit
                        </button>
                        {onOpenInViewer && (
                          <button
                            type="button"
                            className="rp-button-secondary rp-button-compact"
                            onClick={() => handleOpenInViewerClick(hit)}
                            style={{ marginLeft: "0.5rem" }}
                          >
                            Viewer
                          </button>
                        )}
                      </div>
                      <div className="rp-hit-group-snippet">
                        {shortenSnippet(hit.text)}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        {/* INLINE PREVIEW FROM SEARCH */}
        {selectedSemanticHit && (
          <div className="rp-section-sublist">
            <h4 className="rp-section-subtitle">
              Preview: {selectedSemanticHit.filename}
              {typeof selectedSemanticHit.page === "number" &&
                ` (page ${selectedSemanticHit.page})`}
            </h4>
            <iframe
              title="Spec preview"
              src={`/api/files/${selectedSemanticHit.file_id}/download${
                typeof selectedSemanticHit.page === "number"
                  ? `#page=${selectedSemanticHit.page}${
                      semanticQuery
                        ? `&search=${encodeURIComponent(semanticQuery)}`
                        : ""
                    }`
                  : ""
              }`}
              style={{
                width: "100%",
                height: "420px",
                border: "1px solid #333",
                borderRadius: "4px",
              }}
            />
          </div>
        )}

        {/* LLM ANSWER */}
        {semanticAnswer && (
          <div className="rp-summary-preview">
            <h4 className="rp-section-subtitle">LLM answer</h4>
            <pre>{semanticAnswer}</pre>
            {activeConversationId && (
              <div className="rp-search-row">
                <button
                  className="rp-button subtle"
                  type="button"
                  onClick={handleInjectSemanticAnswerToChat}
                >
                  Ask follow-ups in chat
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default SemanticSearchPanel;

