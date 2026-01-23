// src/components/RightPanel/tabs/PluginsTab.jsx
import React, { useState, useEffect, useRef } from "react";
import { apiFetch, API_BASE } from "../../../api/client";

function PluginsTab({ currentProjectId }) {
  // Tab state: "importers", "exporters", "references"
  const [activeTab, setActiveTab] = useState("importers");

  // Importers state
  const [importers, setImporters] = useState([]);
  const [loadingImporters, setLoadingImporters] = useState(false);
  const [selectedImporter, setSelectedImporter] = useState(null);
  const [importerConfig, setImporterConfig] = useState({});
  const [importMode, setImportMode] = useState("upload");
  const [previewItems, setPreviewItems] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [selectedItemIds, setSelectedItemIds] = useState(null);
  const fileInputRef = useRef(null);

  // Exporters state
  const [exporters, setExporters] = useState([]);
  const [loadingExporters, setLoadingExporters] = useState(false);
  const [selectedExporter, setSelectedExporter] = useState(null);
  const [exporterConfig, setExporterConfig] = useState({});
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState(null);

  // References state
  const [references, setReferences] = useState([]);
  const [loadingReferences, setLoadingReferences] = useState(false);
  const [selectedReference, setSelectedReference] = useState(null);
  const [referenceConfig, setReferenceConfig] = useState({});
  const [refItems, setRefItems] = useState([]);
  const [refLoading, setRefLoading] = useState(false);
  const [refError, setRefError] = useState("");
  const [selectedRefItem, setSelectedRefItem] = useState(null);
  const [fetchedContent, setFetchedContent] = useState(null);
  const [fetching, setFetching] = useState(false);

  // Error state
  const [error, setError] = useState("");

  // Load data on mount
  useEffect(() => {
    loadImporters();
    loadExporters();
    loadReferences();
  }, []);

  // Reset state when project changes
  useEffect(() => {
    setSelectedImporter(null);
    setImporterConfig({});
    setPreviewItems([]);
    setImportResult(null);
    setSelectedItemIds(null);
    setSelectedExporter(null);
    setExporterConfig({});
    setExportResult(null);
    setSelectedReference(null);
    setReferenceConfig({});
    setRefItems([]);
    setSelectedRefItem(null);
    setFetchedContent(null);
  }, [currentProjectId]);

  // ---------------------------------------------------------------------------
  // Load Functions
  // ---------------------------------------------------------------------------

  const loadImporters = async () => {
    setLoadingImporters(true);
    setError("");
    try {
      const data = await apiFetch("/plugins");
      setImporters(data.plugins || []);
    } catch (err) {
      console.error("Failed to load importers", err);
      setError(err.message || "Failed to load importers");
    } finally {
      setLoadingImporters(false);
    }
  };

  const loadExporters = async () => {
    setLoadingExporters(true);
    try {
      const data = await apiFetch("/plugins/exporters");
      setExporters(data.exporters || []);
    } catch (err) {
      console.error("Failed to load exporters", err);
    } finally {
      setLoadingExporters(false);
    }
  };

  const loadReferences = async () => {
    setLoadingReferences(true);
    try {
      const data = await apiFetch("/plugins/references");
      setReferences(data.references || []);
    } catch (err) {
      console.error("Failed to load references", err);
    } finally {
      setLoadingReferences(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Importer Functions
  // ---------------------------------------------------------------------------

  const handleSelectImporter = (plugin) => {
    setSelectedImporter(plugin);
    const initialConfig = {};
    if (plugin.config_schema) {
      Object.entries(plugin.config_schema).forEach(([key, schema]) => {
        if (schema.default !== undefined) {
          initialConfig[key] = schema.default;
        }
      });
    }
    setImporterConfig(initialConfig);
    setPreviewItems([]);
    setImportResult(null);
    setSelectedItemIds(null);
  };

  const handleImporterConfigChange = (key, value) => {
    setImporterConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handlePreview = async () => {
    if (!selectedImporter) return;
    setPreviewLoading(true);
    setPreviewError("");
    setPreviewItems([]);
    setImportResult(null);
    setSelectedItemIds(null);

    try {
      const data = await apiFetch(`/plugins/${selectedImporter.id}/list`, {
        method: "POST",
        body: { config: importerConfig },
      });

      if (data.error) {
        setPreviewError(data.details || data.error);
      } else {
        setPreviewItems(data.items || []);
      }
    } catch (err) {
      console.error("Preview failed", err);
      setPreviewError(err.message || "Failed to list items");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleImport = async () => {
    if (!selectedImporter || !currentProjectId) return;
    setImporting(true);
    setImportResult(null);

    try {
      const body = {
        project_id: currentProjectId,
        config: importerConfig,
      };
      if (selectedItemIds && selectedItemIds.length > 0) {
        body.item_ids = selectedItemIds;
      }

      const data = await apiFetch(`/plugins/${selectedImporter.id}/import`, {
        method: "POST",
        body,
      });

      if (data.error) {
        setImportResult({ success: false, error: data.details || data.error });
      } else {
        setImportResult({ success: true, summary: data.summary, results: data.results });
      }
    } catch (err) {
      console.error("Import failed", err);
      setImportResult({ success: false, error: err.message || "Import failed" });
    } finally {
      setImporting(false);
    }
  };

  const handleFileSelect = () => {
    fileInputRef.current?.click();
  };

  const handleFileUpload = async (event) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    if (!selectedImporter || !currentProjectId) return;

    setImporting(true);
    setImportResult(null);

    try {
      const formData = new FormData();
      formData.append("project_id", currentProjectId);
      for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
      }

      const response = await fetch(
        `${API_BASE}/plugins/${selectedImporter.id}/upload-import`,
        { method: "POST", body: formData, credentials: "include" }
      );

      const data = await response.json();

      if (data.error) {
        setImportResult({ success: false, error: data.details || data.error });
      } else {
        setImportResult({ success: true, summary: data.summary, results: data.results });
      }
    } catch (err) {
      console.error("Upload failed", err);
      setImportResult({ success: false, error: err.message || "Upload failed" });
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const getAcceptedFileTypes = () => {
    if (!selectedImporter) return "*/*";
    switch (selectedImporter.id) {
      case "audio-transcript":
        return "audio/*,video/*,.mp3,.mp4,.m4a,.wav,.webm,.ogg,.flac,.aac,.wma,.avi,.mkv,.mov,.wmv";
      case "bulk-pdf":
        return ".pdf,application/pdf";
      default:
        return "*/*";
    }
  };

  const toggleItemSelection = (itemId) => {
    if (!selectedItemIds) {
      setSelectedItemIds([itemId]);
    } else if (selectedItemIds.includes(itemId)) {
      const newIds = selectedItemIds.filter((id) => id !== itemId);
      setSelectedItemIds(newIds.length > 0 ? newIds : null);
    } else {
      setSelectedItemIds([...selectedItemIds, itemId]);
    }
  };

  const selectAllItems = () => {
    if (previewItems.length === 0) return;
    if (selectedItemIds && selectedItemIds.length === previewItems.length) {
      setSelectedItemIds(null);
    } else {
      setSelectedItemIds(previewItems.map((item) => item.id));
    }
  };

  // ---------------------------------------------------------------------------
  // Exporter Functions
  // ---------------------------------------------------------------------------

  const handleSelectExporter = (plugin) => {
    setSelectedExporter(plugin);
    const initialConfig = {};
    if (plugin.config_schema) {
      Object.entries(plugin.config_schema).forEach(([key, schema]) => {
        if (schema.default !== undefined) {
          initialConfig[key] = schema.default;
        }
      });
    }
    setExporterConfig(initialConfig);
    setExportResult(null);
  };

  const handleExporterConfigChange = (key, value) => {
    setExporterConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleExport = async () => {
    if (!selectedExporter || !currentProjectId) return;
    setExporting(true);
    setExportResult(null);

    try {
      const data = await apiFetch(`/plugins/exporters/${selectedExporter.id}/export`, {
        method: "POST",
        body: { project_id: currentProjectId, config: exporterConfig },
      });

      if (data.error || !data.success) {
        setExportResult({ success: false, error: data.error || data.details || "Export failed" });
      } else {
        setExportResult({
          success: true,
          downloadUrl: API_BASE + data.download_url,
          filename: data.filename,
          sizeBytes: data.size_bytes,
          metadata: data.metadata,
        });
      }
    } catch (err) {
      console.error("Export failed", err);
      setExportResult({ success: false, error: err.message || "Export failed" });
    } finally {
      setExporting(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Reference Functions
  // ---------------------------------------------------------------------------

  const handleSelectReference = (plugin) => {
    setSelectedReference(plugin);
    const initialConfig = {};
    if (plugin.config_schema) {
      Object.entries(plugin.config_schema).forEach(([key, schema]) => {
        if (schema.default !== undefined) {
          initialConfig[key] = schema.default;
        }
      });
    }
    setReferenceConfig(initialConfig);
    setRefItems([]);
    setRefError("");
    setSelectedRefItem(null);
    setFetchedContent(null);
  };

  const handleReferenceConfigChange = (key, value) => {
    setReferenceConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleBrowseReferences = async () => {
    if (!selectedReference) return;
    setRefLoading(true);
    setRefError("");
    setRefItems([]);
    setSelectedRefItem(null);
    setFetchedContent(null);

    try {
      const data = await apiFetch(`/plugins/references/${selectedReference.id}/list`, {
        method: "POST",
        body: { config: referenceConfig },
      });

      if (data.error || !data.success) {
        setRefError(data.error || data.details || "Failed to list items");
      } else {
        setRefItems(data.items || []);
      }
    } catch (err) {
      console.error("Browse references failed", err);
      setRefError(err.message || "Failed to list items");
    } finally {
      setRefLoading(false);
    }
  };

  const handleFetchReference = async (item) => {
    if (!selectedReference) return;
    setSelectedRefItem(item);
    setFetching(true);
    setFetchedContent(null);

    try {
      const data = await apiFetch(`/plugins/references/${selectedReference.id}/fetch`, {
        method: "POST",
        body: { item_id: item.id, config: referenceConfig },
      });

      if (data.error || !data.success) {
        setFetchedContent({ error: data.error || data.details || "Failed to fetch" });
      } else {
        setFetchedContent({
          content: data.content,
          title: data.title,
          url: data.url,
          fetchedAt: data.fetched_at,
          metadata: data.metadata,
        });
      }
    } catch (err) {
      console.error("Fetch reference failed", err);
      setFetchedContent({ error: err.message || "Failed to fetch" });
    } finally {
      setFetching(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Utility Functions
  // ---------------------------------------------------------------------------

  const formatBytes = (bytes) => {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const renderConfigField = (key, schema, config, onChange) => {
    const value = config[key] ?? schema.default ?? "";

    if (schema.type === "boolean") {
      return (
        <label key={key} className="rp-config-field rp-config-checkbox">
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(key, e.target.checked)}
          />
          <span className="rp-config-label">{key}</span>
          {schema.description && <span className="rp-config-desc">{schema.description}</span>}
        </label>
      );
    }

    if (schema.type === "array") {
      return (
        <div key={key} className="rp-config-field">
          <label className="rp-config-label">{key}</label>
          <input
            type="text"
            className="rp-input"
            placeholder={schema.description || `Comma-separated values`}
            value={Array.isArray(value) ? value.join(", ") : value}
            onChange={(e) => {
              const arr = e.target.value.split(",").map((s) => s.trim()).filter((s) => s);
              onChange(key, arr);
            }}
          />
          {schema.description && <span className="rp-config-desc">{schema.description}</span>}
        </div>
      );
    }

    return (
      <div key={key} className="rp-config-field">
        <label className="rp-config-label">{key}</label>
        <input
          type="text"
          className="rp-input"
          placeholder={schema.description || key}
          value={value}
          onChange={(e) => onChange(key, e.target.value)}
        />
        {schema.description && <span className="rp-config-desc">{schema.description}</span>}
      </div>
    );
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="rp-tab-content">
      {/* Tab Navigation */}
      <div className="rp-section">
        <div className="rp-tabs-nav" style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <button
            className={`rp-btn rp-btn-sm ${activeTab === "importers" ? "rp-btn-primary" : ""}`}
            onClick={() => setActiveTab("importers")}
          >
            Importers
          </button>
          <button
            className={`rp-btn rp-btn-sm ${activeTab === "exporters" ? "rp-btn-primary" : ""}`}
            onClick={() => setActiveTab("exporters")}
          >
            Exporters
          </button>
          <button
            className={`rp-btn rp-btn-sm ${activeTab === "references" ? "rp-btn-primary" : ""}`}
            onClick={() => setActiveTab("references")}
          >
            References
          </button>
        </div>
      </div>

      {/* Importers Tab */}
      {activeTab === "importers" && (
        <>
          {/* Importer List */}
          <div className="rp-section">
            <div className="rp-section-header">
              <h3 className="rp-section-title">Importers</h3>
              <button className="rp-btn rp-btn-sm" onClick={loadImporters} disabled={loadingImporters}>
                Refresh
              </button>
            </div>
            <div className="rp-section-body">
              {loadingImporters && <div className="rp-info-text">Loading...</div>}
              {error && <div className="rp-error-text">{error}</div>}
              {!loadingImporters && importers.length === 0 && (
                <div className="rp-info-text">No importers available.</div>
              )}
              {importers.map((plugin) => (
                <div
                  key={plugin.id}
                  className={`rp-list-item ${selectedImporter?.id === plugin.id ? "rp-list-item-selected" : ""}`}
                  onClick={() => handleSelectImporter(plugin)}
                >
                  <div className="rp-list-item-main">
                    <div className="rp-list-item-title">{plugin.name}</div>
                    <div className="rp-list-item-meta">{plugin.description}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Importer Configuration */}
          {selectedImporter && (
            <div className="rp-section">
              <div className="rp-section-header">
                <h3 className="rp-section-title">{selectedImporter.name}</h3>
                <button className="rp-btn rp-btn-sm" onClick={() => setSelectedImporter(null)}>
                  Close
                </button>
              </div>
              <div className="rp-section-body">
                <div className="rp-mode-toggle" style={{ marginBottom: 12 }}>
                  <button
                    className={`rp-btn rp-btn-sm ${importMode === "upload" ? "rp-btn-primary" : ""}`}
                    onClick={() => setImportMode("upload")}
                    style={{ marginRight: 8 }}
                  >
                    Upload from Device
                  </button>
                  <button
                    className={`rp-btn rp-btn-sm ${importMode === "server" ? "rp-btn-primary" : ""}`}
                    onClick={() => setImportMode("server")}
                  >
                    Import from Server
                  </button>
                </div>

                {importMode === "upload" && (
                  <div className="rp-upload-section">
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileUpload}
                      multiple
                      accept={getAcceptedFileTypes()}
                      style={{ display: "none" }}
                    />
                    <div className="rp-upload-dropzone" onClick={handleFileSelect}>
                      <div className="rp-upload-icon">+</div>
                      <div className="rp-upload-text">Click to select files</div>
                    </div>
                    {importing && <div className="rp-info-text" style={{ marginTop: 8 }}>Uploading...</div>}
                  </div>
                )}

                {importMode === "server" && (
                  <>
                    <div className="rp-config-form">
                      {selectedImporter.config_schema &&
                        Object.entries(selectedImporter.config_schema).map(([key, schema]) =>
                          renderConfigField(key, schema, importerConfig, handleImporterConfigChange)
                        )}
                    </div>
                    <div className="rp-button-row" style={{ marginTop: 12 }}>
                      <button
                        className="rp-btn rp-btn-primary"
                        onClick={handlePreview}
                        disabled={previewLoading}
                      >
                        {previewLoading ? "Loading..." : "Preview Items"}
                      </button>
                    </div>
                    {previewError && <div className="rp-error-text" style={{ marginTop: 8 }}>{previewError}</div>}
                  </>
                )}
              </div>
            </div>
          )}

          {/* Preview Items */}
          {selectedImporter && previewItems.length > 0 && (
            <div className="rp-section rp-section-flex">
              <div className="rp-section-header">
                <h3 className="rp-section-title">Items ({previewItems.length})</h3>
                <div className="rp-header-actions">
                  <button className="rp-btn rp-btn-sm" onClick={selectAllItems}>
                    {selectedItemIds?.length === previewItems.length ? "Deselect All" : "Select All"}
                  </button>
                  <button
                    className="rp-btn rp-btn-sm rp-btn-primary"
                    onClick={handleImport}
                    disabled={importing || !currentProjectId}
                  >
                    {importing ? "Importing..." : `Import ${selectedItemIds ? `${selectedItemIds.length} Selected` : "All"}`}
                  </button>
                </div>
              </div>
              <div className="rp-section-body rp-section-scroll">
                {previewItems.map((item) => (
                  <div
                    key={item.id}
                    className={`rp-list-item rp-list-item-compact ${selectedItemIds?.includes(item.id) ? "rp-list-item-selected" : ""}`}
                    onClick={() => toggleItemSelection(item.id)}
                  >
                    <input
                      type="checkbox"
                      checked={selectedItemIds ? selectedItemIds.includes(item.id) : false}
                      onChange={() => toggleItemSelection(item.id)}
                      onClick={(e) => e.stopPropagation()}
                      style={{ marginRight: 8 }}
                    />
                    <div className="rp-list-item-main">
                      <div className="rp-list-item-title">{item.name}</div>
                      <div className="rp-list-item-meta">
                        {item.mime_type && <span>{item.mime_type}</span>}
                        {item.size_bytes && <span> - {formatBytes(item.size_bytes)}</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Import Results */}
          {importResult && (
            <div className="rp-section">
              <div className="rp-section-header">
                <h3 className="rp-section-title">Import Results</h3>
                <button className="rp-btn rp-btn-sm" onClick={() => setImportResult(null)}>Clear</button>
              </div>
              <div className="rp-section-body">
                {!importResult.success && <div className="rp-error-text">{importResult.error}</div>}
                {importResult.success && importResult.summary && (
                  <div className="rp-import-summary">
                    <div className="rp-summary-stat">
                      <span className="rp-summary-label">Total:</span>
                      <span className="rp-summary-value">{importResult.summary.total}</span>
                    </div>
                    <div className="rp-summary-stat rp-summary-success">
                      <span className="rp-summary-label">Succeeded:</span>
                      <span className="rp-summary-value">{importResult.summary.succeeded}</span>
                    </div>
                    {importResult.summary.failed > 0 && (
                      <div className="rp-summary-stat rp-summary-failed">
                        <span className="rp-summary-label">Failed:</span>
                        <span className="rp-summary-value">{importResult.summary.failed}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* Exporters Tab */}
      {activeTab === "exporters" && (
        <>
          <div className="rp-section">
            <div className="rp-section-header">
              <h3 className="rp-section-title">Exporters</h3>
              <button className="rp-btn rp-btn-sm" onClick={loadExporters} disabled={loadingExporters}>
                Refresh
              </button>
            </div>
            <div className="rp-section-body">
              {loadingExporters && <div className="rp-info-text">Loading...</div>}
              {!loadingExporters && exporters.length === 0 && (
                <div className="rp-info-text">No exporters available.</div>
              )}
              {exporters.map((plugin) => (
                <div
                  key={plugin.id}
                  className={`rp-list-item ${selectedExporter?.id === plugin.id ? "rp-list-item-selected" : ""}`}
                  onClick={() => handleSelectExporter(plugin)}
                >
                  <div className="rp-list-item-main">
                    <div className="rp-list-item-title">{plugin.name}</div>
                    <div className="rp-list-item-meta">{plugin.description}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {selectedExporter && (
            <div className="rp-section">
              <div className="rp-section-header">
                <h3 className="rp-section-title">{selectedExporter.name}</h3>
                <button className="rp-btn rp-btn-sm" onClick={() => setSelectedExporter(null)}>
                  Close
                </button>
              </div>
              <div className="rp-section-body">
                {!currentProjectId && (
                  <div className="rp-info-text" style={{ marginBottom: 12 }}>
                    Select a project to export.
                  </div>
                )}
                <div className="rp-config-form">
                  {selectedExporter.config_schema &&
                    Object.entries(selectedExporter.config_schema).map(([key, schema]) =>
                      renderConfigField(key, schema, exporterConfig, handleExporterConfigChange)
                    )}
                </div>
                <div className="rp-button-row" style={{ marginTop: 12 }}>
                  <button
                    className="rp-btn rp-btn-primary"
                    onClick={handleExport}
                    disabled={exporting || !currentProjectId}
                  >
                    {exporting ? "Exporting..." : "Export"}
                  </button>
                </div>

                {exportResult && (
                  <div style={{ marginTop: 12 }}>
                    {!exportResult.success && <div className="rp-error-text">{exportResult.error}</div>}
                    {exportResult.success && (
                      <div className="rp-export-result">
                        <div className="rp-info-text">Export ready!</div>
                        <div style={{ marginTop: 8 }}>
                          <a
                            href={exportResult.downloadUrl}
                            className="rp-btn rp-btn-primary"
                            download={exportResult.filename}
                          >
                            Download {exportResult.filename}
                          </a>
                          <span className="rp-export-size" style={{ marginLeft: 8 }}>
                            ({formatBytes(exportResult.sizeBytes)})
                          </span>
                        </div>
                        {exportResult.metadata && (
                          <div className="rp-export-meta" style={{ marginTop: 8, fontSize: "0.85em", color: "#666" }}>
                            {exportResult.metadata.total_files !== undefined && (
                              <div>Files: {exportResult.metadata.total_files}</div>
                            )}
                            {exportResult.metadata.total_transcripts !== undefined && (
                              <div>Transcripts: {exportResult.metadata.total_transcripts}</div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* References Tab */}
      {activeTab === "references" && (
        <>
          <div className="rp-section">
            <div className="rp-section-header">
              <h3 className="rp-section-title">References</h3>
              <button className="rp-btn rp-btn-sm" onClick={loadReferences} disabled={loadingReferences}>
                Refresh
              </button>
            </div>
            <div className="rp-section-body">
              {loadingReferences && <div className="rp-info-text">Loading...</div>}
              {!loadingReferences && references.length === 0 && (
                <div className="rp-info-text">No reference plugins available.</div>
              )}
              {references.map((plugin) => (
                <div
                  key={plugin.id}
                  className={`rp-list-item ${selectedReference?.id === plugin.id ? "rp-list-item-selected" : ""}`}
                  onClick={() => handleSelectReference(plugin)}
                >
                  <div className="rp-list-item-main">
                    <div className="rp-list-item-title">{plugin.name}</div>
                    <div className="rp-list-item-meta">{plugin.description}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {selectedReference && (
            <div className="rp-section">
              <div className="rp-section-header">
                <h3 className="rp-section-title">{selectedReference.name}</h3>
                <button className="rp-btn rp-btn-sm" onClick={() => setSelectedReference(null)}>
                  Close
                </button>
              </div>
              <div className="rp-section-body">
                <div className="rp-config-form">
                  {selectedReference.config_schema &&
                    Object.entries(selectedReference.config_schema).map(([key, schema]) =>
                      renderConfigField(key, schema, referenceConfig, handleReferenceConfigChange)
                    )}
                </div>
                <div className="rp-button-row" style={{ marginTop: 12 }}>
                  <button
                    className="rp-btn rp-btn-primary"
                    onClick={handleBrowseReferences}
                    disabled={refLoading}
                  >
                    {refLoading ? "Loading..." : "Browse"}
                  </button>
                </div>
                {refError && <div className="rp-error-text" style={{ marginTop: 8 }}>{refError}</div>}
              </div>
            </div>
          )}

          {/* Reference Items List */}
          {selectedReference && refItems.length > 0 && (
            <div className="rp-section rp-section-flex">
              <div className="rp-section-header">
                <h3 className="rp-section-title">Available Items ({refItems.length})</h3>
              </div>
              <div className="rp-section-body rp-section-scroll">
                {refItems.map((item) => (
                  <div
                    key={item.id}
                    className={`rp-list-item rp-list-item-compact ${selectedRefItem?.id === item.id ? "rp-list-item-selected" : ""}`}
                    onClick={() => handleFetchReference(item)}
                  >
                    <div className="rp-list-item-main">
                      <div className="rp-list-item-title">{item.title}</div>
                      <div className="rp-list-item-meta">
                        {item.mime_type && <span>{item.mime_type}</span>}
                        {item.size_bytes && <span> - {formatBytes(item.size_bytes)}</span>}
                      </div>
                      {item.content_preview && (
                        <div className="rp-list-item-preview" style={{ fontSize: "0.85em", color: "#666", marginTop: 4 }}>
                          {item.content_preview.substring(0, 100)}
                          {item.content_preview.length > 100 && "..."}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Fetched Content Preview */}
          {fetching && (
            <div className="rp-section">
              <div className="rp-section-body">
                <div className="rp-info-text">Fetching content...</div>
              </div>
            </div>
          )}

          {fetchedContent && !fetching && (
            <div className="rp-section rp-section-flex">
              <div className="rp-section-header">
                <h3 className="rp-section-title">{fetchedContent.title || "Content Preview"}</h3>
                <button className="rp-btn rp-btn-sm" onClick={() => setFetchedContent(null)}>
                  Close
                </button>
              </div>
              <div className="rp-section-body rp-section-scroll">
                {fetchedContent.error && <div className="rp-error-text">{fetchedContent.error}</div>}
                {!fetchedContent.error && (
                  <>
                    {fetchedContent.url && (
                      <div className="rp-content-meta" style={{ marginBottom: 8, fontSize: "0.85em", color: "#666" }}>
                        Source: {fetchedContent.url}
                      </div>
                    )}
                    {fetchedContent.fetchedAt && (
                      <div className="rp-content-meta" style={{ marginBottom: 8, fontSize: "0.85em", color: "#666" }}>
                        Fetched: {new Date(fetchedContent.fetchedAt).toLocaleString()}
                      </div>
                    )}
                    <pre className="rp-content-preview" style={{
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                      fontSize: "0.9em",
                      background: "#f5f5f5",
                      padding: 12,
                      borderRadius: 4,
                      maxHeight: 400,
                      overflow: "auto",
                    }}>
                      {fetchedContent.content}
                    </pre>
                  </>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default PluginsTab;
