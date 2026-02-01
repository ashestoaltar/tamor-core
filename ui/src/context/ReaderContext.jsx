import React, { createContext, useContext, useState, useCallback } from 'react';

/**
 * Reader Context
 *
 * Manages global reader state for the expandable right panel reader mode.
 * When active, the right panel expands and shows the reader instead of tabs.
 */

const ReaderContext = createContext(null);

export function ReaderProvider({ children }) {
  // Reader state
  const [isReaderOpen, setIsReaderOpen] = useState(false);
  const [readerContent, setReaderContent] = useState({
    contentType: null,  // 'file', 'library', 'transcript'
    contentId: null,
    mode: 'visual',     // 'visual', 'audio', 'both'
    title: null,        // Optional title for display
  });

  // Open reader with specific content
  const openReader = useCallback((contentType, contentId, mode = 'both', title = null) => {
    setReaderContent({
      contentType,
      contentId,
      mode,
      title,
    });
    setIsReaderOpen(true);
  }, []);

  // Close reader and return to normal panel mode
  const closeReader = useCallback(() => {
    setIsReaderOpen(false);
    // Keep content state for potential "resume" functionality
  }, []);

  // Clear reader content entirely
  const clearReader = useCallback(() => {
    setIsReaderOpen(false);
    setReaderContent({
      contentType: null,
      contentId: null,
      mode: 'visual',
      title: null,
    });
  }, []);

  // Update reader mode without reopening
  const setReaderMode = useCallback((mode) => {
    setReaderContent(prev => ({ ...prev, mode }));
  }, []);

  const value = {
    // State
    isReaderOpen,
    readerContent,

    // Actions
    openReader,
    closeReader,
    clearReader,
    setReaderMode,
  };

  return (
    <ReaderContext.Provider value={value}>
      {children}
    </ReaderContext.Provider>
  );
}

export function useReaderContext() {
  const context = useContext(ReaderContext);
  if (!context) {
    throw new Error('useReaderContext must be used within a ReaderProvider');
  }
  return context;
}

export default ReaderContext;
