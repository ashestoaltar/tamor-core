import { useState, useCallback } from 'react';

const API_BASE = '/api';

/**
 * Hook for library API interactions
 */
export function useLibrary() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // List library files
  const listFiles = useCallback(async (params = {}) => {
    setLoading(true);
    setError(null);
    try {
      const query = new URLSearchParams();
      if (params.limit) query.set('limit', params.limit);
      if (params.offset) query.set('offset', params.offset);
      if (params.search) query.set('search', params.search);
      if (params.mime_type) query.set('mime_type', params.mime_type);

      const res = await fetch(`${API_BASE}/library?${query}`);
      if (!res.ok) throw new Error('Failed to fetch library');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Get library stats
  const getStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/library/stats`);
      if (!res.ok) throw new Error('Failed to fetch stats');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Search library
  const search = useCallback(async (query, options = {}) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        q: query,
        scope: options.scope || 'library',
        limit: options.limit || 10,
        min_score: options.min_score || 0.4
      });
      if (options.project_id) {
        params.append('project_id', options.project_id);
      }
      const res = await fetch(`${API_BASE}/library/search?${params}`);
      if (!res.ok) throw new Error('Search failed');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Get file details
  const getFile = useCallback(async (fileId) => {
    try {
      const res = await fetch(`${API_BASE}/library/${fileId}`);
      if (!res.ok) throw new Error('File not found');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Get file text
  const getFileText = useCallback(async (fileId) => {
    try {
      const res = await fetch(`${API_BASE}/library/${fileId}/text`);
      if (!res.ok) throw new Error('Failed to get text');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Add file to project
  const addToProject = useCallback(async (projectId, libraryFileId, notes = null) => {
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/library`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ library_file_id: libraryFileId, notes })
      });
      if (!res.ok) throw new Error('Failed to add to project');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Remove from project
  const removeFromProject = useCallback(async (projectId, libraryFileId) => {
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/library/${libraryFileId}`, {
        method: 'DELETE'
      });
      if (!res.ok) throw new Error('Failed to remove');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Get project's library refs
  const getProjectRefs = useCallback(async (projectId) => {
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/library`);
      if (!res.ok) throw new Error('Failed to fetch refs');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Get scan config
  const getScanConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/library/scan/config`);
      if (!res.ok) throw new Error('Failed to fetch config');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Get scan preview
  const getScanPreview = useCallback(async (limit = 50) => {
    try {
      const res = await fetch(`${API_BASE}/library/scan/preview?limit=${limit}`);
      if (!res.ok) throw new Error('Failed to preview');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Start ingest
  const startIngest = useCallback(async (options = {}) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/library/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          new_only: options.newOnly !== false,
          auto_index: options.autoIndex !== false
        })
      });
      if (!res.ok) throw new Error('Ingest failed');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Get index queue status
  const getIndexQueue = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/library/index/queue`);
      if (!res.ok) throw new Error('Failed to fetch queue');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Process index queue
  const processIndexQueue = useCallback(async (count = 10) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/library/index/all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_size: count })
      });
      if (!res.ok) throw new Error('Processing failed');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Get settings
  const getSettings = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/library/settings`);
      if (!res.ok) throw new Error('Failed to fetch settings');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Update settings
  const updateSettings = useCallback(async (updates) => {
    try {
      const res = await fetch(`${API_BASE}/library/settings`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
      if (!res.ok) throw new Error('Failed to update settings');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // ==========================================================================
  // COLLECTIONS
  // ==========================================================================

  // List all collections
  const listCollections = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/library/collections`);
      if (!res.ok) throw new Error('Failed to fetch collections');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Create collection
  const createCollection = useCallback(async (name, description = null, color = null) => {
    try {
      const res = await fetch(`${API_BASE}/library/collections`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, color })
      });
      if (!res.ok) throw new Error('Failed to create collection');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Get collection
  const getCollection = useCallback(async (collectionId) => {
    try {
      const res = await fetch(`${API_BASE}/library/collections/${collectionId}`);
      if (!res.ok) throw new Error('Collection not found');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Update collection
  const updateCollection = useCallback(async (collectionId, updates) => {
    try {
      const res = await fetch(`${API_BASE}/library/collections/${collectionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
      if (!res.ok) throw new Error('Failed to update collection');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Delete collection
  const deleteCollection = useCallback(async (collectionId) => {
    try {
      const res = await fetch(`${API_BASE}/library/collections/${collectionId}`, {
        method: 'DELETE'
      });
      if (!res.ok) throw new Error('Failed to delete collection');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Get files in collection
  const getCollectionFiles = useCallback(async (collectionId, params = {}) => {
    try {
      const query = new URLSearchParams();
      if (params.limit) query.set('limit', params.limit);
      if (params.offset) query.set('offset', params.offset);

      const res = await fetch(`${API_BASE}/library/collections/${collectionId}/files?${query}`);
      if (!res.ok) throw new Error('Failed to fetch collection files');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Add file(s) to collection
  const addToCollection = useCallback(async (collectionId, fileIdOrIds) => {
    try {
      const body = Array.isArray(fileIdOrIds)
        ? { file_ids: fileIdOrIds }
        : { file_id: fileIdOrIds };

      const res = await fetch(`${API_BASE}/library/collections/${collectionId}/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!res.ok) throw new Error('Failed to add to collection');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Remove file from collection
  const removeFromCollection = useCallback(async (collectionId, fileId) => {
    try {
      const res = await fetch(`${API_BASE}/library/collections/${collectionId}/files/${fileId}`, {
        method: 'DELETE'
      });
      if (!res.ok) throw new Error('Failed to remove from collection');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Get collections for a file
  const getFileCollections = useCallback(async (fileId) => {
    try {
      const res = await fetch(`${API_BASE}/library/${fileId}/collections`);
      if (!res.ok) throw new Error('Failed to fetch file collections');
      return await res.json();
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  return {
    loading,
    error,
    listFiles,
    getStats,
    search,
    getFile,
    getFileText,
    addToProject,
    removeFromProject,
    getProjectRefs,
    getScanConfig,
    getScanPreview,
    startIngest,
    getIndexQueue,
    processIndexQueue,
    getSettings,
    updateSettings,
    // Collections
    listCollections,
    createCollection,
    getCollection,
    updateCollection,
    deleteCollection,
    getCollectionFiles,
    addToCollection,
    removeFromCollection,
    getFileCollections
  };
}

export default useLibrary;
