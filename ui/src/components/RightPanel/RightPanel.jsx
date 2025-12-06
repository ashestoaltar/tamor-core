import "./RightPanel.css";
import { useEffect, useState } from "react";
import { apiFetch, API_BASE } from "../../api/client";

const PLAYLIST_OPTIONS = [
  { slug: "christmas", label: "Christmas" },
  { slug: "thanksgiving", label: "Thanksgiving" },
  { slug: "favorites", label: "Favorites" },
  { slug: "kids", label: "Kids" },
];

const PREVIEW_MAX_CHARS = 16000;

function getFileEmoji(filename, mimeType) {
  const name = (filename || "").toLowerCase();
  const mime = (mimeType || "").toLowerCase();

  if (name.endsWith(".pdf") || mime === "application/pdf") return "📄";
  if (
    name.match(/\.(png|jpe?g|gif|webp|svg)$/) ||
    mime.startsWith("image/")
  ) {
    return "🖼️";
  }
  if (name.match(/\.(mp4|mkv|webm|mov)$/) || mime.startsWith("video/")) {
    return "🎬";
  }
  if (name.match(/\.(mp3|wav|flac|m4a)$/) || mime.startsWith("audio/")) {
    return "🎧";
  }
  if (name.endsWith(".zip") || name.endsWith(".rar")) return "🗜️";
  if (name.endsWith(".csv")) return "📊";
  if (name.match(/\.(js|ts|jsx|tsx|py|json|yml|yaml|lisp|html|css|md)$/)) {
    return "📜";
  }
  return "📁";
}

function isTextLikeFile(file) {
  if (!file) return false;
  const mime = (file.mime_type || "").toLowerCase();
  const name = (file?.filename || "").toLowerCase();

  if (mime.startsWith("text/")) return true;

  const textExts = [
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".py",
    ".lisp",
    ".html",
    ".css",
    ".csv",
    ".yml",
    ".yaml",
  ];

  return textExts.some((ext) => name.endsWith(ext));
}

// Simple inline highlighter for search snippets
function HighlightedSnippet({ snippet, query }) {
  if (!query) return <>{snippet}</>;
  const lower = snippet.toLowerCase();
  const q = query.toLowerCase();
  const idx = lower.indexOf(q);
  if (idx === -1) return <>{snippet}</>;

  const before = snippet.slice(0, idx);
  const match = snippet.slice(idx, idx + query.length);
  const after = snippet.slice(idx + query.length);

  return (
    <>
      {before}
      <mark>{match}</mark>
      {after}
    </>
  );
}

