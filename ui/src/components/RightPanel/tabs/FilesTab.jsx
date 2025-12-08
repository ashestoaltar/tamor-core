// src/components/RightPanel/tabs/FilesTab.jsx
import React, { useEffect, useState } from "react";
import { apiFetch } from "../../../api/client";

import FileList from "../components/FileList.jsx";
import StructurePanel from "../components/StructurePanel.jsx";
import ProjectSummaryPanel from "../components/ProjectSummaryPanel.jsx";

function FilesTab({
  currentProjectId,
  activeConversationId,
  activeMode,
  onConversationsChanged,
}) {
  // Files list
  const [files, setFiles] = useState([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [filesError, setFilesError] = useState("");

  // File keyword search
  const [fileSearchQuery, setFileSearchQuery] = useState("");
  const [fileSearchLoading, setFileSearchLoading] = useState(false);
  const [fileSearchError, setFileSearchError] = useState("");
  const [fileSearchResults, setFileSearchResults] = useState([]);

  // Per-file summaries
  const [fileSummaryLoadingId, setFileSummaryLoadingId] = useState(null);
  const [fileSummaryErrorId, setFileSummaryErrorId] = useState(null);
  const [fileSummaries, setFileSummaries] = useState({});

  // Parsed structure
  const [structureFileId, setStructureFileId] = useState(null);
  const [structureLoading, setStructureLoading] = useState(false);
  const [structureError, setStructureError] = useState("");
  const [structureData, setStructureData] = useState(null);

  // Project-level summary
  const [projectSummaryPrompt, setProjectSummaryPrompt] = useState(
    "High-level overview focusing on constraints, config keys, and open questions."
  );
  const [projectSummaryLoading, setProjectSummaryLoading] = useState(false);
  const [projectSummaryError, setProjectSummaryError] = useState("");
  const [projectSummaryText, setProjectSummaryText] = useState("");

  useEffect(() => {
    if (!currentProjectId) {
      setFiles([]);
      setFilesError("");
      setFilesLoading(false);
      setFileSearchResults([]);
      setFileSummaries({});
      setFileSummaryLoadingId(null);
      setFileSummaryErrorId(null);
      setProjectSummaryText("");
      setStructureFileId(null);
      setStructureData(null);
      setStructureError("");
      setStructureLoading(false);
      return;
    }

    const fetchFiles = async () => {
      setFilesLoading(true);
      setFilesError("");
      try {
        const data = await apiFetch(`/projects/${currentProjectId}/files`);
        setFiles(data.files || []);
      } catch (err) {
        console.error("Failed to fetch project files", err);
        setFilesError("Error loading files");
      } finally {
        setFilesLoading(false);
      }
    };

    fetchFiles();
  }, [currentProjectId]);

  const handleFileKeywordSearch = async () => {
    if (!currentProjectId || !fileSearchQuery.trim()) return;
    setFileSearchLoading(true);
    setFileSearchError("");
    setFileSearchResults([]);
    try {
      const data = await apiFetch(
        `/projects/${currentProjectId}/files/search`,
        {
          method: "POST",
          body: { query: fileSearchQuery },
        }
      );
      setFileSearchResults(data.matches || []);
    } catch (err) {
      console.error("File keyword search failed", err);
      setFileSearchError("Error during keyword search");
    } finally {
      setFileSearchLoading(false);
    }
  };

  const handleFileSummary = async (fileId) => {
    if (!fileId || !currentProjectId) return;

    setFileSummaryLoadingId(fileId);
    setFileSummaryErrorId(null);

    try {
      const data = await apiFetch(`/files/${fileId}/summarize`, {
        method: "POST",
        body: { task: "summary" },
      });

      const summary = data.result || "";
      setFileSummaries((prev) => ({
        ...prev,
        [fileId]: summary,
      }));
    } catch (err) {
      console.error("File summarization failed", err);
      setFileSummaryErrorId(fileId);
    } finally {
      setFileSummaryLoadingId(null);
    }
  };

  const handleSelectStructureFile = async (fileId) => {
    if (!currentProjectId || !fileId) return;

    setStructureFileId(fileId);
    setStructureLoading(true);
    setStructureError("");
    setStructureData(null);

    try {
      const data = await apiFetch(`/files/${fileId}/content`);
      const meta = data.meta || {};
      const structure = meta.structure || null;
      setStructureData(structure);
    } catch (err) {
      console.error("Failed to load file structure", err);
      setStructureError("Error loading file structure");
    } finally {
      setStructureLoading(false);
    }
  };

  const handleInjectSummaryToChat = async () => {
    if (!projectSummaryText || !activeConversationId) return;

    const content =
      "Project summary injected from right panel:\n\n" +
      projectSummaryText;

    try {
      await apiFetch("/chat/inject", {
        method: "POST",
        body: {
          conversation_id: activeConversationId,
          message: content,
          mode: activeMode,
        },
      });

      if (onConversationsChanged) {
        onConversationsChanged();
      }
    } catch (err) {
      console.error("Failed to inject summary into chat:", err);
    }
  };

  const handleInjectFileSummaryToChat = async (fileId) => {
    const summary = fileSummaries[fileId];
    if (!summary || !activeConversationId) return;

    const content =
      "File summary injected from right panel:\n\n" + summary;

    try {
      await apiFetch("/chat/inject", {
        method: "POST",
        body: {
          conversation_id: activeConversationId,
          message: content,
          mode: activeMode,
        },
      });

      if (onConversationsChanged) {
        onConversationsChanged();
      }
    } catch (err) {
      console.error("Failed to inject file summary into chat:", err);
    }
  };

  const handleProjectSummary = async () => {
    if (!currentProjectId) return;

    setProjectSummaryLoading(true);
    setProjectSummaryError("");
    setProjectSummaryText("");

    try {
      const data = await apiFetch(
        `/projects/${currentProjectId}/summarize`,
        {
          method: "POST",
          body: {
            prompt: projectSummaryPrompt,
          },
        }
      );

      const summaryPayload = data.summary;
      if (summaryPayload && typeof summaryPayload === "object") {
        setProjectSummaryText(
          summaryPayload.summary || JSON.stringify(summaryPayload, null, 2)
        );
      } else {
        setProjectSummaryText(summaryPayload || "");
      }
    } catch (err) {
      console.error("Project summarization failed", err);
      setProjectSummaryError("Error during project summarization");
    } finally {
      setProjectSummaryLoading(false);
    }
  };

  return (
    <div className="rp-tab-content">
      {/* Project files */}
      <FileList
        files={files}
        filesLoading={filesLoading}
        filesError={filesError}
        fileSummaries={fileSummaries}
        fileSummaryLoadingId={fileSummaryLoadingId}
        fileSummaryErrorId={fileSummaryErrorId}
        structureFileId={structureFileId}
        structureLoading={structureLoading}
        activeConversationId={activeConversationId}
        onSummarize={handleFileSummary}
        onSelectStructure={handleSelectStructureFile}
        onSendSummaryToChat={handleInjectFileSummaryToChat}
      />

      {/* Structure block */}
      <StructurePanel
        structureFileId={structureFileId}
        structureLoading={structureLoading}
        structureError={structureError}
        structureData={structureData}
      />

      <div className="rp-divider" />

      {/* Keyword search */}
      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">Keyword search</h3>
        </div>
        <div className="rp-section-body">
          <div className="rp-search-row">
            <input
              className="rp-input"
              placeholder="Find exact words across files…"
              value={fileSearchQuery}
              onChange={(e) => setFileSearchQuery(e.target.value)}
            />
            <button
              className="rp-button"
              type="button"
              onClick={handleFileKeywordSearch}
              disabled={fileSearchLoading}
            >
              {fileSearchLoading ? "Searching…" : "Search"}
            </button>
          </div>
          {fileSearchError && (
            <div className="rp-error">{fileSearchError}</div>
          )}
          {fileSearchResults.length > 0 && (
            <div className="rp-section-sublist">
              {fileSearchResults.map((r, idx) => (
                <div key={idx} className="rp-hit-row">
                  <div className="rp-hit-title">{r.filename}</div>
                  <div className="rp-hit-snippet">{r.snippet}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="rp-divider" />

      {/* Project summary */}
      <ProjectSummaryPanel
        projectSummaryPrompt={projectSummaryPrompt}
        setProjectSummaryPrompt={setProjectSummaryPrompt}
        projectSummaryLoading={projectSummaryLoading}
        projectSummaryError={projectSummaryError}
        projectSummaryText={projectSummaryText}
        activeConversationId={activeConversationId}
        onSummarize={handleProjectSummary}
        onSendSummaryToChat={handleInjectSummaryToChat}
      />
    </div>
  );
}

export default FilesTab;

