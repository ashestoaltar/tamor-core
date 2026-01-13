// src/components/RightPanel/hooks/useSemanticSearch.js
import { useState } from "react";
import { apiFetch } from "../../../api/client";

export default function useSemanticSearch({
  currentProjectId,
  activeConversationId,
  activeMode,
  onConversationsChanged,
}) {
  const [semanticQuery, setSemanticQuery] = useState("");
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [semanticError, setSemanticError] = useState("");
  const [semanticResults, setSemanticResults] = useState([]);
  const [semanticAnswer, setSemanticAnswer] = useState("");

  const handleSemanticSearch = async () => {
    if (!currentProjectId || !semanticQuery.trim()) return;

    try {
      setSemanticLoading(true);
      setSemanticError("");
      setSemanticResults([]);
      setSemanticAnswer("");

      const data = await apiFetch(
        `/projects/${currentProjectId}/files/semantic-search`,
        {
          method: "POST",
          body: {
            query: semanticQuery,
            top_k: 8,
          },
        }
      );

      setSemanticResults(data.results || []);
      setSemanticAnswer(data.answer || "");
    } catch (err) {
      console.error("Semantic search failed", err);
      setSemanticError("Error during semantic search");
    } finally {
      setSemanticLoading(false);
    }
  };

  const handleInjectSemanticAnswerToChat = async () => {
    if (!semanticAnswer || !activeConversationId) return;

    const content =
      "Semantic search answer injected from right panel:\n\n" +
      semanticAnswer +
      (semanticQuery
        ? `\n\n(Original query: "${semanticQuery}")`
        : "");

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
      console.error("Failed to inject semantic answer into chat:", err);
    }
  };

  return {
    semanticQuery,
    setSemanticQuery,
    semanticLoading,
    semanticError,
    semanticResults,
    semanticAnswer,
    handleSemanticSearch,
    handleInjectSemanticAnswerToChat,
  };
}
