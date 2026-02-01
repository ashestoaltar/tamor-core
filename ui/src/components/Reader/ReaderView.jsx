import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useReader } from '../../hooks/useReader';
import ReaderControls from './ReaderControls';
import './Reader.css';

/**
 * Main reader component for visual and audio reading
 */
function ReaderView({
  contentType,
  contentId,
  onClose,
  initialMode = 'visual',
}) {
  const {
    session,
    content,
    loading,
    error,
    audioState,
    playAudio,
    pauseAudio,
    togglePlayback,
    seekTo,
    skipForward,
    skipBackward,
    updateProgress,
    addBookmark,
    removeBookmark,
    updateSettings,
    getVoices,
    completeSession,
  } = useReader(contentType, contentId, initialMode);

  // UI state
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showBookmarks, setShowBookmarks] = useState(false);
  const [fontSize, setFontSize] = useState(18);
  const [lineHeight, setLineHeight] = useState(1.8);
  const [voices, setVoices] = useState([]);
  const [lastScrollTime, setLastScrollTime] = useState(Date.now());

  // Refs
  const contentRef = useRef(null);
  const containerRef = useRef(null);
  const readingStartTime = useRef(Date.now());

  // Load available voices
  useEffect(() => {
    getVoices().then(data => {
      if (data?.voices) setVoices(data.voices);
    });
  }, [getVoices]);

  // Scroll tracking for progress
  const handleScroll = useCallback(() => {
    if (!contentRef.current || !content?.total_chars) return;

    const { scrollTop, scrollHeight, clientHeight } = contentRef.current;
    const scrollPercent = scrollTop / (scrollHeight - clientHeight);
    const positionChar = Math.floor(scrollPercent * content.total_chars);

    // Calculate reading time since last update
    const now = Date.now();
    const timeDelta = Math.floor((now - lastScrollTime) / 1000);
    setLastScrollTime(now);

    // Update progress (debounced)
    updateProgress(positionChar, timeDelta > 0 && timeDelta < 30 ? timeDelta : 0);
  }, [content?.total_chars, lastScrollTime, updateProgress]);

  // Scroll to bookmark
  const scrollToPosition = useCallback((charPosition) => {
    if (!contentRef.current || !content?.total_chars) return;

    const percent = charPosition / content.total_chars;
    const scrollHeight = contentRef.current.scrollHeight - contentRef.current.clientHeight;
    contentRef.current.scrollTo({
      top: percent * scrollHeight,
      behavior: 'smooth',
    });
  }, [content?.total_chars]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ignore if typing in an input
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      switch (e.key) {
        case ' ':
          e.preventDefault();
          togglePlayback();
          break;
        case 'Escape':
          onClose?.();
          break;
        case 'b':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            handleAddBookmark();
          }
          break;
        case 'f':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            toggleFullscreen();
          }
          break;
        case '=':
        case '+':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            setFontSize(s => Math.min(32, s + 2));
          }
          break;
        case '-':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            setFontSize(s => Math.max(12, s - 2));
          }
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [togglePlayback, onClose]);

  // Fullscreen handling
  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  }, []);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // Add bookmark at current position
  const handleAddBookmark = useCallback(() => {
    if (!contentRef.current || !content?.total_chars) return;

    const { scrollTop, scrollHeight, clientHeight } = contentRef.current;
    const scrollPercent = scrollTop / (scrollHeight - clientHeight);
    const positionChar = Math.floor(scrollPercent * content.total_chars);

    addBookmark(positionChar);
  }, [content?.total_chars, addBookmark]);

  // Calculate progress percentage
  const progressPercent = session?.total_chars
    ? (session.position_char / session.total_chars) * 100
    : 0;

  // Loading state
  if (loading) {
    return (
      <div className="reader-container reader-loading" ref={containerRef}>
        <div className="reader-spinner-large" />
        <p>Loading content...</p>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="reader-container reader-error" ref={containerRef}>
        <h2>Failed to load</h2>
        <p>{error}</p>
        <button onClick={onClose} className="reader-btn">Close</button>
      </div>
    );
  }

  return (
    <div
      className={`reader-container ${isFullscreen ? 'fullscreen' : ''}`}
      ref={containerRef}
    >
      {/* Header */}
      <header className="reader-header">
        <div className="reader-header-left">
          <button
            className="reader-btn reader-btn-close"
            onClick={onClose}
            aria-label="Close reader"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
          <h1 className="reader-title">{content?.title || 'Untitled'}</h1>
        </div>

        <div className="reader-header-center">
          <span className="reader-progress-text">
            {progressPercent.toFixed(0)}% complete
          </span>
        </div>

        <div className="reader-header-right">
          <button
            className={`reader-btn ${showBookmarks ? 'active' : ''}`}
            onClick={() => setShowBookmarks(!showBookmarks)}
            aria-label="Toggle bookmarks"
            title="Bookmarks"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
              <path d="M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2z"/>
            </svg>
            {session?.bookmarks?.length > 0 && (
              <span className="reader-badge">{session.bookmarks.length}</span>
            )}
          </button>

          <button
            className={`reader-btn ${showSettings ? 'active' : ''}`}
            onClick={() => setShowSettings(!showSettings)}
            aria-label="Settings"
            title="Settings"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
              <path d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
            </svg>
          </button>

          <button
            className="reader-btn"
            onClick={toggleFullscreen}
            aria-label="Toggle fullscreen"
            title="Fullscreen"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
              {isFullscreen ? (
                <path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/>
              ) : (
                <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/>
              )}
            </svg>
          </button>
        </div>
      </header>

      {/* Settings panel */}
      {showSettings && (
        <div className="reader-settings-panel">
          <div className="reader-setting">
            <label>Font Size: {fontSize}px</label>
            <input
              type="range"
              min="12"
              max="32"
              value={fontSize}
              onChange={(e) => setFontSize(parseInt(e.target.value))}
            />
          </div>

          <div className="reader-setting">
            <label>Line Height: {lineHeight}</label>
            <input
              type="range"
              min="1.2"
              max="2.5"
              step="0.1"
              value={lineHeight}
              onChange={(e) => setLineHeight(parseFloat(e.target.value))}
            />
          </div>

          {voices.length > 0 && (
            <div className="reader-setting">
              <label>Voice</label>
              <select
                value={session?.tts_voice || ''}
                onChange={(e) => updateSettings(e.target.value, session?.tts_speed)}
                className="reader-select"
              >
                {voices.map(v => (
                  <option key={v.name} value={v.name}>{v.name}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}

      {/* Progress bar with bookmarks */}
      <div className="reader-progress-bar">
        <div
          className="reader-progress-fill"
          style={{ width: `${progressPercent}%` }}
        />
        {session?.bookmarks?.map((bm, idx) => {
          const bmPercent = (bm.char / session.total_chars) * 100;
          return (
            <div
              key={idx}
              className="reader-bookmark-marker"
              style={{ left: `${bmPercent}%` }}
              onClick={() => scrollToPosition(bm.char)}
              title={bm.label}
            />
          );
        })}
      </div>

      {/* Main content area */}
      <div className="reader-main">
        {/* Bookmarks sidebar */}
        {showBookmarks && (
          <aside className="reader-bookmarks-sidebar">
            <h3>Bookmarks</h3>
            {session?.bookmarks?.length > 0 ? (
              <ul className="reader-bookmarks-list">
                {session.bookmarks.map((bm, idx) => (
                  <li key={idx} className="reader-bookmark-item">
                    <button
                      className="reader-bookmark-goto"
                      onClick={() => scrollToPosition(bm.char)}
                    >
                      {bm.label}
                    </button>
                    <button
                      className="reader-bookmark-delete"
                      onClick={() => removeBookmark(idx)}
                      aria-label="Remove bookmark"
                    >
                      <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                      </svg>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="reader-no-bookmarks">No bookmarks yet</p>
            )}
          </aside>
        )}

        {/* Content */}
        <div
          className="reader-content"
          ref={contentRef}
          onScroll={handleScroll}
          style={{
            fontSize: `${fontSize}px`,
            lineHeight: lineHeight,
          }}
        >
          <div className="reader-text">
            {content?.text?.split('\n').map((paragraph, idx) => (
              paragraph.trim() ? (
                <p key={idx}>{paragraph}</p>
              ) : (
                <br key={idx} />
              )
            ))}
          </div>

          {/* End of content */}
          <div className="reader-end">
            <p>End of document</p>
            <button
              className="reader-btn reader-btn-complete"
              onClick={completeSession}
            >
              Mark as Complete
            </button>
          </div>
        </div>
      </div>

      {/* Audio controls */}
      {(initialMode === 'audio' || initialMode === 'both') && (
        <footer className="reader-footer">
          <ReaderControls
            session={session}
            audioState={audioState}
            onPlay={playAudio}
            onPause={pauseAudio}
            onToggle={togglePlayback}
            onSkipBack={skipBackward}
            onSkipForward={skipForward}
            onSeek={seekTo}
            onAddBookmark={handleAddBookmark}
            onSpeedChange={updateSettings}
            availableVoices={voices}
          />
        </footer>
      )}
    </div>
  );
}

export default ReaderView;
