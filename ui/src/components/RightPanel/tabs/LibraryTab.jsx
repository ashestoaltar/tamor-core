import React, { useState, useEffect } from 'react';
import { useLibrary } from '../../../hooks/useLibrary';
import './LibraryTab.css';

// File type icons
const getFileIcon = (mimeType) => {
  if (!mimeType) return '📄';
  if (mimeType.includes('pdf')) return '📕';
  if (mimeType.includes('epub')) return '📘';
  if (mimeType.includes('audio')) return '🎵';
  if (mimeType.includes('video')) return '🎬';
  if (mimeType.includes('word') || mimeType.includes('document')) return '📝';
  return '📄';
};

// Format file size
const formatSize = (bytes) => {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

function LibraryTab({ projectId }) {
  const {
    loading,
    error,
    listFiles,
    getStats,
    search,
    addToProject,
    getIndexQueue,
    processIndexQueue,
    startIngest,
    getScanConfig
  } = useLibrary();

  const [view, setView] = useState('browse'); // browse | search | manage
  const [files, setFiles] = useState([]);
  const [stats, setStats] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [indexQueue, setIndexQueue] = useState(null);
  const [scanConfig, setScanConfig] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);

  // Load initial data
  useEffect(() => {
    loadLibrary();
    loadStats();
  }, []);

  const loadLibrary = async () => {
    const result = await listFiles({ limit: 50 });
    if (result) {
      setFiles(result.files);
    }
  };

  const loadStats = async () => {
    const result = await getStats();
    if (result) {
      setStats(result);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    const result = await search(searchQuery, {
      scope: projectId ? 'all' : 'library',
      project_id: projectId,
      limit: 20
    });

    if (result) {
      setSearchResults(result);
      setView('search');
    }
  };

  const handleAddToProject = async (libraryFileId) => {
    if (!projectId) {
      alert('Select a project first');
      return;
    }

    const result = await addToProject(projectId, libraryFileId);
    if (result) {
      alert(result.status === 'created' ? 'Added to project' : 'Already in project');
    }
  };

  const loadManageData = async () => {
    const [queue, config] = await Promise.all([
      getIndexQueue(),
      getScanConfig()
    ]);
    setIndexQueue(queue);
    setScanConfig(config);
  };

  const handleProcessQueue = async () => {
    const result = await processIndexQueue(20);
    if (result) {
      alert(`Indexed ${result.success} files`);
      loadManageData();
      loadStats();
    }
  };

  const handleIngest = async () => {
    if (!confirm('Import new files from library path?')) return;

    const result = await startIngest({ autoIndex: false });
    if (result) {
      alert(`Imported ${result.result.created} new files`);
      loadLibrary();
      loadStats();
      loadManageData();
    }
  };

  // Render stats bar
  const renderStats = () => {
    if (!stats) return null;

    return (
      <div className="library-stats">
        <span className="stat">
          <strong>{stats.file_count}</strong> files
        </span>
        <span className="stat">
          <strong>{stats.total_mb}</strong> MB
        </span>
        <span className="stat">
          <strong>{stats.indexed}</strong> indexed
        </span>
        {stats.not_indexed > 0 && (
          <span className="stat warning">
            <strong>{stats.not_indexed}</strong> pending
          </span>
        )}
      </div>
    );
  };

  // Render file list
  const renderFileList = (fileList, showRelevance = false) => {
    return (
      <div className="library-file-list">
        {fileList.map((file) => (
          <div
            key={file.library_file_id || file.id}
            className={`library-file-item ${selectedFile === (file.library_file_id || file.id) ? 'selected' : ''}`}
            onClick={() => setSelectedFile(file.library_file_id || file.id)}
          >
            <span className="file-icon">{getFileIcon(file.mime_type)}</span>
            <div className="file-info">
              <div className="file-name">{file.filename}</div>
              <div className="file-meta">
                {formatSize(file.size_bytes)}
                {showRelevance && file.score && (
                  <span className="relevance">
                    {Math.round(file.score * 100)}% match
                  </span>
                )}
              </div>
              {showRelevance && file.content && (
                <div className="file-excerpt">
                  {file.content.substring(0, 150)}...
                </div>
              )}
            </div>
            <div className="file-actions">
              {projectId && (
                <button
                  className="btn-small"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleAddToProject(file.library_file_id || file.id);
                  }}
                  title="Add to project"
                >
                  +
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    );
  };

  // Browse view
  const renderBrowse = () => (
    <div className="library-browse">
      {renderStats()}

      <form onSubmit={handleSearch} className="library-search-form">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search library..."
          className="library-search-input"
        />
        <button type="submit" disabled={loading}>
          Search
        </button>
      </form>

      {files.length > 0 ? (
        renderFileList(files)
      ) : (
        <div className="library-empty">
          <p>No files in library yet.</p>
          <button onClick={() => { setView('manage'); loadManageData(); }}>
            Import Files
          </button>
        </div>
      )}
    </div>
  );

  // Search results view
  const renderSearchResults = () => (
    <div className="library-search-results">
      <div className="search-header">
        <button onClick={() => setView('browse')} className="back-btn">
          ← Back
        </button>
        <span className="search-info">
          {searchResults?.count || 0} results for "{searchResults?.query}"
        </span>
      </div>

      {searchResults?.results?.length > 0 ? (
        renderFileList(searchResults.results, true)
      ) : (
        <div className="no-results">No matching content found.</div>
      )}
    </div>
  );

  // Manage view
  const renderManage = () => (
    <div className="library-manage">
      <button onClick={() => setView('browse')} className="back-btn">
        ← Back
      </button>

      <h4>Library Management</h4>

      {scanConfig && (
        <div className="config-section">
          <h5>Storage</h5>
          <div className="config-item">
            <span className="config-label">Mount Path:</span>
            <span className="config-value">{scanConfig.mount_path}</span>
          </div>
          <div className="config-item">
            <span className="config-label">Status:</span>
            <span className={`config-value ${scanConfig.is_mounted ? 'ok' : 'error'}`}>
              {scanConfig.is_mounted ? '✓ Mounted' : '✗ Not Mounted'}
            </span>
          </div>
        </div>
      )}

      {indexQueue && (
        <div className="queue-section">
          <h5>Indexing Queue</h5>
          <div className="queue-stats">
            <span>{indexQueue.indexed} indexed</span>
            <span>{indexQueue.unindexed} pending</span>
          </div>
          {indexQueue.unindexed > 0 && (
            <button onClick={handleProcessQueue} disabled={loading}>
              {loading ? 'Processing...' : 'Index Next 20'}
            </button>
          )}
        </div>
      )}

      <div className="ingest-section">
        <h5>Import Files</h5>
        <p>Scan library path for new files and import them.</p>
        <button onClick={handleIngest} disabled={loading || !scanConfig?.is_mounted}>
          {loading ? 'Importing...' : 'Import New Files'}
        </button>
      </div>
    </div>
  );

  return (
    <div className="library-tab">
      <div className="library-header">
        <h3>Library</h3>
        <div className="library-nav">
          <button
            className={view === 'browse' ? 'active' : ''}
            onClick={() => setView('browse')}
          >
            Browse
          </button>
          <button
            className={view === 'manage' ? 'active' : ''}
            onClick={() => { setView('manage'); loadManageData(); }}
          >
            Manage
          </button>
        </div>
      </div>

      {error && <div className="library-error">{error}</div>}

      <div className="library-content">
        {view === 'browse' && renderBrowse()}
        {view === 'search' && renderSearchResults()}
        {view === 'manage' && renderManage()}
      </div>
    </div>
  );
}

export default LibraryTab;
