import React, { useState, useEffect } from 'react';
import './TranscriptionQueue.css';

const STATUS_ICONS = {
  pending: '⏳',
  processing: '🔄',
  completed: '✅',
  failed: '❌'
};

const formatDuration = (seconds) => {
  if (!seconds) return '';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
};

function TranscriptionQueue({ onClose }) {
  const [queue, setQueue] = useState([]);
  const [stats, setStats] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [models, setModels] = useState(null);
  const [selectedModel, setSelectedModel] = useState('base');
  const [view, setView] = useState('queue'); // queue | add
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    loadQueue();
    loadModels();
  }, []);

  const loadQueue = async () => {
    try {
      const res = await fetch('/api/library/transcription/queue');
      const data = await res.json();
      setQueue(data.items || []);
      setStats(data.stats || {});
    } catch (err) {
      console.error('Failed to load queue:', err);
    }
  };

  const loadModels = async () => {
    try {
      const res = await fetch('/api/library/transcription/models');
      const data = await res.json();
      setModels(data.models);
      setSelectedModel(data.default || 'base');
    } catch (err) {
      console.error('Failed to load models:', err);
    }
  };

  const loadCandidates = async () => {
    try {
      const res = await fetch('/api/library/transcription/candidates?limit=50');
      const data = await res.json();
      setCandidates(data.files || []);
    } catch (err) {
      console.error('Failed to load candidates:', err);
    }
  };

  const handleAddToQueue = async (fileId) => {
    try {
      const res = await fetch('/api/library/transcription/queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          library_file_id: fileId,
          model: selectedModel
        })
      });
      const data = await res.json();
      if (data.status === 'queued') {
        loadQueue();
        loadCandidates();
      }
    } catch (err) {
      console.error('Failed to add to queue:', err);
    }
  };

  const handleQueueAll = async () => {
    if (!confirm(`Queue all ${candidates.length} files for transcription?`)) return;

    try {
      const res = await fetch('/api/library/transcription/queue-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: selectedModel })
      });
      const data = await res.json();
      alert(`Added ${data.added} files to queue`);
      loadQueue();
      loadCandidates();
    } catch (err) {
      console.error('Failed to queue all:', err);
    }
  };

  const handleRemove = async (queueId) => {
    try {
      await fetch(`/api/library/transcription/queue/${queueId}`, {
        method: 'DELETE'
      });
      loadQueue();
    } catch (err) {
      console.error('Failed to remove:', err);
    }
  };

  const handleRetry = async (queueId) => {
    try {
      await fetch(`/api/library/transcription/queue/${queueId}/retry`, {
        method: 'POST'
      });
      loadQueue();
    } catch (err) {
      console.error('Failed to retry:', err);
    }
  };

  const handleProcess = async () => {
    setProcessing(true);
    try {
      const res = await fetch('/api/library/transcription/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ count: 1 })
      });
      const data = await res.json();
      alert(`Processed ${data.success} of ${data.processed} items`);
      loadQueue();
    } catch (err) {
      console.error('Failed to process:', err);
    } finally {
      setProcessing(false);
    }
  };

  const renderStats = () => {
    if (!stats) return null;

    return (
      <div className="transcription-stats">
        <div className="stat">
          <span className="stat-value">{stats.pending}</span>
          <span className="stat-label">Pending</span>
        </div>
        <div className="stat">
          <span className="stat-value">{stats.processing}</span>
          <span className="stat-label">Processing</span>
        </div>
        <div className="stat">
          <span className="stat-value">{stats.completed}</span>
          <span className="stat-label">Completed</span>
        </div>
        <div className="stat">
          <span className="stat-value">{stats.failed}</span>
          <span className="stat-label">Failed</span>
        </div>
      </div>
    );
  };

  const renderQueueItem = (item) => (
    <div key={item.id} className={`queue-item status-${item.status}`}>
      <span className="status-icon">{STATUS_ICONS[item.status]}</span>
      <div className="item-info">
        <div className="item-filename">{item.filename}</div>
        <div className="item-meta">
          Model: {item.model} | Priority: {item.priority}
          {item.processing_time_seconds && (
            <span> | Time: {formatDuration(item.processing_time_seconds)}</span>
          )}
          {item.error_message && (
            <span className="error-text"> | {item.error_message}</span>
          )}
        </div>
      </div>
      <div className="item-actions">
        {item.status === 'pending' && (
          <button onClick={() => handleRemove(item.id)} title="Remove">×</button>
        )}
        {item.status === 'failed' && (
          <button onClick={() => handleRetry(item.id)} title="Retry">↻</button>
        )}
      </div>
    </div>
  );

  const renderQueue = () => (
    <div className="queue-view">
      {renderStats()}

      <div className="queue-actions">
        <button
          onClick={handleProcess}
          disabled={processing || stats?.pending === 0}
        >
          {processing ? 'Processing...' : 'Process Next'}
        </button>
        <button onClick={() => { setView('add'); loadCandidates(); }}>
          Add Files
        </button>
      </div>

      <div className="queue-list">
        {queue.length === 0 ? (
          <div className="empty-queue">No items in queue</div>
        ) : (
          queue.map(renderQueueItem)
        )}
      </div>
    </div>
  );

  const renderAddView = () => (
    <div className="add-view">
      <div className="add-header">
        <button onClick={() => setView('queue')} className="back-btn">
          ← Back to Queue
        </button>
      </div>

      <div className="model-selector">
        <label>Model:</label>
        <select
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
        >
          {models && Object.entries(models).map(([name, info]) => (
            <option key={name} value={name}>
              {name} ({info.speed}, {info.accuracy} accuracy)
            </option>
          ))}
        </select>
      </div>

      {candidates.length > 0 && (
        <div className="queue-all-section">
          <button onClick={handleQueueAll}>
            Queue All ({candidates.length} files)
          </button>
        </div>
      )}

      <div className="candidates-list">
        {candidates.length === 0 ? (
          <div className="no-candidates">
            No audio/video files waiting for transcription
          </div>
        ) : (
          candidates.map((file) => (
            <div key={file.id} className="candidate-item">
              <span className="file-icon">
                {file.mime_type?.includes('video') ? '🎬' : '🎵'}
              </span>
              <div className="file-info">
                <div className="filename">{file.filename}</div>
              </div>
              <button onClick={() => handleAddToQueue(file.id)}>
                + Queue
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );

  return (
    <div className="transcription-queue">
      <div className="panel-header">
        <h4>Transcription Queue</h4>
        {onClose && (
          <button className="close-btn" onClick={onClose}>×</button>
        )}
      </div>

      {view === 'queue' && renderQueue()}
      {view === 'add' && renderAddView()}
    </div>
  );
}

export default TranscriptionQueue;