export default function RightPanel({
  lastMemoryMatches,
  activeMode,
  currentProjectId,
  conversationRefreshToken,
  activeConversationId,
  onConversationsChanged,
}) {
  const [activeTab, setActiveTab] = useState("workspace");

  // Notes
  const [notes, setNotes] = useState("");
  const [notesLoading, setNotesLoading] = useState(false);
  const [notesSaving, setNotesSaving] = useState(false);
  const [notesStatus, setNotesStatus] = useState("");

  // Playlists
  const [playlistSlug, setPlaylistSlug] = useState("christmas");
  const [playlistItems, setPlaylistItems] = useState([]);
  const [playlistLoading, setPlaylistLoading] = useState(false);

  // Files
  const [files, setFiles] = useState([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadSuccess, setUploadSuccess] = useState("");
  const [filesRefreshToken, setFilesRefreshToken] = useState(0);

  // File analysis (LLM summary / QA)
  const [previewFileId, setPreviewFileId] = useState(null);
  const [previewFileName, setPreviewFileName] = useState("");
  const [previewMode, setPreviewMode] = useState("qa");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [fileQuery, setFileQuery] = useState("");
  const [previewAnswer, setPreviewAnswer] = useState("");

  // Project-wide keyword search (simple substring)
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");

  // Project-wide semantic search (embeddings + LLM)
  const [semanticQuery, setSemanticQuery] = useState("");
  const [semanticResults, setSemanticResults] = useState([]);
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [semanticError, setSemanticError] = useState("");

  // Project-wide summary (Phase 2.2)
  const [projectSummaryPrompt, setProjectSummaryPrompt] = useState(
    "High-level overview of this project’s files, focusing on constraints, config keys, and open questions."
  );
  const [projectSummaryLoading, setProjectSummaryLoading] = useState(false);
  const [projectSummaryError, setProjectSummaryError] = useState("");
  const [projectSummaryText, setProjectSummaryText] = useState("");

  // Knowledge graph (symbols)
  const [knowledgeStats, setKnowledgeStats] = useState(null);
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);
  const [knowledgeError, setKnowledgeError] = useState("");
  const [symbolQuery, setSymbolQuery] = useState("");
  const [symbolResults, setSymbolResults] = useState([]);

  // Inline file content preview (for text/code + images)
  const [selectedFile, setSelectedFile] = useState(null);
  const [contentPreview, setContentPreview] = useState({
    loading: false,
    text: "",
    truncated: false,
    error: null,
  });

  // --- Global scroll-to-file handler (used by ChatPanel later) -------------
  useEffect(() => {
    function handleScrollToFileEvent(e) {
      const fileId = e.detail?.fileId;
      if (!fileId) return;

      // Switch to Files tab
      setActiveTab("files");

      // Give React a tick to render files list
      setTimeout(() => {
        const row = document.querySelector(`[data-file-id="${fileId}"]`);
        if (row) {
          row.scrollIntoView({ block: "center", behavior: "smooth" });
          row.classList.add("rp-file-highlight");
          setTimeout(() => {
            row.classList.remove("rp-file-highlight");
          }, 1500);
        }
      }, 50);
    }

    window.addEventListener("tamor-scroll-to-file", handleScrollToFileEvent);
    return () => {
      window.removeEventListener(
        "tamor-scroll-to-file",
        handleScrollToFileEvent
      );
    };
  }, []);

  // --- Workspace notes ------------------------------------------------------

  useEffect(() => {
    if (activeTab !== "workspace") return;

    if (!currentProjectId) {
      setNotes("");
      setNotesStatus("Select a project to edit workspace notes.");
      return;
    }

    async function fetchNotes() {
      try {
        setNotesLoading(true);
        setNotesStatus("");
        const data = await apiFetch(`/projects/${currentProjectId}/notes`);
        setNotes(data.content || "");
      } catch (err) {
        console.error("Failed to load project notes:", err);
        setNotesStatus("Error loading notes.");
      } finally {
        setNotesLoading(false);
      }
    }

    fetchNotes();
  }, [activeTab, currentProjectId]);

  const handleNotesSave = async () => {
    if (!currentProjectId) return;
    try {
      setNotesSaving(true);
      setNotesStatus("Saving…");
      const data = await apiFetch(`/projects/${currentProjectId}/notes`, {
        method: "POST",
        body: { content: notes },
      });
      setNotes(data.content || "");
      setNotesStatus("Saved!");
    } catch (err) {
      console.error("Failed to save project notes:", err);
      setNotesStatus("Error saving notes.");
    } finally {
      setNotesSaving(false);
      setTimeout(() => setNotesStatus(""), 2000);
    }
  };

  // --- Playlists ------------------------------------------------------------

  useEffect(() => {
    if (activeTab !== "playlists") return;

    async function fetchPlaylist() {
      try {
        setPlaylistLoading(true);
        const data = await apiFetch(`/playlists/${playlistSlug}`);
        setPlaylistItems(data.items || []);
      } catch (err) {
        console.error("Failed to load playlist:", err);
      } finally {
        setPlaylistLoading(false);
      }
    }

    fetchPlaylist();
  }, [activeTab, playlistSlug]);

  const handleRemoveFromPlaylist = async (title) => {
    if (!playlistSlug || !title) return;

    try {
      await apiFetch(`/playlists/${playlistSlug}`, {
        method: "DELETE",
        body: { title },
      });
      setPlaylistItems((prev) => prev.filter((item) => item.title !== title));
    } catch (err) {
      console.error("Failed to remove from playlist:", err);
    }
  };

  // --- Files: list + upload -------------------------------------------------

  useEffect(() => {
    if (activeTab !== "files") return;
    if (!currentProjectId) {
      setFiles([]);
      setFilesLoading(false);
      return;
    }

    let cancelled = false;

    async function fetchFiles() {
      try {
        setFilesLoading(true);
        const data = await apiFetch(
          `/projects/${currentProjectId}/files?refresh=${filesRefreshToken}`
        );
        if (cancelled) return;
        setFiles(data.files || []);
      } catch (err) {
        console.error("Failed to load project files:", err);
      } finally {
        if (!cancelled) {
          setFilesLoading(false);
        }
      }
    }

    fetchFiles();

    return () => {
      cancelled = true;
    };
  }, [activeTab, currentProjectId, filesRefreshToken]);

  // Inline content preview for selected file
  useEffect(() => {
    if (!selectedFile) {
      setContentPreview({
        loading: false,
        text: "",
        truncated: false,
        error: null,
      });
      return;
    }

    let cancelled = false;

    async function loadPreview() {
      setContentPreview({
        loading: true,
        text: "",
        truncated: false,
        error: null,
      });

      try {
        if (
          selectedFile.mime_type?.startsWith("image/") &&
          !isTextLikeFile(selectedFile)
        ) {
          setContentPreview({
            loading: false,
            text: "",
            truncated: false,
            error: null,
          });
          return;
        }

        const res = await fetch(`${API_BASE}/files/${selectedFile.id}`);
        if (!res.ok) {
          throw new Error("Failed to load file content");
        }

        const text = await res.text();
        if (cancelled) return;

        const fullText = text || "";
        const truncated = fullText.length > PREVIEW_MAX_CHARS;

        setContentPreview({
          loading: false,
          text: truncated
            ? fullText.slice(0, PREVIEW_MAX_CHARS) + "\n\n[... truncated ...]"
            : fullText,
          truncated,
          error: null,
        });
      } catch (err) {
        if (cancelled) return;
        setContentPreview({
          loading: false,
          text: "",
          truncated: false,
          error: err.message || "Failed to load preview",
        });
      }
    }

    loadPreview();

    return () => {
      cancelled = true;
    };
  }, [selectedFile]);

  const handleFileInputChange = async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file || !currentProjectId) return;

    event.target.value = "";

    setUploading(true);
    setUploadError("");
    setUploadSuccess("");

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("project_id", String(currentProjectId));

      const response = await fetch(`${API_BASE}/files/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Upload failed");
      }

      setUploadSuccess(`Uploaded ${data.filename || file.name}`);
      setFilesRefreshToken((prev) => prev + 1);
    } catch (err) {
      console.error("Upload error:", err);
      setUploadError(err.message || "Upload failed");
    } finally {
      setUploading(false);
      setTimeout(() => {
        setUploadError("");
        setUploadSuccess("");
      }, 3000);
    }
  };

  const handleDeleteFile = async (fileId) => {
    if (!currentProjectId || !fileId) return;
    if (!window.confirm("Delete this file from the project?")) return;

    try {
      await apiFetch(`/files/${fileId}`, {
        method: "DELETE",
      });
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
    } catch (err) {
      console.error("Failed to delete file:", err);
    }
  };

  // --- Per-file LLM analysis (summary / QA) ---------------------------------

  const handleSummarizeFile = (file) => {
    if (!file) return;
    setPreviewFileId(file.id);
    setPreviewFileName(file.filename);
    setPreviewMode("qa");
    setFileQuery("");
    setPreviewAnswer("");
  };

  const clearPreview = () => {
    setPreviewFileId(null);
    setPreviewFileName("");
    setFileQuery("");
    setPreviewAnswer("");
    setPreviewLoading(false);
  };

  const handleAskAboutFile = async () => {
    if (!previewFileId || !fileQuery.trim()) return;

    try {
      setPreviewLoading(true);
      setPreviewAnswer("");

      const data = await apiFetch(`/files/${previewFileId}/analyze`, {
        method: "POST",
        body: {
          mode: previewMode,
          query: fileQuery.trim(),
        },
      });

      const answer =
        data.answer || data.summary || data.text || JSON.stringify(data, null, 2);
      setPreviewAnswer(answer);
    } catch (err) {
      console.error("Ask about file failed:", err);
      setPreviewAnswer(`Error: ${err.message || "Request failed"}`);
    } finally {
      setPreviewLoading(false);
    }
  };

  // --- Project-wide keyword search -----------------------------------------

  const handleSearchProjectFiles = async () => {
    if (!currentProjectId || !searchQuery.trim()) return;

    try {
      setSearchLoading(true);
      setSearchError("");
      setSearchResults([]);

      const data = await apiFetch(
        `/projects/${currentProjectId}/files/search`,
        {
          method: "POST",
          body: {
            query: searchQuery.trim(),
          },
        }
      );

      setSearchResults(data.hits || []);
    } catch (err) {
      console.error("Keyword search failed:", err);
      setSearchError(err.message || "Search failed");
    } finally {
      setSearchLoading(false);
    }
  };

  // --- Project-wide semantic search (Phase 2.1) ----------------------------

  const handleSemanticSearch = async () => {
    if (!currentProjectId || !semanticQuery.trim()) return;

    try {
      setSemanticLoading(true);
      setSemanticError("");
      setSemanticResults([]);

      const data = await apiFetch(
        `/projects/${currentProjectId}/files/semantic-search`,
        {
          method: "POST",
          body: {
            query: semanticQuery.trim(),
          },
        }
      );

      setSemanticResults(data.results || []);
    } catch (err) {
      console.error("Semantic search failed:", err);
      setSemanticError(err.message || "Semantic search failed");
    } finally {
      setSemanticLoading(false);
    }
  };

  // --- Project-wide summary (Phase 2.2) ------------------------------------

  const handleProjectSummary = async () => {
    if (!currentProjectId) return;

    try {
      setProjectSummaryLoading(true);
      setProjectSummaryError("");
      setProjectSummaryText("");

      const data = await apiFetch(`/projects/${currentProjectId}/summarize`, {
        method: "POST",
        body: {
          prompt: projectSummaryPrompt.trim(),
        },
      });

      setProjectSummaryText(data.summary || "");
    } catch (err) {
      console.error("Project summary failed:", err);
      setProjectSummaryError(err.message || "Project summary failed");
    } finally {
      setProjectSummaryLoading(false);
    }
  };

  const handleInjectSummaryToChat = async () => {
    if (!projectSummaryText || !activeConversationId) return;

    const content = `Project summary injected from right panel:\n\n${projectSummaryText}`;

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
      console.error("Failed to inject project summary into chat:", err);
    }
  };

  // --- Ask-in-chat for symbols (Phase 2.3) ---------------------------------

  const handleAskSymbolInChat = async (hit) => {
    if (!activeConversationId) {
      alert("Open or create a chat first, then try again.");
      return;
    }

    const symbolName = hit.symbol || symbolQuery || "this symbol";
    const fileLabel = `${hit.filename || "unknown file"} (line ${
      hit.line_number ?? "?"
    })`;

    const content =
      `Question about project symbol **${symbolName}**:\n\n` +
      `- File: ${fileLabel}\n` +
      (hit.snippet ? `- Snippet: \`${hit.snippet}\`\n\n` : `\n`) +
      `Please explain what **${symbolName}** represents in this project, ` +
      `what constraints or typical values it has, and any related parameters I should be aware of.`;

    try {
      await apiFetch("/chat/inject-and-reply", {
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
      console.error("Failed to inject symbol question into chat:", err);
      alert("Could not send question to chat.");
    }
  };

  // --- Knowledge graph (Phase 2.3) -----------------------------------------

  const handleKnowledgeExtract = async () => {
    if (!currentProjectId) return;
    try {
      setKnowledgeLoading(true);
      setKnowledgeError("");
      const data = await apiFetch(
        `/projects/${currentProjectId}/knowledge/extract`,
        {
          method: "POST",
        }
      );
      setKnowledgeStats(data || null);
    } catch (err) {
      console.error("Failed to extract knowledge:", err);
      setKnowledgeError(err.message || "Failed to extract symbols");
    } finally {
      setKnowledgeLoading(false);
    }
  };

  const handleKnowledgeSearch = async () => {
    if (!currentProjectId || !symbolQuery.trim()) return;
    try {
      setKnowledgeLoading(true);
      setKnowledgeError("");
      const data = await apiFetch(
        `/projects/${currentProjectId}/knowledge/search`,
        {
          method: "POST",
          body: { symbol: symbolQuery.trim(), top_k: 50 },
        }
      );
      const hits = data.hits || data.results || [];
      setSymbolResults(hits);
    } catch (err) {
      console.error("Failed to search symbols:", err);
      setKnowledgeError(err.message || "Failed to search symbols");
    } finally {
      setKnowledgeLoading(false);
    }
  };

  // --- Render helpers ------------------------------------------------------

  const renderWorkspaceTab = () => (
    <div className="rp-section">
      <h3 className="rp-section-title">Workspace Notes</h3>

      {!currentProjectId && (
        <p className="rp-help-text">
          Select a project in the left panel to attach notes and files.
        </p>
      )}

      {currentProjectId && (
        <>
          <textarea
            className="rp-notes-textarea"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Brain dump, todos, and key decisions for this project…"
            rows={8}
          />
          <div className="rp-notes-actions">
            <button
              className="rp-button"
              type="button"
              onClick={handleNotesSave}
              disabled={notesSaving}
            >
              {notesSaving ? "Saving…" : "Save notes"}
            </button>
            {notesStatus && (
              <span className="rp-status-text">{notesStatus}</span>
            )}
          </div>
        </>
      )}

      {!!lastMemoryMatches?.length && (
        <>
          <div className="rp-divider" />
          <h4 className="rp-section-subtitle">Recent memories</h4>
          <ul className="rp-memory-list">
            {lastMemoryMatches.map((m) => (
              <li key={m.id} className="rp-memory-item">
                <div className="rp-memory-text">{m.text}</div>
                {m.tags && m.tags.length > 0 && (
                  <div className="rp-memory-tags">
                    {m.tags.map((tag) => (
                      <span key={tag} className="rp-tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );

  const renderPlaylistsTab = () => (
    <div className="rp-section">
      <div className="rp-playlist-header">
        <h3 className="rp-section-title">Playlists</h3>
        <select
          className="rp-select"
          value={playlistSlug}
          onChange={(e) => setPlaylistSlug(e.target.value)}
        >
          {PLAYLIST_OPTIONS.map((opt) => (
            <option key={opt.slug} value={opt.slug}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {playlistLoading && <p className="rp-help-text">Loading playlist…</p>}

      {!playlistLoading && playlistItems.length === 0 && (
        <p className="rp-help-text">
          No items in this playlist yet. Ask Tamor to add something.
        </p>
      )}

      <div className="rp-playlist-grid">
        {playlistItems.map((item, idx) => (
          <div key={idx} className="rp-playlist-card">
            {item.poster && (
              <div className="rp-poster-wrapper">
                <img
                  src={item.poster}
                  alt={item.title}
                  className="rp-poster-image"
                />
              </div>
            )}
            <div className="rp-playlist-body">
              <div className="rp-playlist-title-row">
                <h4 className="rp-playlist-title">{item.title}</h4>
                <button
                  className="rp-icon-button"
                  type="button"
                  onClick={() => handleRemoveFromPlaylist(item.title)}
                  title="Remove from playlist"
                >
                  🗑️
                </button>
              </div>
              {item.overview && (
                <p className="rp-playlist-overview">{item.overview}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderFilesTab = () => (
    <div className="rp-section">
      <h3 className="rp-section-title">Project files</h3>

      {!currentProjectId && (
        <p className="rp-help-text">
          Select a project to see and attach files.
        </p>
      )}

      {currentProjectId && (
        <>
          {/* Keyword search (fast substring) */}
          <h4 className="rp-section-subtitle">Keyword search</h4>
          <div className="rp-search-row">
            <input
              className="rp-input"
              type="text"
              placeholder='Search files for… (e.g., "louver", "WidthMM")'
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleSearchProjectFiles();
                }
              }}
            />
            <button
              className="rp-button"
              type="button"
              onClick={handleSearchProjectFiles}
              disabled={searchLoading || !searchQuery.trim()}
            >
              {searchLoading ? "Searching…" : "Search"}
            </button>
          </div>
          {searchError && (
            <div className="rp-status-text error">{searchError}</div>
          )}
          {searchResults.length > 0 && (
            <div className="rp-search-results">
              <ul className="rp-file-list">
                {searchResults.map((hit) => (
                  <li
                    key={`${hit.file_id}-${hit.line_number}`}
                    className="rp-file-item"
                    data-file-id={hit.file_id}
                    onClick={() => {
                      const file =
                        files.find((f) => f.id === hit.file_id) || null;
                      if (file) setSelectedFile(file);
                      window.dispatchEvent(
                        new CustomEvent("tamor-scroll-to-file", {
                          detail: { fileId: hit.file_id },
                        })
                      );
                    }}
                  >
                    <div className="rp-file-main">
                      <span className="rp-file-icon">
                        {getFileEmoji(hit.filename, hit.mime_type)}
                      </span>
                      <div className="rp-file-text">
                        <div className="rp-file-name">
                          {hit.filename}
                          <span className="rp-file-meta-small">
                            {" "}
                            • {hit.matches} match
                            {hit.matches !== 1 ? "es" : ""}
                          </span>
                        </div>
                        <div className="rp-file-meta rp-snippet">
                          <HighlightedSnippet
                            snippet={hit.snippet}
                            query={searchQuery}
                          />
                        </div>
                      </div>
                    </div>
                    <div className="rp-file-actions">
                      <a
                        href={`${API_BASE}/files/${hit.file_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rp-button subtle"
                        onClick={(e) => e.stopPropagation()}
                      >
                        Open
                      </a>
                      <button
                        className="rp-button subtle"
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          const file =
                            files.find((f) => f.id === hit.file_id) || null;
                          if (file) {
                            setSelectedFile(file);
                            handleSummarizeFile(file);
                          }
                        }}
                      >
                        Summarize / explain
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="rp-divider" />

          {/* Semantic search (embedding + LLM) */}
          <h4 className="rp-section-subtitle">Semantic search</h4>
          <div className="rp-search-row">
            <input
              className="rp-input"
              type="text"
              placeholder='Ask across all files… (e.g., "valid WidthMM ranges")'
              value={semanticQuery}
              onChange={(e) => setSemanticQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleSemanticSearch();
                }
              }}
            />
            <button
              className="rp-button"
              type="button"
              onClick={handleSemanticSearch}
              disabled={semanticLoading || !semanticQuery.trim()}
            >
              {semanticLoading ? "Searching…" : "Search semantically"}
            </button>
          </div>
          {semanticError && (
            <div className="rp-status-text error">{semanticError}</div>
          )}
          {!semanticLoading &&
            semanticQuery.trim() &&
            semanticResults.length === 0 &&
            !semanticError && (
              <p className="rp-help-text">
                No semantic hits found for <strong>{semanticQuery}</strong>.
              </p>
            )}
          {semanticResults.length > 0 && (
            <div className="rp-search-results">
              <ul className="rp-file-list">
                {semanticResults.map((hit) => (
                  <li
                    key={`${hit.chunk_id}-${hit.file_id}-${hit.chunk_index}`}
                    className="rp-file-item"
                    data-file-id={hit.file_id}
                    onClick={() => {
                      const file =
                        files.find((f) => f.id === hit.file_id) || null;
                      if (file) setSelectedFile(file);
                      window.dispatchEvent(
                        new CustomEvent("tamor-scroll-to-file", {
                          detail: { fileId: hit.file_id },
                        })
                      );
                    }}
                  >
                    <div className="rp-file-main">
                      <span className="rp-file-icon">
                        {getFileEmoji(hit.filename, hit.mime_type)}
                      </span>
                      <div className="rp-file-text">
                        <div className="rp-file-name">
                          {hit.filename}
                          <span className="rp-file-meta-small">
                            {" "}
                            • semantic hit
                          </span>
                        </div>
                        {hit.snippet && (
                          <div className="rp-file-meta rp-snippet">
                            {hit.snippet}
                          </div>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="rp-divider" />

          {/* Project-wide summary */}
          <h4 className="rp-section-subtitle">Project summary</h4>
          <textarea
            className="rp-notes-textarea"
            value={projectSummaryPrompt}
            onChange={(e) => setProjectSummaryPrompt(e.target.value)}
            rows={3}
          />
          <div className="rp-search-row">
            <button
              className="rp-button"
              type="button"
              onClick={handleProjectSummary}
              disabled={projectSummaryLoading}
            >
              {projectSummaryLoading ? "Summarizing…" : "Summarize project"}
            </button>
            {projectSummaryText && (
              <button
                className="rp-button subtle"
                type="button"
                onClick={handleInjectSummaryToChat}
              >
                Send summary to chat
              </button>
            )}
          </div>
          {projectSummaryError && (
            <div className="rp-status-text error">{projectSummaryError}</div>
          )}
          {projectSummaryText && (
            <div className="rp-summary-preview">
              <pre>{projectSummaryText}</pre>
            </div>
          )}

          <div className="rp-divider" />

          {/* Upload + file list */}
          <label className="rp-button">
            {uploading ? "Uploading…" : "Attach file"}
            <input
              type="file"
              style={{ display: "none" }}
              onChange={handleFileInputChange}
              disabled={uploading}
            />
          </label>

          {uploadError && (
            <div className="rp-status-text error">{uploadError}</div>
          )}
          {uploadSuccess && (
            <div className="rp-status-text success">{uploadSuccess}</div>
          )}

          <div className="rp-divider" />

          {filesLoading && <p className="rp-help-text">Loading files…</p>}

          {!filesLoading && files.length === 0 && (
            <p className="rp-help-text">
              No files yet. Attach specs, PDFs, screenshots, or code here.
            </p>
          )}

          {!filesLoading && files.length > 0 && (
            <ul className="rp-file-list">
              {files.map((f) => (
                <li
                  key={f.id}
                  className={
                    selectedFile && selectedFile.id === f.id
                      ? "rp-file-item selected"
                      : "rp-file-item"
                  }
                  data-file-id={f.id}
                  onClick={() => setSelectedFile(f)}
                >
                  <div className="rp-file-main">
                    <span className="rp-file-icon">
                      {getFileEmoji(f.filename, f.mime_type)}
                    </span>
                    <div className="rp-file-text">
                      <div className="rp-file-name">{f.filename}</div>
                      <div className="rp-file-meta">
                        {f.mime_type || "unknown type"}
                        {typeof f.size_bytes === "number" && (
                          <> • {(f.size_bytes / 1024).toFixed(1)} KB</>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="rp-file-actions">
                    <button
                      className="rp-button subtle"
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSummarizeFile(f);
                      }}
                    >
                      Summarize / explain
                    </button>
                    <button
                      className="rp-button subtle danger"
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteFile(f.id);
                      }}
                    >
                      Delete
                    </button>
                  </div>

                  {/* Tiny inline thumbnail for images */}
                  {f.mime_type?.startsWith("image/") && (
                    <div className="rp-file-thumb">
                      <img
                        src={`${API_BASE}/files/${f.id}`}
                        alt={f.filename}
                      />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          {/* Inline content preview panel */}
          {selectedFile && (
            <div className="rp-inline-preview">
              <div className="rp-inline-preview-header">
                <div className="rp-inline-preview-title">
                  {selectedFile.filename}
                </div>
                <div className="rp-inline-preview-meta">
                  {selectedFile.mime_type || "unknown type"}
                  {typeof selectedFile.size_bytes === "number" && (
                    <> • {(selectedFile.size_bytes / 1024).toFixed(1)} KB</>
                  )}
                </div>
              </div>

              {/* Image preview */}
              {selectedFile.mime_type?.startsWith("image/") && (
                <div className="rp-inline-preview-image-wrap">
                  <img
                    src={`${API_BASE}/files/${selectedFile.id}`}
                    alt={selectedFile.filename}
                    className="rp-inline-preview-image"
                  />
                </div>
              )}

              {/* Text / code preview */}
              {!selectedFile.mime_type?.startsWith("image/") &&
                isTextLikeFile(selectedFile) && (
                  <div className="rp-inline-preview-text">
                    {contentPreview.loading && (
                      <p className="rp-help-text">Loading preview…</p>
                    )}
                    {contentPreview.error && (
                      <p className="rp-status-text error">
                        {contentPreview.error}
                      </p>
                    )}
                    {!contentPreview.loading && !contentPreview.error && (
                      <pre>{contentPreview.text}</pre>
                    )}
                    {contentPreview.truncated && (
                      <p className="rp-help-text">
                        Preview truncated for very large files.
                      </p>
                    )}
                  </div>
                )}

              {!selectedFile.mime_type?.startsWith("image/") &&
                !isTextLikeFile(selectedFile) && (
                  <div className="rp-help-text">
                    This file type can’t be previewed inline yet, but you can
                    still open or summarize it.
                  </div>
                )}
            </div>
          )}

          {/* LLM analysis (summary / QA) */}
          {previewFileId && (
            <div className="rp-file-preview">
              <div className="rp-file-preview-header">
                <span className="rp-file-preview-title">
                  {previewMode === "qa"
                    ? `Answers from: ${previewFileName}`
                    : `Summary for: ${previewFileName}`}
                </span>
                <button
                  className="rp-button subtle"
                  type="button"
                  onClick={clearPreview}
                >
                  Clear
                </button>
              </div>

              <div className="rp-file-preview-body">
                <textarea
                  className="rp-input"
                  rows={previewMode === "qa" ? 3 : 4}
                  placeholder={
                    previewMode === "qa"
                      ? "Ask a question about this file…"
                      : "Short summary or notes for this file…"
                  }
                  value={fileQuery}
                  onChange={(e) => setFileQuery(e.target.value)}
                />
                <div className="rp-search-row">
                  <button
                    className="rp-button"
                    type="button"
                    onClick={handleAskAboutFile}
                    disabled={!fileQuery.trim() || previewLoading}
                  >
                    {previewLoading ? "Asking…" : "Ask"}
                  </button>
                </div>
                {previewAnswer && (
                  <div className="rp-project-summary-preview">
                    <pre>{previewAnswer}</pre>
                  </div>
                )}
                <p className="rp-help-text">
                  Tamor reads only this file’s text (truncated if very large) to
                  answer. For binary formats (PDF, Word, etc.), you’ll get a
                  basic text extraction until richer parsers are wired in.
                </p>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );

  const renderKnowledgeTab = () => (
    <div className="rp-section">
      <h3 className="rp-section-title">Knowledge graph</h3>

      {!currentProjectId && (
        <p className="rp-help-text">
          Select a project to extract symbols and config keys from its files.
        </p>
      )}

      {currentProjectId && (
        <>
          <h4 className="rp-section-subtitle">Extract symbols</h4>
          <p className="rp-help-text">
            Tamor will scan all text-like files in this project for config keys,
            parameters, and function/class names, then index them for fast
            lookup.
          </p>
          <div className="rp-search-row">
            <button
              type="button"
              className="rp-button"
              onClick={handleKnowledgeExtract}
              disabled={knowledgeLoading}
            >
              {knowledgeLoading ? "Indexing…" : "Extract / refresh symbols"}
            </button>
            {knowledgeStats && (
              <span className="rp-status-text">
                Indexed {knowledgeStats.files_with_symbols}/
                {knowledgeStats.files_scanned} files,{" "}
                {knowledgeStats.symbols_written} symbols.
              </span>
            )}
          </div>
          {knowledgeError && (
            <div className="rp-status-text error">{knowledgeError}</div>
          )}

          <div className="rp-divider" />

          <h4 className="rp-section-subtitle">Search symbols</h4>
          <div className="rp-search-row">
            <input
              className="rp-input"
              type="text"
              placeholder='Search symbols… (e.g., "WidthMM", "MotorSide")'
              value={symbolQuery}
              onChange={(e) => setSymbolQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleKnowledgeSearch();
                }
              }}
            />
            <button
              className="rp-button"
              type="button"
              onClick={handleKnowledgeSearch}
              disabled={knowledgeLoading || !symbolQuery.trim()}
            >
              {knowledgeLoading ? "Searching…" : "Search symbols"}
            </button>
          </div>

          {symbolQuery.trim() &&
            !knowledgeLoading &&
            symbolResults.length === 0 &&
            !knowledgeError && (
              <p className="rp-help-text">
                No symbols found matching <strong>{symbolQuery}</strong>.
              </p>
            )}

          {symbolResults.length > 0 && (
            <div className="rp-search-results">
              <ul className="rp-file-list">
                {symbolResults.map((hit) => (
                  <li
                    key={
                      hit.id ||
                      `${hit.file_id}-${hit.symbol}-${hit.line_number}`
                    }
                    className="rp-file-item"
                    data-file-id={hit.file_id}
                    onClick={() => {
                      const file =
                        files.find((f) => f.id === hit.file_id) || null;
                      if (file) setSelectedFile(file);
                      window.dispatchEvent(
                        new CustomEvent("tamor-scroll-to-file", {
                          detail: { fileId: hit.file_id },
                        })
                      );
                    }}
                  >
                    <div className="rp-file-main">
                      <span className="rp-file-icon">
                        {getFileEmoji(hit.filename, hit.mime_type)}
                      </span>
                      <div className="rp-file-text">
                        <div className="rp-file-name">
                          {hit.symbol}
                          <span className="rp-file-meta-small">
                            {" "}
                            • {hit.filename} @ line {hit.line_number}
                          </span>
                        </div>
                        {hit.snippet && (
                          <div className="rp-file-meta rp-snippet">
                            <HighlightedSnippet
                              snippet={hit.snippet}
                              query={symbolQuery}
                            />
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="rp-file-actions">
                      <button
                        className="rp-button subtle"
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleAskSymbolInChat(hit);
                        }}
                      >
                        Ask in chat
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );

  return (
    <div className="RightPanelRoot">
      <div className="rp-tabs">
        <button
          className={activeTab === "workspace" ? "rp-tab active" : "rp-tab"}
          onClick={() => setActiveTab("workspace")}
        >
          Workspace
        </button>
        <button
          className={activeTab === "playlists" ? "rp-tab active" : "rp-tab"}
          onClick={() => setActiveTab("playlists")}
        >
          Playlists
        </button>
        <button
          className={activeTab === "files" ? "rp-tab active" : "rp-tab"}
          onClick={() => setActiveTab("files")}
        >
          Files
        </button>
        <button
          className={activeTab === "knowledge" ? "rp-tab active" : "rp-tab"}
          onClick={() => setActiveTab("knowledge")}
        >
          Knowledge
        </button>
      </div>

      <div className="rp-body">
        {activeTab === "workspace" && renderWorkspaceTab()}
        {activeTab === "playlists" && renderPlaylistsTab()}
        {activeTab === "files" && renderFilesTab()}
        {activeTab === "knowledge" && renderKnowledgeTab()}
      </div>
    </div>
  );
}

