// src/components/RightPanel/RightPanel.jsx
import "./RightPanel.css";
import { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";

const PLAYLIST_OPTIONS = [
  { slug: "christmas", label: "Christmas" },
  { slug: "thanksgiving", label: "Thanksgiving" },
  { slug: "favorites", label: "Favorites" },
  { slug: "kids", label: "Kids" },
];

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
  if (name.match(/\.(mp4|mov|mkv|webm)$/) || mime.startsWith("video/")) {
    return "🎬";
  }
  if (name.match(/\.(mp3|wav|flac|m4a)$/) || mime.startsWith("audio/")) {
    return "🎵";
  }
  if (name.match(/\.(xls|xlsx|csv)$/)) return "📊";
  if (name.match(/\.(doc|docx)$/)) return "📝";
  if (name.match(/\.(zip|rar|7z)$/)) return "🗜️";
  if (
    name.match(
      /\.(js|ts|jsx|tsx|py|rb|go|java|c|cpp|cs|php|html|css|json|yml|yaml)$/
    )
  ) {
    return "💻";
  }

  return "📁";
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

  // File analysis
  const [previewFileId, setPreviewFileId] = useState(null);
  const [previewFileName, setPreviewFileName] = useState("");
  const [previewText, setPreviewText] = useState("");
  const [previewMode, setPreviewMode] = useState("summary");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [fileQuery, setFileQuery] = useState("");

  // Project-wide file search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");

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
      setNotesStatus("Saved.");
    } catch (err) {
      console.error("Failed to save notes:", err);
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
      return;
    }

    async function fetchFiles() {
      try {
        setFilesLoading(true);
        setUploadError("");
        setUploadSuccess("");
        const data = await apiFetch(`/projects/${currentProjectId}/files`);
        setFiles(data.files || []);
      } catch (err) {
        console.error("Failed to load project files:", err);
      } finally {
        setFilesLoading(false);
      }
    }

    fetchFiles();
  }, [activeTab, currentProjectId, conversationRefreshToken, filesRefreshToken]);

  // Clear search when switching projects
  useEffect(() => {
    setSearchQuery("");
    setSearchResults([]);
    setSearchError("");
    setSearchLoading(false);
  }, [currentProjectId]);

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

      const response = await fetch("/api/files/upload", {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(
          errData.error || `Upload failed with status ${response.status}`
        );
      }

      const data = await response.json();
      const uploaded = data.file || data;

      setUploadSuccess(`Uploaded ${uploaded.filename || file.name}.`);
      setFilesRefreshToken((prev) => prev + 1);
    } catch (err) {
      console.error("File upload error:", err);
      setUploadError(err.message || "File upload failed.");
    } finally {
      setUploading(false);
      setTimeout(() => {
        setUploadError("");
        setUploadSuccess("");
      }, 3000);
    }
  };

  const handleDeleteFile = async (fileId) => {
    if (!fileId) return;

    setFiles((prev) => prev.filter((f) => f.id !== fileId));

    try {
      await apiFetch(`/files/${fileId}`, {
        method: "DELETE",
      });
    } catch (err) {
      console.error("Failed to delete file:", err);
      setFilesRefreshToken((prev) => prev + 1);
    }
  };

  // --- Inject summaries / QA into chat -------------------------------------

  const injectIntoChat = async (rawText, file, task, query) => {
    if (!activeConversationId || !rawText) return;

    const filename = file?.filename || "attached file";

    let content;
    if (task === "qa" && query) {
      content = `Answer based on file "${filename}":\n\nQ: ${query}\n\n${rawText}`;
    } else {
      content = `Here is the summary of file "${filename}":\n\n${rawText}`;
    }

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

  const fetchFileAnalysis = async (fileId, file, mode, queryText = "") => {
    setPreviewLoading(true);
    setPreviewMode(mode);
    setPreviewText("");

    try {
      const data = await apiFetch(`/files/${fileId}/summarize`, {
        method: "POST",
        body: {
          task: mode === "qa" ? "qa" : "summary",
          query: queryText || null,
        },
      });

      const result =
        data.result || data.summary || "(No response from analysis.)";

      setPreviewText(result);

      await injectIntoChat(
        result,
        file,
        mode === "qa" ? "qa" : "summary",
        queryText
      );
    } catch (err) {
      console.error("Failed to analyze file:", err);
      setPreviewText(`(Error analyzing file: ${err.message})`);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleSummarizeFile = (file) => {
    if (!file?.id) return;
    setPreviewFileId(file.id);
    setPreviewFileName(file.filename);
    setFileQuery("");
    fetchFileAnalysis(file.id, file, "summary");
  };

  const handleAskAboutFile = () => {
    if (!previewFileId || !fileQuery.trim()) return;
    const file = files.find((f) => f.id === previewFileId) || null;
    fetchFileAnalysis(previewFileId, file, "qa", fileQuery.trim());
  };

  const clearPreview = () => {
    setPreviewFileId(null);
    setPreviewFileName("");
    setPreviewText("");
    setPreviewMode("summary");
    setFileQuery("");
    setPreviewLoading(false);
  };

  // --- Project-wide search --------------------------------------------------

  const handleSearchProjectFiles = async () => {
    const q = searchQuery.trim();
    if (!q || !currentProjectId) {
      setSearchResults([]);
      setSearchError(q ? "" : "");
      return;
    }

    setSearchLoading(true);
    setSearchError("");
    setSearchResults([]);

    try {
      const data = await apiFetch(`/projects/${currentProjectId}/files/search`, {
        method: "POST",
        body: { query: q },
      });
      setSearchResults(data.hits || []);
    } catch (err) {
      console.error("File search error:", err);
      setSearchError(err.message || "File search failed.");
    } finally {
      setSearchLoading(false);
    }
  };

  const handleSearchHitAsk = (hit) => {
    if (!hit || !hit.file_id) return;
    const file = files.find((f) => f.id === hit.file_id) || {
      id: hit.file_id,
      filename: hit.filename,
      mime_type: hit.mime_type,
    };

    setPreviewFileId(file.id);
    setPreviewFileName(file.filename);
    setFileQuery(searchQuery);
    fetchFileAnalysis(file.id, file, "qa", searchQuery.trim());
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
            rows={10}
          />
          <div className="rp-notes-actions">
            <button
              className="rp-button"
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

      <div className="rp-divider" />

      <h4 className="rp-section-subtitle">Recent memory hits</h4>
      {(!lastMemoryMatches || lastMemoryMatches.length === 0) && (
        <p className="rp-help-text">
          Tamor will surface relevant memories here as you chat.
        </p>
      )}
      {lastMemoryMatches && lastMemoryMatches.length > 0 && (
        <ul className="rp-memory-list">
          {lastMemoryMatches.map((m, idx) => (
            <li key={idx} className="rp-memory-item">
              <div className="rp-memory-score">
                {(m.score * 100).toFixed(1)}%
              </div>
              <div className="rp-memory-snippet">{m.text}</div>
            </li>
          ))}
        </ul>
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
          {PLAYLIST_OPTIONS.map((p) => (
            <option key={p.slug} value={p.slug}>
              {p.label}
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
                  className="rp-poster"
                />
              </div>
            )}
            <div className="rp-playlist-meta">
              <div className="rp-playlist-title">
                {item.title}
                {item.year && <span className="rp-year"> ({item.year})</span>}
              </div>
              {item.overview && (
                <div className="rp-overview">{item.overview}</div>
              )}
              <div className="rp-playlist-actions">
                {item.imdb_id && (
                  <a
                    href={`https://www.imdb.com/title/${item.imdb_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rp-link"
                  >
                    IMDB
                  </a>
                )}
                {item.tmdb_id && (
                  <a
                    href={`https://www.themoviedb.org/movie/${item.tmdb_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rp-link"
                  >
                    TMDb
                  </a>
                )}
                <button
                  className="rp-button subtle"
                  onClick={() => handleRemoveFromPlaylist(item.title)}
                >
                  Remove
                </button>
              </div>
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
          {/* Search bar */}
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
              className="rp-button subtle"
              type="button"
              onClick={handleSearchProjectFiles}
            >
              Search
            </button>
          </div>
          {searchLoading && (
            <p className="rp-help-text">Searching project files…</p>
          )}
          {searchError && (
            <p className="rp-status-text error">{searchError}</p>
          )}
          {!searchLoading &&
            searchQuery.trim() &&
            searchResults.length === 0 &&
            !searchError && (
              <p className="rp-help-text">
                No matches found for <strong>{searchQuery}</strong>.
              </p>
            )}
          {searchResults.length > 0 && (
            <div className="rp-search-results">
              <h4 className="rp-section-subtitle">
                Matches for “{searchQuery}”
              </h4>
              <ul className="rp-file-list">
                {searchResults.map((hit) => (
                  <li key={`${hit.file_id}-${hit.snippet}`} className="rp-file-item">
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
                        href={`/api/files/${hit.file_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rp-button subtle"
                      >
                        Open
                      </a>
                      <button
                        className="rp-button subtle"
                        type="button"
                        onClick={() => handleSearchHitAsk(hit)}
                        disabled={!activeConversationId}
                        title={
                          activeConversationId
                            ? "Ask Tamor about this usage in chat"
                            : "Select or start a conversation first"
                        }
                      >
                        Ask in chat
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
              <div className="rp-divider" />
            </div>
          )}

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
                <li key={f.id} className="rp-file-item">
                  <div className="rp-file-main">
                    <span className="rp-file-icon">
                      {getFileEmoji(f.filename, f.mime_type)}
                    </span>
                    <div className="rp-file-text">
                      <a
                        href={`/api/files/${f.id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rp-file-name"
                      >
                        {f.filename}
                      </a>
                      <div className="rp-file-meta">
                        {typeof f.size_bytes === "number" && (
                          <span>{(f.size_bytes / 1024).toFixed(1)} KB</span>
                        )}
                        {f.created_at && (
                          <span>
                            {" • "}
                            {new Date(f.created_at).toLocaleString()}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="rp-file-actions">
                    <button
                      className="rp-button subtle"
                      type="button"
                      onClick={() => handleSummarizeFile(f)}
                    >
                      Summarize / explain
                    </button>
                    <button
                      className="rp-button subtle danger"
                      type="button"
                      onClick={() => handleDeleteFile(f.id)}
                    >
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}

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

              {previewLoading && (
                <p className="rp-help-text">Thinking over that file…</p>
              )}

              {!previewLoading && previewText && (
                <pre className="rp-file-preview-body">{previewText}</pre>
              )}

              <div className="rp-file-preview-controls">
                <div className="rp-file-preview-row">
                  <label className="rp-file-preview-label">
                    Ask about this file:
                  </label>
                  <input
                    type="text"
                    className="rp-input"
                    placeholder='e.g., "Where do we set the louver spacing?"'
                    value={fileQuery}
                    onChange={(e) => setFileQuery(e.target.value)}
                  />
                  <button
                    className="rp-button subtle"
                    type="button"
                    onClick={handleAskAboutFile}
                    disabled={!fileQuery.trim() || previewLoading}
                  >
                    Ask
                  </button>
                </div>
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
      </div>

      <div className="rp-body">
        {activeTab === "workspace" && renderWorkspaceTab()}
        {activeTab === "playlists" && renderPlaylistsTab()}
        {activeTab === "files" && renderFilesTab()}
      </div>
    </div>
  );
}

