import { useState, useCallback, useEffect, useRef } from 'react';

const API_BASE = '/api/reader';

/**
 * Hook for managing reader state and API interactions
 */
export function useReader(contentType, contentId, initialMode = 'visual') {
  // Core state
  const [session, setSession] = useState(null);
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Audio state
  const [audioState, setAudioState] = useState({
    playing: false,
    loading: false,
    currentTime: 0,
    duration: 0,
    currentChunk: null,
    bufferedChunks: [],
    totalChunks: null,
  });

  // Audio element ref
  const audioRef = useRef(null);
  const progressSaveTimer = useRef(null);
  const chunkPreloadTimer = useRef(null);
  const playNextChunkRef = useRef(null); // For auto-advance

  // Initialize audio element
  useEffect(() => {
    audioRef.current = new Audio();
    audioRef.current.addEventListener('timeupdate', handleTimeUpdate);
    audioRef.current.addEventListener('ended', handleAudioEnded);
    audioRef.current.addEventListener('loadedmetadata', handleLoadedMetadata);
    audioRef.current.addEventListener('error', handleAudioError);

    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.removeEventListener('timeupdate', handleTimeUpdate);
        audioRef.current.removeEventListener('ended', handleAudioEnded);
        audioRef.current.removeEventListener('loadedmetadata', handleLoadedMetadata);
        audioRef.current.removeEventListener('error', handleAudioError);
      }
      if (progressSaveTimer.current) clearTimeout(progressSaveTimer.current);
      if (chunkPreloadTimer.current) clearTimeout(chunkPreloadTimer.current);
    };
  }, []);

  // Audio event handlers
  const handleTimeUpdate = useCallback(() => {
    if (audioRef.current) {
      setAudioState(prev => ({
        ...prev,
        currentTime: audioRef.current.currentTime,
      }));
    }
  }, []);

  const handleLoadedMetadata = useCallback(() => {
    if (audioRef.current) {
      setAudioState(prev => ({
        ...prev,
        duration: audioRef.current.duration,
        loading: false,
      }));
    }
  }, []);

  const handleAudioEnded = useCallback(() => {
    // Auto-advance to next chunk
    if (playNextChunkRef.current) {
      playNextChunkRef.current();
    } else {
      setAudioState(prev => ({
        ...prev,
        playing: false,
      }));
    }
  }, []);

  const handleAudioError = useCallback((e) => {
    console.error('Audio error:', e);
    setAudioState(prev => ({
      ...prev,
      playing: false,
      loading: false,
    }));
  }, []);

  // Load session and content
  const loadSession = useCallback(async () => {
    if (!contentType || !contentId) return;

    setLoading(true);
    setError(null);

    try {
      // Create or get existing session
      const sessionRes = await fetch(`${API_BASE}/session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content_type: contentType,
          content_id: contentId,
          mode: initialMode,
        }),
      });

      if (!sessionRes.ok) {
        throw new Error('Failed to create session');
      }

      const sessionData = await sessionRes.json();
      setSession(sessionData);

      // Get content
      const contentRes = await fetch(
        `${API_BASE}/content/${contentType}/${contentId}`
      );

      if (!contentRes.ok) {
        throw new Error('Failed to load content');
      }

      const contentData = await contentRes.json();
      setContent(contentData);

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [contentType, contentId, initialMode]);

  // Load on mount
  useEffect(() => {
    loadSession();
  }, [loadSession]);

  // Debounced progress saving
  const saveProgressDebounced = useCallback((positionChar, positionSeconds, readingTimeDelta) => {
    if (progressSaveTimer.current) {
      clearTimeout(progressSaveTimer.current);
    }

    progressSaveTimer.current = setTimeout(async () => {
      if (!session?.id) return;

      try {
        const res = await fetch(`${API_BASE}/session/${session.id}/progress`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            position_char: positionChar,
            position_seconds: positionSeconds,
            reading_time_delta: readingTimeDelta,
          }),
        });

        if (res.ok) {
          const data = await res.json();
          setSession(prev => ({
            ...prev,
            position_char: data.position_char,
            position_seconds: data.position_seconds,
            total_reading_time_seconds: data.total_reading_time_seconds,
          }));
        }
      } catch (err) {
        console.error('Failed to save progress:', err);
      }
    }, 1000); // Save after 1 second of no changes
  }, [session?.id]);

  // Update progress (for scroll tracking)
  const updateProgress = useCallback((positionChar, readingTimeDelta = 0) => {
    if (!session) return;

    // Update local state immediately
    setSession(prev => ({
      ...prev,
      position_char: positionChar,
    }));

    // Debounced save to server
    saveProgressDebounced(positionChar, null, readingTimeDelta);
  }, [session, saveProgressDebounced]);

  // Generate audio for chunks
  const generateAudio = useCallback(async (startChunk = 0, numChunks = 3) => {
    if (!session?.id) return null;

    setAudioState(prev => ({ ...prev, loading: true }));

    try {
      const res = await fetch(`${API_BASE}/session/${session.id}/audio`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start_chunk: startChunk, num_chunks: numChunks }),
      });

      if (!res.ok) {
        throw new Error('Failed to generate audio');
      }

      const data = await res.json();

      // Update buffered chunks and total count
      setAudioState(prev => ({
        ...prev,
        loading: false,
        totalChunks: data.total_chunks ?? prev.totalChunks,
        bufferedChunks: [
          ...prev.bufferedChunks.filter(c =>
            !data.generated_chunks.some(gc => gc.index === c.index)
          ),
          ...data.generated_chunks.filter(c => !c.error),
        ],
      }));

      return data;
    } catch (err) {
      setAudioState(prev => ({ ...prev, loading: false }));
      console.error('Failed to generate audio:', err);
      return null;
    }
  }, [session?.id]);

  // Play audio
  const playAudio = useCallback(async (chunkIndex = 0) => {
    if (!audioRef.current) return;

    // Check if chunk is buffered
    let chunk = audioState.bufferedChunks.find(c => c.index === chunkIndex);

    if (!chunk) {
      // Generate audio for this chunk and a few ahead
      const result = await generateAudio(chunkIndex, 3);
      if (!result?.generated_chunks?.length) return;
      chunk = result.generated_chunks.find(c => c.index === chunkIndex && !c.error);
      if (!chunk) return;
    }

    // Set audio source and play
    const audioUrl = `${API_BASE}/audio/${chunk.audio_path.split('/').pop()}`;
    audioRef.current.src = audioUrl;
    audioRef.current.playbackRate = session?.tts_speed || 1.0;
    audioRef.current.load();

    setAudioState(prev => ({
      ...prev,
      playing: true,
      loading: true,
      currentChunk: chunk,
    }));

    try {
      await audioRef.current.play();
    } catch (err) {
      console.error('Playback failed:', err);
      setAudioState(prev => ({ ...prev, playing: false, loading: false }));
    }

    // Pre-generate next chunks immediately
    if (chunkPreloadTimer.current) clearTimeout(chunkPreloadTimer.current);
    chunkPreloadTimer.current = setTimeout(() => {
      generateAudio(chunkIndex + 1, 5);  // Preload 5 chunks ahead
    }, 100);  // Start preloading quickly
  }, [audioState.bufferedChunks, generateAudio, session?.tts_speed]);

  // Update playback rate when speed changes
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = session?.tts_speed || 1.0;
    }
  }, [session?.tts_speed]);

  // Update playNextChunkRef when current chunk changes
  useEffect(() => {
    if (audioState.currentChunk !== null) {
      playNextChunkRef.current = () => {
        const nextIndex = audioState.currentChunk.index + 1;
        // Check if there are more chunks
        if (audioState.totalChunks && nextIndex >= audioState.totalChunks) {
          // No more chunks, stop playing
          setAudioState(prev => ({ ...prev, playing: false }));
        } else {
          playAudio(nextIndex);
        }
      };
    } else {
      playNextChunkRef.current = null;
    }
  }, [audioState.currentChunk, audioState.totalChunks, playAudio]);

  // Pause audio
  const pauseAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      setAudioState(prev => ({ ...prev, playing: false }));
    }
  }, []);

  // Toggle play/pause
  const togglePlayback = useCallback(() => {
    if (audioState.playing) {
      pauseAudio();
    } else {
      const chunkIndex = audioState.currentChunk?.index ?? 0;
      playAudio(chunkIndex);
    }
  }, [audioState.playing, audioState.currentChunk, playAudio, pauseAudio]);

  // Seek to position
  const seekTo = useCallback((seconds) => {
    if (audioRef.current) {
      audioRef.current.currentTime = seconds;
    }
  }, []);

  // Skip forward/backward
  const skipForward = useCallback((seconds = 30) => {
    if (audioRef.current) {
      audioRef.current.currentTime = Math.min(
        audioRef.current.duration,
        audioRef.current.currentTime + seconds
      );
    }
  }, []);

  const skipBackward = useCallback((seconds = 10) => {
    if (audioRef.current) {
      audioRef.current.currentTime = Math.max(0, audioRef.current.currentTime - seconds);
    }
  }, []);

  // Add bookmark
  const addBookmark = useCallback(async (positionChar, label = null) => {
    if (!session?.id) return null;

    try {
      const res = await fetch(`${API_BASE}/session/${session.id}/bookmark`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position_char: positionChar, label }),
      });

      if (!res.ok) throw new Error('Failed to add bookmark');

      const data = await res.json();
      setSession(prev => ({
        ...prev,
        bookmarks: data.bookmarks,
      }));

      return data;
    } catch (err) {
      console.error('Failed to add bookmark:', err);
      return null;
    }
  }, [session?.id]);

  // Remove bookmark
  const removeBookmark = useCallback(async (index) => {
    if (!session?.id) return null;

    try {
      const res = await fetch(
        `${API_BASE}/session/${session.id}/bookmark/${index}`,
        { method: 'DELETE' }
      );

      if (!res.ok) throw new Error('Failed to remove bookmark');

      const data = await res.json();
      setSession(prev => ({
        ...prev,
        bookmarks: data.bookmarks,
      }));

      return data;
    } catch (err) {
      console.error('Failed to remove bookmark:', err);
      return null;
    }
  }, [session?.id]);

  // Update TTS settings
  const updateSettings = useCallback(async (voice, speed) => {
    if (!session?.id) return null;

    try {
      const res = await fetch(`${API_BASE}/session/${session.id}/settings`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tts_voice: voice, tts_speed: speed }),
      });

      if (!res.ok) throw new Error('Failed to update settings');

      const data = await res.json();
      setSession(prev => ({
        ...prev,
        tts_voice: data.tts_voice,
        tts_speed: data.tts_speed,
      }));

      // Clear buffered chunks when settings change
      setAudioState(prev => ({
        ...prev,
        bufferedChunks: [],
      }));

      return data;
    } catch (err) {
      console.error('Failed to update settings:', err);
      return null;
    }
  }, [session?.id]);

  // Complete session
  const completeSession = useCallback(async () => {
    if (!session?.id) return null;

    try {
      const res = await fetch(`${API_BASE}/session/${session.id}/complete`, {
        method: 'POST',
      });

      if (!res.ok) throw new Error('Failed to complete session');

      const data = await res.json();
      setSession(data);
      return data;
    } catch (err) {
      console.error('Failed to complete session:', err);
      return null;
    }
  }, [session?.id]);

  // Get TTS voices
  const getVoices = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/tts/voices`);
      if (!res.ok) throw new Error('Failed to get voices');
      return await res.json();
    } catch (err) {
      console.error('Failed to get voices:', err);
      return null;
    }
  }, []);

  return {
    // State
    session,
    content,
    loading,
    error,
    audioState,

    // Audio controls
    playAudio,
    pauseAudio,
    togglePlayback,
    seekTo,
    skipForward,
    skipBackward,
    generateAudio,

    // Progress
    updateProgress,

    // Bookmarks
    addBookmark,
    removeBookmark,

    // Settings
    updateSettings,
    getVoices,

    // Session
    completeSession,
    reload: loadSession,
  };
}
