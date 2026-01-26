import React, { useState, useEffect } from 'react';
import './StatusIndicator.css';

function StatusIndicator({ showExpanded = false }) {
  const [status, setStatus] = useState(null);
  const [expanded, setExpanded] = useState(showExpanded);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStatus();
    // Refresh every 60 seconds
    const interval = setInterval(fetchStatus, 60000);
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/system-status');
      const data = await res.json();
      setStatus(data);
    } catch (err) {
      setStatus({ online: false });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="status-indicator loading">...</div>;
  }

  // Minimal view: just online/offline dot
  if (!expanded) {
    return (
      <button
        className="status-indicator minimal"
        onClick={() => setExpanded(true)}
        title={status?.online ? 'System online' : 'System offline'}
      >
        <span
          className="status-dot"
          style={{ color: status?.online ? 'var(--success-color)' : 'var(--error-color)' }}
        >
          ●
        </span>
      </button>
    );
  }

  // Expanded view: show all indicators
  return (
    <div className="status-indicator expanded">
      <div className="status-header">
        <span>System Status</span>
        <button onClick={() => setExpanded(false)}>×</button>
      </div>

      <div className="status-list">
        <div className={`status-item ${status?.online ? 'ok' : 'error'}`}>
          <span className="status-icon">●</span>
          <span className="status-label">Network</span>
          <span className="status-value">{status?.online ? 'Online' : 'Offline'}</span>
        </div>

        <div className={`status-item ${status?.llm_available ? 'ok' : 'error'}`}>
          <span className="status-icon">🤖</span>
          <span className="status-label">LLM</span>
          <span className="status-value">
            {status?.llm_available ? status?.llm_provider : 'Unavailable'}
          </span>
        </div>

        <div className={`status-item ${status?.library_mounted ? 'ok' : 'warn'}`}>
          <span className="status-icon">📚</span>
          <span className="status-label">Library</span>
          <span className="status-value">
            {status?.library_mounted
              ? `${status?.library_file_count} files`
              : 'Not mounted'}
          </span>
        </div>

        <div className={`status-item ${status?.sword_available ? 'ok' : 'warn'}`}>
          <span className="status-icon">📖</span>
          <span className="status-label">Bible (SWORD)</span>
          <span className="status-value">
            {status?.sword_available
              ? `${status?.sword_module_count} modules`
              : 'No modules'}
          </span>
        </div>

        <div className={`status-item ${status?.embeddings_available ? 'ok' : 'error'}`}>
          <span className="status-icon">🔍</span>
          <span className="status-label">Embeddings</span>
          <span className="status-value">
            {status?.embeddings_available ? 'Ready' : 'Unavailable'}
          </span>
        </div>
      </div>

      <button className="status-refresh" onClick={fetchStatus}>
        Refresh
      </button>
    </div>
  );
}

export default StatusIndicator;
