import React, { useState, useEffect } from 'react';
import { useLibrary } from '../../../hooks/useLibrary';
import './LibrarySettings.css';

function LibrarySettings({ onClose }) {
  const { getSettings, updateSettings, loading } = useLibrary();
  const [settings, setSettings] = useState(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    const result = await getSettings();
    if (result) {
      setSettings(result.settings);
    }
  };

  const handleChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
    setDirty(true);
  };

  const handleSave = async () => {
    const result = await updateSettings(settings);
    if (result) {
      setSettings(result.settings);
      setDirty(false);
    }
  };

  if (!settings) {
    return <div className="library-settings loading">Loading...</div>;
  }

  return (
    <div className="library-settings">
      <div className="settings-header">
        <h4>Library Settings</h4>
        {onClose && (
          <button className="close-btn" onClick={onClose}>×</button>
        )}
      </div>

      <div className="settings-section">
        <h5>Context Injection</h5>
        <p className="section-desc">
          Control how library content is used in chat responses.
        </p>

        <label className="setting-row toggle">
          <span>Enable context injection</span>
          <input
            type="checkbox"
            checked={settings.context_injection_enabled}
            onChange={(e) => handleChange('context_injection_enabled', e.target.checked)}
          />
        </label>

        <label className="setting-row">
          <span>Search scope</span>
          <select
            value={settings.context_scope}
            onChange={(e) => handleChange('context_scope', e.target.value)}
          >
            <option value="library">Entire library</option>
            <option value="project">Project references only</option>
            <option value="all">Both (project prioritized)</option>
          </select>
        </label>

        <label className="setting-row">
          <span>Max context chunks</span>
          <input
            type="number"
            min="1"
            max="10"
            value={settings.context_max_chunks}
            onChange={(e) => handleChange('context_max_chunks', parseInt(e.target.value))}
          />
        </label>

        <label className="setting-row">
          <span>Min relevance score</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={settings.context_min_score}
            onChange={(e) => handleChange('context_min_score', parseFloat(e.target.value))}
          />
          <span className="range-value">{settings.context_min_score}</span>
        </label>
      </div>

      <div className="settings-section">
        <h5>Display</h5>

        <label className="setting-row toggle">
          <span>Show sources in responses</span>
          <input
            type="checkbox"
            checked={settings.show_sources_in_response}
            onChange={(e) => handleChange('show_sources_in_response', e.target.checked)}
          />
        </label>
      </div>

      {dirty && (
        <div className="settings-actions">
          <button onClick={handleSave} disabled={loading}>
            {loading ? 'Saving...' : 'Save Changes'}
          </button>
          <button onClick={loadSettings} className="secondary">
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

export default LibrarySettings;
