import React, { useState, useEffect } from 'react';
import { useLibrary } from '../../../hooks/useLibrary';
import LibrarySettings from './LibrarySettings';
import TranscriptionQueue from './TranscriptionQueue';
import CollectionModal from './CollectionModal';
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
    getScanConfig,
    listCollections,
    createCollection,
    updateCollection,
    deleteCollection,
    getCollectionFiles,
    addToCollection,
    removeFromCollection
  } = useLibrary();

  const [view, setView] = useState('browse'); // browse | search | manage | settings | collections
  const [showTranscription, setShowTranscription] = useState(false);
  const [files, setFiles] = useState([]);
  const [stats, setStats] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [indexQueue, setIndexQueue] = useState(null);
  const [scanConfig, setScanConfig] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);

  // Collections state
  const [collections, setCollections] = useState([]);
  const [selectedCollection, setSelectedCollection] = useState(null);
  const [collectionFiles, setCollectionFiles] = useState([]);
  const [showCollectionModal, setShowCollectionModal] = useState(false);
  const [editingCollection, setEditingCollection] = useState(null);
  const [showAddToCollection, setShowAddToCollection] = useState(null); // file id to add

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

  // Collections functions
  const loadCollections = async () => {
    const result = await listCollections();
    if (result) {
      setCollections(result.collections);
    }
  };

  const loadCollectionFiles = async (collectionId) => {
    const result = await getCollectionFiles(collectionId);
    if (result) {
      setCollectionFiles(result.files);
    }
  };

  const handleCreateCollection = async (data) => {
    const result = await createCollection(data.name, data.description, data.color);
    if (result) {
      setShowCollectionModal(false);
      loadCollections();
    }
  };

  const handleUpdateCollection = async (data) => {
    const result = await updateCollection(data.id, {
      name: data.name,
      description: data.description,
      color: data.color
    });
    if (result) {
      setShowCollectionModal(false);
      setEditingCollection(null);
      loadCollections();
      if (selectedCollection?.id === data.id) {
        setSelectedCollection(result.collection);
      }
    }
  };

  const handleDeleteCollection = async (collection) => {
    if (!confirm(`Delete collection "${collection.name}"? Files will not be deleted.`)) return;

    const result = await deleteCollection(collection.id);
    if (result) {
      loadCollections();
      if (selectedCollection?.id === collection.id) {
        setSelectedCollection(null);
        setCollectionFiles([]);
      }
    }
  };

  const handleAddToCollection = async (collectionId, fileId) => {
    const result = await addToCollection(collectionId, fileId);
    if (result) {
      setShowAddToCollection(null);
      if (selectedCollection?.id === collectionId) {
        loadCollectionFiles(collectionId);
      }
      loadCollections();
    }
  };

  const handleRemoveFromCollection = async (fileId) => {
    if (!selectedCollection) return;

    const result = await removeFromCollection(selectedCollection.id, fileId);
    if (result) {
      loadCollectionFiles(selectedCollection.id);
      loadCollections();
    }
  };

  const openCollection = async (collection) => {
    setSelectedCollection(collection);
    await loadCollectionFiles(collection.id);
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
  const renderFileList = (fileList, showRelevance = false, options = {}) => {
    const { showCollectionActions = true, inCollection = false } = options;

    return (
      <div className="library-file-list">
        {fileList.map((file) => {
          const fileId = file.library_file_id || file.id;
          return (
            <div
              key={fileId}
              className={`library-file-item ${selectedFile === fileId ? 'selected' : ''}`}
              onClick={() => setSelectedFile(fileId)}
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
                {showCollectionActions && !inCollection && (
                  <button
                    className="btn-small btn-collection"
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowAddToCollection(fileId);
                    }}
                    title="Add to collection"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
                    </svg>
                  </button>
                )}
                {inCollection && (
                  <button
                    className="btn-small btn-remove"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveFromCollection(fileId);
                    }}
                    title="Remove from collection"
                  >
                    &times;
                  </button>
                )}
                {projectId && (
                  <button
                    className="btn-small"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleAddToProject(fileId);
                    }}
                    title="Add to project"
                  >
                    +
                  </button>
                )}
              </div>
            </div>
          );
        })}
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

      <div className="transcription-section">
        <h5>Transcription</h5>
        <p>Transcribe audio and video files to searchable text.</p>
        <button onClick={() => setShowTranscription(true)}>
          Open Transcription Queue
        </button>
      </div>
    </div>
  );

  // Collections view
  const renderCollections = () => {
    if (selectedCollection) {
      return (
        <div className="collection-view">
          <div className="collection-header">
            <button onClick={() => { setSelectedCollection(null); setCollectionFiles([]); }} className="back-btn">
              ← Back
            </button>
            <div className="collection-title">
              <span className="collection-dot" style={{ backgroundColor: selectedCollection.color }}></span>
              <span>{selectedCollection.name}</span>
              <span className="collection-count">({selectedCollection.file_count} files)</span>
            </div>
            <div className="collection-actions">
              <button
                className="btn-small"
                onClick={() => {
                  setEditingCollection(selectedCollection);
                  setShowCollectionModal(true);
                }}
                title="Edit collection"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
              </button>
              <button
                className="btn-small btn-remove"
                onClick={() => handleDeleteCollection(selectedCollection)}
                title="Delete collection"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                </svg>
              </button>
            </div>
          </div>
          {selectedCollection.description && (
            <p className="collection-description">{selectedCollection.description}</p>
          )}

          {collectionFiles.length > 0 ? (
            renderFileList(collectionFiles, false, { inCollection: true })
          ) : (
            <div className="collection-empty">
              <p>No files in this collection yet.</p>
              <button onClick={() => setView('browse')}>
                Browse Library to Add Files
              </button>
            </div>
          )}
        </div>
      );
    }

    return (
      <div className="collections-list">
        <div className="collections-header">
          <h4>Collections</h4>
          <button
            className="btn-primary-small"
            onClick={() => {
              setEditingCollection(null);
              setShowCollectionModal(true);
            }}
          >
            + New Collection
          </button>
        </div>

        {collections.length > 0 ? (
          <div className="collection-cards">
            {collections.map((collection) => (
              <div
                key={collection.id}
                className="collection-card"
                onClick={() => openCollection(collection)}
              >
                <div className="collection-card-header">
                  <span className="collection-dot" style={{ backgroundColor: collection.color }}></span>
                  <span className="collection-name">{collection.name}</span>
                </div>
                <div className="collection-card-meta">
                  {collection.file_count} file{collection.file_count !== 1 ? 's' : ''}
                </div>
                {collection.description && (
                  <div className="collection-card-desc">
                    {collection.description.substring(0, 80)}
                    {collection.description.length > 80 ? '...' : ''}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="collections-empty">
            <p>No collections yet. Create one to organize your library.</p>
          </div>
        )}
      </div>
    );
  };

  // Add to collection dropdown
  const renderAddToCollectionDropdown = () => {
    if (!showAddToCollection) return null;

    return (
      <div className="add-to-collection-overlay" onClick={() => setShowAddToCollection(null)}>
        <div className="add-to-collection-dropdown" onClick={(e) => e.stopPropagation()}>
          <h4>Add to Collection</h4>
          {collections.length > 0 ? (
            <div className="collection-options">
              {collections.map((collection) => (
                <button
                  key={collection.id}
                  className="collection-option"
                  onClick={() => handleAddToCollection(collection.id, showAddToCollection)}
                >
                  <span className="collection-dot" style={{ backgroundColor: collection.color }}></span>
                  <span>{collection.name}</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="no-collections">No collections yet.</p>
          )}
          <button
            className="btn-create-new"
            onClick={() => {
              setShowAddToCollection(null);
              setEditingCollection(null);
              setShowCollectionModal(true);
            }}
          >
            + Create New Collection
          </button>
        </div>
      </div>
    );
  };

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
            className={view === 'collections' ? 'active' : ''}
            onClick={() => { setView('collections'); loadCollections(); }}
          >
            Collections
          </button>
          <button
            className={view === 'manage' ? 'active' : ''}
            onClick={() => { setView('manage'); loadManageData(); }}
          >
            Manage
          </button>
          <button
            className={`settings-btn ${view === 'settings' ? 'active' : ''}`}
            onClick={() => setView('settings')}
            title="Library Settings"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
            </svg>
          </button>
        </div>
      </div>

      {error && <div className="library-error">{error}</div>}

      <div className="library-content">
        {view === 'browse' && renderBrowse()}
        {view === 'search' && renderSearchResults()}
        {view === 'collections' && renderCollections()}
        {view === 'manage' && renderManage()}
        {view === 'settings' && (
          <LibrarySettings onClose={() => setView('browse')} />
        )}
      </div>

      {showTranscription && (
        <div className="transcription-overlay">
          <TranscriptionQueue onClose={() => setShowTranscription(false)} />
        </div>
      )}

      {showCollectionModal && (
        <CollectionModal
          collection={editingCollection}
          onSave={editingCollection ? handleUpdateCollection : handleCreateCollection}
          onClose={() => {
            setShowCollectionModal(false);
            setEditingCollection(null);
          }}
        />
      )}

      {renderAddToCollectionDropdown()}
    </div>
  );
}

export default LibraryTab;
