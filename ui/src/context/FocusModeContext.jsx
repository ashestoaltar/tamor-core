import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const FocusModeContext = createContext(null);

export function FocusModeProvider({ children }) {
  const [isFocusMode, setIsFocusMode] = useState(() => {
    const saved = localStorage.getItem('tamor_focus_mode');
    return saved === 'true';
  });

  const [focusSettings, setFocusSettings] = useState(() => {
    const saved = localStorage.getItem('tamor_focus_settings');
    return saved ? JSON.parse(saved) : {
      voiceFirst: true,        // Large mic button, voice input default
      autoEnterOnMobile: false, // Auto-enter focus mode on mobile
      showProjectIndicator: true,
      allowEscape: true,       // Allow keyboard/gesture exit
    };
  });

  // Persist state
  useEffect(() => {
    localStorage.setItem('tamor_focus_mode', isFocusMode.toString());
  }, [isFocusMode]);

  useEffect(() => {
    localStorage.setItem('tamor_focus_settings', JSON.stringify(focusSettings));
  }, [focusSettings]);

  const enterFocusMode = useCallback(() => {
    setIsFocusMode(true);
  }, []);

  const exitFocusMode = useCallback(() => {
    setIsFocusMode(false);
  }, []);

  const toggleFocusMode = useCallback(() => {
    setIsFocusMode(prev => !prev);
  }, []);

  const updateFocusSettings = useCallback((updates) => {
    setFocusSettings(prev => ({ ...prev, ...updates }));
  }, []);

  // Keyboard shortcut: Escape exits focus mode
  useEffect(() => {
    if (!isFocusMode || !focusSettings.allowEscape) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        exitFocusMode();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isFocusMode, focusSettings.allowEscape, exitFocusMode]);

  return (
    <FocusModeContext.Provider value={{
      isFocusMode,
      focusSettings,
      enterFocusMode,
      exitFocusMode,
      toggleFocusMode,
      updateFocusSettings,
    }}>
      {children}
    </FocusModeContext.Provider>
  );
}

export function useFocusMode() {
  const context = useContext(FocusModeContext);
  if (!context) {
    throw new Error('useFocusMode must be used within FocusModeProvider');
  }
  return context;
}

export default FocusModeContext;
