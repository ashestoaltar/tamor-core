// src/components/RightPanel/tabs/KnowledgeTab.jsx
import React, { useState } from "react";
import { apiFetch } from "../../../api/client";

function KnowledgeTab({
  currentProjectId,
  activeConversationId,
  activeMode,
  onConversationsChanged,
}) {
  const [knowledgeQuery, setKnowledgeQuery] = useState("");
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);
  const [knowledgeError, setKnowledgeError] = useState("");
  const [knowledgeResults, setKnowledgeResults] = useState([]);

  const handleKnowledgeSearch = async () => {
    if (!currentProjectId || !knowledgeQuery.trim()) return;

    setKnowledgeLoading(true);
    setKnowledgeError("");
    setKnowledgeResults([]);

    try {
      const data = await apiFetch(
        `/projects/${currentProjectId}/knowledge/search`,
        {
          method: "POST",
          body: {
            query: knowledgeQuery,
          },
        }
      );

      setKnowledgeResults(data.hits || []);
    } catch (err) {
      console.error("Knowledge search failed", err);
      setKnowledgeError("Error during knowledge search");
    } finally {
      setKnowledgeLoading(false);
    }
  };

  const handleAskKnowledgeHitInChat = async (hit) => {
    if (!activeConversationId || !hit) return;

    const content =
      "Ask about this knowledge symbol from the Knowledge tab:\n\n" +
      JSON.stringify(hit, null, 2);

    try {
      await apiFetch("/chat/inject", {
        method: "POST",
        body: {
          conversation_id: activeConversationId,
          message: content,
          mode: activeMode,
        },
      });

      if (typeof onConversationsChanged === "function") {
        onConversationsChanged();
      }
    } catch (err) {
      console.error("Failed to inject knowledge symbol into chat:", err);
    }
  };

  return (
    <div className="rp-tab-content">
      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">Knowledge search</h3>
        </div>
        <div className="rp-section-body">
          <div className="rp-search-row">
            <input
              className="rp-input"
              placeholder="Search extracted symbols, config keys, parameters…"
              value={knowledgeQuery}
              onChange={(e) => setKnowledgeQuery(e.target.value)}
            />
            <button
              className="rp-button"
              type="button"
              onClick={handleKnowledgeSearch}
              disabled={knowledgeLoading}
            >
              {knowledgeLoading ? "Searching…" : "Search"}
            </button>
          </div>
          {knowledgeError && (
            <div className="rp-error">{knowledgeError}</div>
          )}
          {knowledgeResults.length > 0 && (
            <div className="rp-section-sublist">
              {knowledgeResults.map((hit, idx) => (
                <div key={idx} className="rp-hit-row">
                  <div className="rp-hit-title">
                    {hit.symbol || hit.name || hit.key}
                  </div>
                  <div className="rp-hit-snippet">
                    {hit.context || hit.description || ""}
                  </div>
                  {activeConversationId && (
                    <button
                      className="rp-button subtle"
                      type="button"
                      onClick={() => handleAskKnowledgeHitInChat(hit)}
                    >
                      Ask in chat
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default KnowledgeTab;
