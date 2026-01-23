// src/components/RightPanel/tabs/ViewerTab.jsx
import React, { useEffect, useState } from "react";
import { apiFetch, API_BASE } from "../../../api/client";
import { useDevMode } from "../../../context/DevModeContext";
import StructurePanel from "../components/StructurePanel.jsx";

function ViewerTab({ currentProjectId, viewerSelectedFileId, viewerSelectedPage }) {
  const { devMode } = useDevMode();
  const [files, setFiles] = useState([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [filesError, setFilesError] = useState("");

  // always store file IDs as strings
  const [selectedFileId, setSelectedFileId] = useState("");

  // optional forced page (when coming from Search)
  const [forcedPage, setForcedPage] = useState(null);

  // structure state (reuse same pattern as FilesTab)
  const [structureFileId, setStructureFileId] = useState(null);
  const [structureLoading, setStructureLoading] = useState(false);
  const [structureError, setStructureError] = useState("");
  const [structureData, setStructureData] = useState(null);

  useEffect(() => {
    if (!currentProjectId) {
      setFiles([]);
      setFilesError("");
      setFilesLoading(false);
      setSelectedFileId("");
      setForcedPage(null);
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
        const list = (data && data.files) || [];
        setFiles(list);

        if (viewerSelectedFileId) {
          // if we came here from Search, prefer that file
          const exists = list.some(
            (f) => String(f.id) === String(viewerSelectedFileId)
          );
          if (exists) {
            setSelectedFileId(String(viewerSelectedFileId));
            setForcedPage(
              typeof viewerSelectedPage === "number" && viewerSelectedPage > 0
                ? viewerSelectedPage
                : null
            );
            return;
          }
        }

        // otherwise default to first file
        if (list.length > 0) {
          setSelectedFileId(String(list[0].id));
          setForcedPage(null);
        } else {
          setSelectedFileId("");
          setForcedPage(null);
        }
      } catch (err) {
        console.error("Failed to fetch project files for viewer", err);
        setFilesError("Error loading files");
      } finally {
        setFilesLoading(false);
      }
    };

    fetchFiles();
  }, [currentProjectId, viewerSelectedFileId, viewerSelectedPage]);

  useEffect(() => {
    // whenever selected file changes, reset structure info
    setStructureFileId(null);
    setStructureData(null);
    setStructureError("");
    setStructureLoading(false);
  }, [selectedFileId]);

  // when Search chooses a file + page after files are already loaded
  useEffect(() => {
    if (!viewerSelectedFileId) return;
    if (!files || files.length === 0) return;

    const exists = files.some(
      (f) => String(f.id) === String(viewerSelectedFileId)
    );
    if (!exists) return;

    setSelectedFileId(String(viewerSelectedFileId));
    setForcedPage(
      typeof viewerSelectedPage === "number" && viewerSelectedPage > 0
        ? viewerSelectedPage
        : null
    );
  }, [viewerSelectedFileId, viewerSelectedPage, files]);

  const handleSelectFile = (fileId) => {
    setSelectedFileId(fileId);
    setForcedPage(null); // user manually changed file; don't force a page anymore
  };

  const handleLoadStructure = async () => {
    if (!selectedFileId || !currentProjectId) return;

    setStructureFileId(selectedFileId);
    setStructureLoading(true);
    setStructureError("");
    setStructureData(null);

    try {
      const data = await apiFetch(`/files/${selectedFileId}/content`);
      const meta = data.meta || {};
      const structure = meta.structure || null;
      setStructureData(structure);
    } catch (err) {
      console.error("Failed to load file structure (viewer)", err);
      setStructureError("Error loading file structure");
    } finally {
      setStructureLoading(false);
    }
  };

  const selectedFile =
    files.find((f) => String(f.id) === String(selectedFileId)) || null;

  const buildFileUrl = (fileId) => {
    const base = `${API_BASE}/files/${fileId}/download`;
    if (forcedPage && forcedPage > 0) {
      return `${base}#page=${forcedPage}`;
    }
    return base;
  };

  return (
    <div className="rp-tab-content">
      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">File viewer</h3>
        </div>
        <div className="rp-section-body">
          {filesLoading && (
            <div className="rp-small-text">Loading files…</div>
          )}
          {filesError && <div className="rp-error">{filesError}</div>}
          {!filesLoading && files.length === 0 && (
            <div className="rp-small-text rp-muted">
              No files uploaded yet. Upload a spec to preview it here.
            </div>
          )}

          {files.length > 0 && (
            <>
              <div className="rp-search-row" style={{ marginBottom: 8 }}>
                <select
                  className="rp-input"
                  value={selectedFileId}
                  onChange={(e) => handleSelectFile(e.target.value)}
                >
                  {files.map((f) => (
                    <option key={f.id} value={String(f.id)}>
                      {f.filename}
                    </option>
                  ))}
                </select>
                {selectedFile && (
                  <a
                    className="rp-button subtle"
                    href={buildFileUrl(selectedFile.id)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Open in new tab
                  </a>
                )}
              </div>

              {selectedFile && (
                <div style={{ marginTop: 8 }}>
                  <div
                    className="rp-small-text rp-muted"
                    style={{ marginBottom: 6 }}
                  >
                    Inline preview (best for PDFs and text-like formats)
                    {forcedPage && (
                      <span> — jumped to page {forcedPage}</span>
                    )}
                  </div>
                  <iframe
                    title={`Preview: ${selectedFile.filename}`}
                    src={buildFileUrl(selectedFile.id)}
                    style={{
                      width: "100%",
                      height: "420px",
                      border: "1px solid #333",
                      borderRadius: "4px",
                    }}
                  />
                  {devMode && (
                    <div style={{ marginTop: 8 }}>
                      <button
                        type="button"
                        className="rp-button subtle"
                        onClick={handleLoadStructure}
                        disabled={structureLoading}
                      >
                        {structureLoading
                          ? "Loading structure…"
                          : "Show structure"}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Structure details for the selected file (dev mode only) */}
      {devMode && (
        <StructurePanel
          structureFileId={structureFileId}
          structureLoading={structureLoading}
          structureError={structureError}
          structureData={structureData}
        />
      )}
    </div>
  );
}

export default ViewerTab;

