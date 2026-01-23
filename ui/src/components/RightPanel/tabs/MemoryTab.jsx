// src/components/RightPanel/tabs/MemoryTab.jsx
import React, { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../../../api/client";

const DEFAULT_CATEGORIES = [
  "identity",
  "preference",
  "project",
  "theology",
  "engineering",
  "music",
  "general",
];

function MemoryTab() {
  // Memory list state
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Filters
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [pinnedOnly, setPinnedOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSemanticSearch, setIsSemanticSearch] = useState(false);

  // Categories from API
  const [categories, setCategories] = useState([]);

  // Settings
  const [settings, setSettings] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(false);

  // Add memory form
  const [showAddForm, setShowAddForm] = useState(false);
  const [newMemoryContent, setNewMemoryContent] = useState("");
  const [newMemoryCategory, setNewMemoryCategory] = useState("general");
  const [addingMemory, setAddingMemory] = useState(false);

  // Expanded memory for viewing full content
  const [expandedMemoryId, setExpandedMemoryId] = useState(null);

  // Load memories
  const loadMemories = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      let data;

      if (searchQuery && isSemanticSearch) {
        // Semantic search
        data = await apiFetch("/memory/search", {
          method: "POST",
          body: { query: searchQuery, limit: 50 },
        });
      } else {
        // Regular list with filters
        const params = new URLSearchParams();
        if (categoryFilter && categoryFilter !== "all") {
          params.append("category", categoryFilter);
        }
        if (sourceFilter && sourceFilter !== "all") {
          params.append("source", sourceFilter);
        }
        if (pinnedOnly) {
          params.append("pinned_only", "true");
        }
        if (searchQuery && !isSemanticSearch) {
          params.append("q", searchQuery);
        }

        const url = `/memory/list${params.toString() ? "?" + params : ""}`;
        data = await apiFetch(url);
      }

      setMemories(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to load memories:", err);
      setError("Failed to load memories");
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, sourceFilter, pinnedOnly, searchQuery, isSemanticSearch]);

  // Load categories
  const loadCategories = async () => {
    try {
      const data = await apiFetch("/memory/categories");
      if (Array.isArray(data)) {
        // Merge with defaults
        const merged = new Set([...DEFAULT_CATEGORIES, ...data]);
        setCategories([...merged].sort());
      }
    } catch (err) {
      console.error("Failed to load categories:", err);
      setCategories(DEFAULT_CATEGORIES);
    }
  };

  // Load settings
  const loadSettings = async () => {
    try {
      const data = await apiFetch("/memory/settings");
      setSettings(data);
    } catch (err) {
      console.error("Failed to load settings:", err);
    }
  };

  // Initial load
  useEffect(() => {
    loadMemories();
    loadCategories();
    loadSettings();
  }, []);

  // Reload when filters change
  useEffect(() => {
    loadMemories();
  }, [loadMemories]);

  // Add memory
  const handleAddMemory = async () => {
    if (!newMemoryContent.trim()) return;

    setAddingMemory(true);
    try {
      await apiFetch("/memory/add", {
        method: "POST",
        body: {
          content: newMemoryContent.trim(),
          category: newMemoryCategory,
        },
      });

      setNewMemoryContent("");
      setShowAddForm(false);
      loadMemories();
      loadCategories();
    } catch (err) {
      console.error("Failed to add memory:", err);
      setError("Failed to add memory");
    } finally {
      setAddingMemory(false);
    }
  };

  // Delete memory
  const handleDeleteMemory = async (memoryId) => {
    if (!window.confirm("Delete this memory?")) return;

    try {
      await apiFetch(`/memory/${memoryId}`, { method: "DELETE" });
      loadMemories();
    } catch (err) {
      console.error("Failed to delete memory:", err);
      setError("Failed to delete memory");
    }
  };

  // Pin/Unpin memory
  const handleTogglePin = async (memory) => {
    const endpoint = memory.is_pinned
      ? `/memory/${memory.id}/unpin`
      : `/memory/${memory.id}/pin`;

    try {
      const result = await apiFetch(endpoint, { method: "POST" });
      if (result.error) {
        setError(result.error);
        return;
      }
      loadMemories();
    } catch (err) {
      console.error("Failed to toggle pin:", err);
      setError("Failed to toggle pin");
    }
  };

  // Update settings
  const handleUpdateSettings = async (updates) => {
    setSettingsLoading(true);
    try {
      await apiFetch("/memory/settings", {
        method: "PUT",
        body: updates,
      });
      await loadSettings();
    } catch (err) {
      console.error("Failed to update settings:", err);
      setError("Failed to update settings");
    } finally {
      setSettingsLoading(false);
    }
  };

  // Handle search
  const handleSearch = (e) => {
    e.preventDefault();
    loadMemories();
  };

  // Render memory card
  const renderMemoryCard = (memory) => {
    const isExpanded = expandedMemoryId === memory.id;
    const content = memory.content || "";
    const shouldTruncate = content.length > 200 && !isExpanded;

    return (
      <div key={memory.id} className="rp-memory-card">
        <div className="rp-memory-header">
          <div className="rp-memory-tags">
            <span className="rp-tag rp-tag-muted">{memory.category}</span>
            {memory.is_pinned && (
              <span className="rp-tag rp-tag-positive">Pinned</span>
            )}
            <span
              className={`rp-tag ${
                memory.source === "manual"
                  ? "rp-tag-warning"
                  : "rp-tag-muted"
              }`}
            >
              {memory.source}
            </span>
            {memory.score !== undefined && (
              <span className="rp-tag rp-tag-muted">
                {(memory.score * 100).toFixed(0)}%
              </span>
            )}
          </div>
          <div className="rp-memory-actions">
            <button
              className="rp-button-compact"
              onClick={() => handleTogglePin(memory)}
              title={memory.is_pinned ? "Unpin" : "Pin"}
            >
              {memory.is_pinned ? "Unpin" : "Pin"}
            </button>
            <button
              className="rp-button-compact rp-btn-danger"
              onClick={() => handleDeleteMemory(memory.id)}
              title="Delete"
            >
              Del
            </button>
          </div>
        </div>

        <div
          className="rp-memory-content"
          onClick={() =>
            setExpandedMemoryId(isExpanded ? null : memory.id)
          }
        >
          {shouldTruncate ? content.slice(0, 200) + "..." : content}
        </div>

        {memory.created_at && (
          <div className="rp-memory-meta">
            {new Date(memory.created_at).toLocaleDateString()}
          </div>
        )}
      </div>
    );
  };

  // Render settings panel
  const renderSettings = () => {
    if (!settings) return null;

    return (
      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">Memory Settings</h3>
          <button
            className="rp-button subtle"
            onClick={() => setShowSettings(false)}
          >
            Close
          </button>
        </div>
        <div className="rp-section-body">
          <div className="rp-memory-setting">
            <label className="rp-memory-setting-label">
              <input
                type="checkbox"
                checked={settings.auto_save_enabled}
                onChange={(e) =>
                  handleUpdateSettings({ auto_save_enabled: e.target.checked })
                }
                disabled={settingsLoading}
              />
              Auto-save memories
            </label>
            <div className="rp-help-text">
              Automatically save relevant information from conversations
            </div>
          </div>

          <div className="rp-memory-setting">
            <label className="rp-label">Max Pinned Memories</label>
            <select
              className="rp-select"
              value={settings.max_pinned_memories}
              onChange={(e) =>
                handleUpdateSettings({
                  max_pinned_memories: parseInt(e.target.value),
                })
              }
              disabled={settingsLoading}
            >
              {[5, 10, 15, 20, 25].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>

          <div className="rp-memory-setting">
            <label className="rp-label">Auto-save Categories</label>
            <div className="rp-memory-category-toggles">
              {DEFAULT_CATEGORIES.map((cat) => (
                <label key={cat} className="rp-memory-category-toggle">
                  <input
                    type="checkbox"
                    checked={(settings.auto_save_categories || []).includes(
                      cat
                    )}
                    onChange={(e) => {
                      const current = settings.auto_save_categories || [];
                      const updated = e.target.checked
                        ? [...current, cat]
                        : current.filter((c) => c !== cat);
                      handleUpdateSettings({ auto_save_categories: updated });
                    }}
                    disabled={settingsLoading}
                  />
                  {cat}
                </label>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Render add form
  const renderAddForm = () => {
    return (
      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">Add Memory</h3>
          <button
            className="rp-button subtle"
            onClick={() => setShowAddForm(false)}
          >
            Cancel
          </button>
        </div>
        <div className="rp-section-body">
          <div className="rp-memory-form">
            <textarea
              className="rp-notes-textarea rp-small"
              placeholder="Enter memory content..."
              value={newMemoryContent}
              onChange={(e) => setNewMemoryContent(e.target.value)}
              disabled={addingMemory}
            />

            <div className="rp-memory-form-row">
              <select
                className="rp-select"
                value={newMemoryCategory}
                onChange={(e) => setNewMemoryCategory(e.target.value)}
                disabled={addingMemory}
              >
                {categories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>

              <button
                className="rp-button primary"
                onClick={handleAddMemory}
                disabled={addingMemory || !newMemoryContent.trim()}
              >
                {addingMemory ? "Adding..." : "Add"}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="rp-tab-content">
      {/* Search and Controls */}
      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">Memory</h3>
          <div className="rp-header-actions">
            <button
              className="rp-button subtle"
              onClick={() => {
                setShowSettings(!showSettings);
                setShowAddForm(false);
              }}
            >
              Settings
            </button>
            <button
              className="rp-button primary"
              onClick={() => {
                setShowAddForm(!showAddForm);
                setShowSettings(false);
              }}
            >
              Add
            </button>
          </div>
        </div>

        <div className="rp-section-body">
          {/* Search */}
          <form onSubmit={handleSearch} className="rp-search-bar">
            <input
              type="text"
              className="rp-search-input"
              placeholder="Search memories..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <button type="submit" className="rp-search-button">
              Search
            </button>
          </form>

          {/* Search mode toggle */}
          <div className="rp-memory-controls">
            <button
              className={`rp-button-pill ${
                !isSemanticSearch ? "rp-button-pill-active" : ""
              }`}
              onClick={() => setIsSemanticSearch(false)}
            >
              Text
            </button>
            <button
              className={`rp-button-pill ${
                isSemanticSearch ? "rp-button-pill-active" : ""
              }`}
              onClick={() => setIsSemanticSearch(true)}
            >
              Semantic
            </button>
          </div>

          {/* Filters */}
          <div className="rp-memory-filters">
            <div className="rp-memory-filter-group">
              <label className="rp-label">Category</label>
              <select
                className="rp-select"
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
              >
                <option value="all">All</option>
                {categories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            <div className="rp-memory-filter-group">
              <label className="rp-label">Source</label>
              <select
                className="rp-select"
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
              >
                <option value="all">All</option>
                <option value="manual">Manual</option>
                <option value="auto">Auto</option>
              </select>
            </div>

            <div className="rp-memory-filter-group">
              <label className="rp-memory-setting-label">
                <input
                  type="checkbox"
                  checked={pinnedOnly}
                  onChange={(e) => setPinnedOnly(e.target.checked)}
                />
                Pinned only
              </label>
            </div>
          </div>

          {/* Stats */}
          <div className="rp-memory-stats">
            {memories.length} memor{memories.length === 1 ? "y" : "ies"}
            {settings && (
              <span className="rp-memory-stat-pinned">
                {" "}
                | {memories.filter((m) => m.is_pinned).length}/
                {settings.max_pinned_memories} pinned
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Settings Panel */}
      {showSettings && renderSettings()}

      {/* Add Form */}
      {showAddForm && renderAddForm()}

      {/* Error */}
      {error && (
        <div className="rp-section">
          <div className="rp-error-text">{error}</div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="rp-section">
          <div className="rp-info-text">Loading memories...</div>
        </div>
      )}

      {/* Memory List */}
      {!loading && memories.length === 0 && (
        <div className="rp-empty-state">
          <div className="rp-empty-title">No memories found</div>
          <div className="rp-empty-text">
            Memories are automatically saved from conversations or can be
            added manually.
          </div>
        </div>
      )}

      {!loading && memories.length > 0 && (
        <div className="rp-memory-list">
          {memories.map(renderMemoryCard)}
        </div>
      )}
    </div>
  );
}

export default MemoryTab;
