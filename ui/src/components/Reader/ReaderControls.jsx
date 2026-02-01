import React, { useCallback } from 'react';

/**
 * Audio playback controls for the reader
 */
function ReaderControls({
  session,
  audioState,
  onPlay,
  onPause,
  onToggle,
  onSkipBack,
  onSkipForward,
  onSeek,
  onAddBookmark,
  onSpeedChange,
  availableVoices = [],
}) {
  const { playing, loading, currentTime, duration, currentChunk } = audioState;

  // Format time as mm:ss
  const formatTime = useCallback((seconds) => {
    if (!seconds || !isFinite(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }, []);

  // Handle scrubber click
  const handleScrubberClick = useCallback((e) => {
    if (!duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const percent = clickX / rect.width;
    const newTime = percent * duration;
    onSeek?.(newTime);
  }, [duration, onSeek]);

  // Handle speed change
  const handleSpeedChange = useCallback((e) => {
    const speed = parseFloat(e.target.value);
    onSpeedChange?.(session?.tts_voice, speed);
  }, [session?.tts_voice, onSpeedChange]);

  // Calculate progress percentage
  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="reader-controls">
      {/* Progress scrubber */}
      <div
        className="reader-scrubber"
        onClick={handleScrubberClick}
        role="slider"
        aria-label="Audio progress"
        aria-valuenow={currentTime}
        aria-valuemin={0}
        aria-valuemax={duration}
        tabIndex={0}
      >
        <div className="reader-scrubber-track">
          <div
            className="reader-scrubber-fill"
            style={{ width: `${progressPercent}%` }}
          />
          <div
            className="reader-scrubber-thumb"
            style={{ left: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Time display */}
      <div className="reader-time">
        <span className="reader-time-current">{formatTime(currentTime)}</span>
        <span className="reader-time-separator">/</span>
        <span className="reader-time-total">{formatTime(duration)}</span>
        {currentChunk && (
          <span className="reader-chunk-info">
            Chunk {currentChunk.index + 1}
          </span>
        )}
      </div>

      {/* Playback controls */}
      <div className="reader-playback-controls">
        {/* Skip back */}
        <button
          className="reader-btn reader-btn-skip"
          onClick={() => onSkipBack?.(10)}
          aria-label="Skip back 10 seconds"
          title="Skip back 10s"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/>
            <text x="12" y="15" fontSize="7" textAnchor="middle" fill="currentColor">10</text>
          </svg>
        </button>

        {/* Play/Pause */}
        <button
          className={`reader-btn reader-btn-play ${loading ? 'loading' : ''}`}
          onClick={onToggle}
          disabled={loading}
          aria-label={playing ? 'Pause' : 'Play'}
        >
          {loading ? (
            <span className="reader-spinner" />
          ) : playing ? (
            <svg viewBox="0 0 24 24" fill="currentColor" width="28" height="28">
              <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="currentColor" width="28" height="28">
              <path d="M8 5v14l11-7z"/>
            </svg>
          )}
        </button>

        {/* Skip forward */}
        <button
          className="reader-btn reader-btn-skip"
          onClick={() => onSkipForward?.(30)}
          aria-label="Skip forward 30 seconds"
          title="Skip forward 30s"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <path d="M12 5V1l5 5-5 5V7c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6h2c0 4.42-3.58 8-8 8s-8-3.58-8-8 3.58-8 8-8z"/>
            <text x="12" y="15" fontSize="7" textAnchor="middle" fill="currentColor">30</text>
          </svg>
        </button>
      </div>

      {/* Settings row */}
      <div className="reader-settings-row">
        {/* Speed selector */}
        <div className="reader-speed">
          <label htmlFor="tts-speed">Speed:</label>
          <select
            id="tts-speed"
            value={session?.tts_speed || 1.0}
            onChange={handleSpeedChange}
            className="reader-select"
          >
            <option value="0.75">0.75x</option>
            <option value="1.0">1.0x</option>
            <option value="1.25">1.25x</option>
            <option value="1.5">1.5x</option>
            <option value="2.0">2.0x</option>
          </select>
        </div>

        {/* Bookmark button */}
        <button
          className="reader-btn reader-btn-bookmark"
          onClick={onAddBookmark}
          aria-label="Add bookmark"
          title="Add bookmark at current position"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
            <path d="M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2z"/>
          </svg>
        </button>
      </div>
    </div>
  );
}

export default ReaderControls;
