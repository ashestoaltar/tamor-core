// ui/src/hooks/useReferences.js
/**
 * Hook for fetching scripture references from the API.
 */

import { useState, useCallback } from 'react';
import { apiFetch } from '../api/client';

/**
 * Hook for fetching and managing scripture references.
 *
 * @returns {Object} - Reference lookup functions and state
 *
 * @example
 * const { lookup, compare, loading, error } = useReferences();
 *
 * // Look up a single reference
 * const results = await lookup('John 3:16', { translations: ['KJV', 'ASV'] });
 *
 * // Compare translations
 * const comparisons = await compare('Genesis 1:1', ['KJV', 'ASV', 'YLT']);
 */
export function useReferences() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [cache, setCache] = useState({}); // Local cache to avoid re-fetching

  /**
   * Look up a scripture reference.
   *
   * @param {string} ref - Reference string (e.g., "John 3:16")
   * @param {Object} options - Lookup options
   * @param {string[]} [options.sources] - Sources to query ("sword", "sefaria")
   * @param {string[]} [options.translations] - SWORD translations to use
   * @param {boolean} [options.skipCache=false] - Bypass local cache
   * @returns {Promise<Array|null>} - Array of reference results or null on error
   */
  const lookup = useCallback(async (ref, options = {}) => {
    const { sources, translations, skipCache = false } = options;

    // Build cache key
    const cacheKey = `${ref}-${sources?.join(',') || 'all'}-${translations?.join(',') || 'default'}`;

    // Check cache first
    if (!skipCache && cache[cacheKey]) {
      return cache[cacheKey];
    }

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({ ref });
      if (sources) params.set('sources', sources.join(','));
      if (translations) params.set('translations', translations.join(','));

      const data = await apiFetch(`/references/lookup?${params}`);

      // Cache result
      setCache(prev => ({ ...prev, [cacheKey]: data.results }));

      return data.results;
    } catch (err) {
      setError(err.message || 'Failed to fetch reference');
      return null;
    } finally {
      setLoading(false);
    }
  }, [cache]);

  /**
   * Compare multiple translations of a passage.
   *
   * @param {string} ref - Reference string
   * @param {string[]} translations - Translation codes to compare
   * @param {boolean} [includeSefaria=false] - Include Sefaria English
   * @returns {Promise<Array|null>} - Array of translation results or null on error
   */
  const compare = useCallback(async (ref, translations, includeSefaria = false) => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        ref,
        translations: translations.join(','),
      });
      if (includeSefaria) {
        params.set('include_sefaria', 'true');
      }

      const data = await apiFetch(`/references/compare?${params}`);
      return data.translations;
    } catch (err) {
      setError(err.message || 'Failed to compare translations');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Search references by keyword.
   *
   * @param {string} query - Search query
   * @param {Object} options - Search options
   * @param {string[]} [options.sources] - Sources to search
   * @param {number} [options.limit=20] - Maximum results
   * @returns {Promise<Array|null>} - Array of search results or null on error
   */
  const search = useCallback(async (query, options = {}) => {
    const { sources, limit = 20 } = options;

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({ q: query, limit: String(limit) });
      if (sources) params.set('sources', sources.join(','));

      const data = await apiFetch(`/references/search?${params}`);
      return data.results;
    } catch (err) {
      setError(err.message || 'Search failed');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Get available translations.
   *
   * @returns {Promise<Array>} - Array of translation info objects
   */
  const getTranslations = useCallback(async () => {
    try {
      const data = await apiFetch('/references/translations');
      return data.translations || [];
    } catch (err) {
      console.error('Failed to fetch translations:', err);
      return [];
    }
  }, []);

  /**
   * Get installed SWORD modules.
   *
   * @returns {Promise<Array>} - Array of installed module codes
   */
  const getInstalledModules = useCallback(async () => {
    try {
      const data = await apiFetch('/references/modules/installed');
      return data.modules || [];
    } catch (err) {
      console.error('Failed to fetch installed modules:', err);
      return [];
    }
  }, []);

  /**
   * Get book information.
   *
   * @param {string} book - Book name
   * @param {string} [translation] - Optional translation code
   * @returns {Promise<Object|null>} - Book info or null on error
   */
  const getBookInfo = useCallback(async (book, translation) => {
    try {
      const path = translation
        ? `/references/book/${encodeURIComponent(book)}?translation=${translation}`
        : `/references/book/${encodeURIComponent(book)}`;
      return await apiFetch(path);
    } catch (err) {
      console.error('Failed to fetch book info:', err);
      return null;
    }
  }, []);

  /**
   * Get commentary for a passage.
   *
   * @param {string} ref - Reference string
   * @param {string} [commentator] - Specific commentator (optional)
   * @returns {Promise<Object|null>} - Reference with commentary or null on error
   */
  const getCommentary = useCallback(async (ref, commentator) => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({ ref });
      if (commentator) params.set('commentator', commentator);

      const data = await apiFetch(`/references/commentary?${params}`);
      return data;
    } catch (err) {
      setError(err.message || 'Failed to fetch commentary');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Get cross-references for a passage.
   *
   * @param {string} ref - Reference string
   * @returns {Promise<Array|null>} - Array of cross-references or null on error
   */
  const getCrossReferences = useCallback(async (ref) => {
    try {
      const params = new URLSearchParams({ ref });
      const data = await apiFetch(`/references/cross-references?${params}`);
      return data.cross_references || [];
    } catch (err) {
      console.error('Failed to fetch cross-references:', err);
      return null;
    }
  }, []);

  /**
   * Detect references in text (server-side).
   *
   * @param {string} text - Text to search for references
   * @returns {Promise<Array|null>} - Array of detected references or null on error
   */
  const detectReferences = useCallback(async (text) => {
    try {
      const data = await apiFetch('/references/detect', {
        method: 'POST',
        body: { text },
      });
      return data.references || [];
    } catch (err) {
      console.error('Failed to detect references:', err);
      return null;
    }
  }, []);

  /**
   * Batch lookup multiple references.
   *
   * @param {string[]} refs - Array of reference strings
   * @param {Object} options - Lookup options (same as lookup)
   * @returns {Promise<Object>} - Map of ref string to results
   */
  const lookupBatch = useCallback(async (refs, options = {}) => {
    const results = {};

    // Fetch in parallel
    await Promise.all(
      refs.map(async (ref) => {
        const result = await lookup(ref, options);
        if (result) {
          results[ref] = result;
        }
      })
    );

    return results;
  }, [lookup]);

  /**
   * Clear the local cache.
   */
  const clearCache = useCallback(() => {
    setCache({});
  }, []);

  return {
    // Lookup functions
    lookup,
    compare,
    search,
    lookupBatch,

    // Metadata functions
    getTranslations,
    getInstalledModules,
    getBookInfo,

    // Extended functions
    getCommentary,
    getCrossReferences,
    detectReferences,

    // State
    loading,
    error,

    // State management
    clearError: () => setError(null),
    clearCache,
  };
}

export default useReferences;
