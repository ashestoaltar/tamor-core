// src/components/RightPanel/tabs/PluginsTab.jsx
import React, { useState, useEffect, useRef } from "react";
import { apiFetch, API_BASE } from "../../../api/client";

function PluginsTab({ currentProjectId }) {
  const [plugins, setPlugins] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Selected plugin for configuration/import
  const [selectedPlugin, setSelectedPlugin] = useState(null);
  const [config, setConfig] = useState({});

  // Import mode: "server" or "upload"
  const [importMode, setImportMode] = useState("upload");

  // Preview state (for server mode)
  const [previewItems, setPreviewItems] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");

  // Import state
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);

  // Selected items for import (null = all)
  const [selectedItemIds, setSelectedItemIds] = useState(null);

  // File upload
  const fileInputRef = useRef(null);
  const [uploadProgress, setUploadProgress] = useState(null);

  // Load plugins on mount
  useEffect(() => {
    loadPlugins();
  }, []);

  // Reset state when project changes
  useEffect(() => {
    setSelectedPlugin(null);
    setConfig({});
    setPreviewItems([]);
    setImportResult(null);
    setSelectedItemIds(null);
  }, [currentProjectId]);

  const loadPlugins = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch("/plugins");
      setPlugins(data.plugins || []);
    } catch (err) {
      console.error("Failed to load plugins", err);
      setError(err.message || "Failed to load plugins");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPlugin = (plugin) => {
    setSelectedPlugin(plugin);
    // Initialize config with defaults from schema
    const initialConfig = {};
    if (plugin.config_schema) {
      Object.entries(plugin.config_schema).forEach(([key, schema]) => {
        if (schema.default !== undefined) {
          initialConfig[key] = schema.default;
        }
      });
    }
    setConfig(initialConfig);
    setPreviewItems([]);
    setImportResult(null);
    setSelectedItemIds(null);
  };

  const handleConfigChange = (key, value) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handlePreview = async () => {
    if (!selectedPlugin) return;

    setPreviewLoading(true);
    setPreviewError("");
    setPreviewItems([]);
    setImportResult(null);
    setSelectedItemIds(null);

    try {
      const data = await apiFetch(`/plugins/${selectedPlugin.id}/list`, {
        method: "POST",
        body: { config },
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
    if (!selectedPlugin || !currentProjectId) return;

    setImporting(true);
    setImportResult(null);

    try {
      const body = {
        project_id: currentProjectId,
        config,
      };

      // If specific items selected, include them
      if (selectedItemIds && selectedItemIds.length > 0) {
        body.item_ids = selectedItemIds;
      }

      const data = await apiFetch(`/plugins/${selectedPlugin.id}/import`, {
        method: "POST",
        body,
      });

      if (data.error) {
        setImportResult({
          success: false,
          error: data.details || data.error,
        });
      } else {
        setImportResult({
          success: true,
          summary: data.summary,
          results: data.results,
        });
      }
    } catch (err) {
      console.error("Import failed", err);
      setImportResult({
        success: false,
        error: err.message || "Import failed",
      });
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
    if (!selectedPlugin || !currentProjectId) return;

    setImporting(true);
    setImportResult(null);
    setUploadProgress({ current: 0, total: files.length });

    try {
      const formData = new FormData();
      formData.append("project_id", currentProjectId);
      for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
      }

      // Use fetch directly for FormData (apiFetch uses JSON)
      const response = await fetch(
        `${API_BASE}/plugins/${selectedPlugin.id}/upload-import`,
        {
          method: "POST",
          body: formData,
          credentials: "include",
        }
      );

      const data = await response.json();

      if (data.error) {
        setImportResult({
          success: false,
          error: data.details || data.error,
        });
      } else {
        setImportResult({
          success: true,
          summary: data.summary,
          results: data.results,
        });
      }
    } catch (err) {
      console.error("Upload failed", err);
      setImportResult({
        success: false,
        error: err.message || "Upload failed",
      });
    } finally {
      setImporting(false);
      setUploadProgress(null);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const getAcceptedFileTypes = () => {
    if (!selectedPlugin) return "*/*";

    // Set accepted file types based on plugin
    switch (selectedPlugin.id) {
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
      // First selection - start with just this item
      setSelectedItemIds([itemId]);
    } else if (selectedItemIds.includes(itemId)) {
      // Remove from selection
      const newIds = selectedItemIds.filter((id) => id !== itemId);
      setSelectedItemIds(newIds.length > 0 ? newIds : null);
    } else {
      // Add to selection
      setSelectedItemIds([...selectedItemIds, itemId]);
    }
  };

  const selectAllItems = () => {
    if (previewItems.length === 0) return;

    if (
      selectedItemIds &&
      selectedItemIds.length === previewItems.length
    ) {
      // Deselect all
      setSelectedItemIds(null);
    } else {
      // Select all
      setSelectedItemIds(previewItems.map((item) => item.id));
    }
  };

  const formatBytes = (bytes) => {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const renderConfigField = (key, schema) => {
    const value = config[key] ?? schema.default ?? "";

    if (schema.type === "boolean") {
      return (
        <label key={key} className="rp-config-field rp-config-checkbox">
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => handleConfigChange(key, e.target.checked)}
          />
          <span className="rp-config-label">{key}</span>
          {schema.description && (
            <span className="rp-config-desc">{schema.description}</span>
          )}
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
              const val = e.target.value;
              const arr = val
                .split(",")
                .map((s) => s.trim())
                .filter((s) => s);
              handleConfigChange(key, arr);
            }}
          />
          {schema.description && (
            <span className="rp-config-desc">{schema.description}</span>
          )}
        </div>
      );
    }

    // Default: string input
    return (
      <div key={key} className="rp-config-field">
        <label className="rp-config-label">{key}</label>
        <input
          type="text"
          className="rp-input"
          placeholder={schema.description || key}
          value={value}
          onChange={(e) => handleConfigChange(key, e.target.value)}
        />
        {schema.description && (
          <span className="rp-config-desc">{schema.description}</span>
        )}
      </div>
    );
  };

  return (
    <div className="rp-tab-content">
      {/* Plugin List Section */}
      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">Available Plugins</h3>
          <button
            className="rp-btn rp-btn-sm"
            onClick={loadPlugins}
            disabled={loading}
          >
            Refresh
          </button>
        </div>
        <div className="rp-section-body">
          {loading && <div className="rp-info-text">Loading plugins...</div>}
          {error && <div className="rp-error-text">{error}</div>}
          {!loading && plugins.length === 0 && (
            <div className="rp-info-text">No plugins available.</div>
          )}
          {plugins.map((plugin) => (
            <div
              key={plugin.id}
              className={`rp-list-item ${
                selectedPlugin?.id === plugin.id ? "rp-list-item-selected" : ""
              }`}
              onClick={() => handleSelectPlugin(plugin)}
            >
              <div className="rp-list-item-main">
                <div className="rp-list-item-title">{plugin.name}</div>
                <div className="rp-list-item-meta">{plugin.description}</div>
              </div>
              <span className="rp-tag rp-tag-info">{plugin.type}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Plugin Configuration Section */}
      {selectedPlugin && (
        <div className="rp-section">
          <div className="rp-section-header">
            <h3 className="rp-section-title">{selectedPlugin.name}</h3>
            <button
              className="rp-btn rp-btn-sm"
              onClick={() => setSelectedPlugin(null)}
            >
              Close
            </button>
          </div>
          <div className="rp-section-body">
            {/* Import Mode Toggle */}
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

            {/* Upload Mode */}
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
                  <div className="rp-upload-text">
                    Click to select files from your device
                  </div>
                  <div className="rp-upload-hint">
                    {selectedPlugin.id === "audio-transcript" && "Audio/video files (mp3, mp4, wav, etc.)"}
                    {selectedPlugin.id === "bulk-pdf" && "PDF files"}
                    {selectedPlugin.id === "local-folder" && "Any files"}
                  </div>
                </div>
                {importing && (
                  <div className="rp-info-text" style={{ marginTop: 8 }}>
                    Uploading and processing files...
                  </div>
                )}
              </div>
            )}

            {/* Server Mode */}
            {importMode === "server" && (
              <>
                <div className="rp-config-form">
                  {selectedPlugin.config_schema &&
                    Object.entries(selectedPlugin.config_schema).map(
                      ([key, schema]) => renderConfigField(key, schema)
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
                {previewError && (
                  <div className="rp-error-text" style={{ marginTop: 8 }}>
                    {previewError}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Preview Items Section */}
      {selectedPlugin && previewItems.length > 0 && (
        <div className="rp-section rp-section-flex">
          <div className="rp-section-header">
            <h3 className="rp-section-title">
              Items to Import ({previewItems.length})
            </h3>
            <div className="rp-header-actions">
              <button
                className="rp-btn rp-btn-sm"
                onClick={selectAllItems}
              >
                {selectedItemIds?.length === previewItems.length
                  ? "Deselect All"
                  : "Select All"}
              </button>
              <button
                className="rp-btn rp-btn-sm rp-btn-primary"
                onClick={handleImport}
                disabled={importing || !currentProjectId}
              >
                {importing
                  ? "Importing..."
                  : `Import ${
                      selectedItemIds
                        ? `${selectedItemIds.length} Selected`
                        : "All"
                    }`}
              </button>
            </div>
          </div>
          <div className="rp-section-body rp-section-scroll">
            {previewItems.map((item) => (
              <div
                key={item.id}
                className={`rp-list-item rp-list-item-compact ${
                  selectedItemIds?.includes(item.id)
                    ? "rp-list-item-selected"
                    : ""
                }`}
                onClick={() => toggleItemSelection(item.id)}
              >
                <input
                  type="checkbox"
                  checked={
                    selectedItemIds
                      ? selectedItemIds.includes(item.id)
                      : false
                  }
                  onChange={() => toggleItemSelection(item.id)}
                  onClick={(e) => e.stopPropagation()}
                  style={{ marginRight: 8 }}
                />
                <div className="rp-list-item-main">
                  <div className="rp-list-item-title">{item.name}</div>
                  <div className="rp-list-item-meta">
                    {item.mime_type && <span>{item.mime_type}</span>}
                    {item.size_bytes && (
                      <span> • {formatBytes(item.size_bytes)}</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Import Results Section */}
      {importResult && (
        <div className="rp-section">
          <div className="rp-section-header">
            <h3 className="rp-section-title">Import Results</h3>
            <button
              className="rp-btn rp-btn-sm"
              onClick={() => setImportResult(null)}
            >
              Clear
            </button>
          </div>
          <div className="rp-section-body">
            {!importResult.success && (
              <div className="rp-error-text">{importResult.error}</div>
            )}
            {importResult.success && importResult.summary && (
              <div className="rp-import-summary">
                <div className="rp-summary-stat">
                  <span className="rp-summary-label">Total:</span>
                  <span className="rp-summary-value">
                    {importResult.summary.total}
                  </span>
                </div>
                <div className="rp-summary-stat rp-summary-success">
                  <span className="rp-summary-label">Succeeded:</span>
                  <span className="rp-summary-value">
                    {importResult.summary.succeeded}
                  </span>
                </div>
                {importResult.summary.failed > 0 && (
                  <div className="rp-summary-stat rp-summary-failed">
                    <span className="rp-summary-label">Failed:</span>
                    <span className="rp-summary-value">
                      {importResult.summary.failed}
                    </span>
                  </div>
                )}
              </div>
            )}
            {importResult.success &&
              importResult.results &&
              importResult.results.some((r) => !r.success) && (
                <div className="rp-import-errors" style={{ marginTop: 12 }}>
                  <div className="rp-info-text">Failed items:</div>
                  {importResult.results
                    .filter((r) => !r.success)
                    .map((r) => (
                      <div
                        key={r.item_id}
                        className="rp-error-item"
                      >
                        <strong>{r.item_name}</strong>: {r.error}
                      </div>
                    ))}
                </div>
              )}
          </div>
        </div>
      )}
    </div>
  );
}

export default PluginsTab;
