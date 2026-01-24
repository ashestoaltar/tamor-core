// ui/src/context/VoiceSettingsContext.jsx
// Context for managing voice input/output settings across the app
import React, { createContext, useCallback, useContext, useEffect, useState } from "react";

// Storage keys
const STORAGE_KEYS = {
  inputEnabled: "tamor_voice_input_enabled",
  outputEnabled: "tamor_voice_output_enabled",
  autoRead: "tamor_voice_auto_read",
  selectedVoice: "tamor_voice_selected",
  rate: "tamor_voice_rate",
};

// Default values
const DEFAULTS = {
  inputEnabled: true,
  outputEnabled: true,
  autoRead: false,
  selectedVoice: null,
  rate: 1,
};

const VoiceSettingsContext = createContext(null);

/**
 * Helper to safely read from localStorage
 */
function getStoredValue(key, defaultValue, parser = (v) => v) {
  if (typeof window === "undefined") return defaultValue;
  try {
    const stored = localStorage.getItem(key);
    if (stored === null) return defaultValue;
    return parser(stored);
  } catch {
    return defaultValue;
  }
}

/**
 * Helper to safely write to localStorage
 */
function setStoredValue(key, value) {
  try {
    localStorage.setItem(key, String(value));
  } catch {
    // Ignore storage errors
  }
}

/**
 * Provider component for voice settings
 */
export function VoiceSettingsProvider({ children }) {
  // Voice input settings
  const [inputEnabled, setInputEnabledState] = useState(() =>
    getStoredValue(STORAGE_KEYS.inputEnabled, DEFAULTS.inputEnabled, (v) => v === "true")
  );

  // Voice output settings
  const [outputEnabled, setOutputEnabledState] = useState(() =>
    getStoredValue(STORAGE_KEYS.outputEnabled, DEFAULTS.outputEnabled, (v) => v === "true")
  );

  const [autoRead, setAutoReadState] = useState(() =>
    getStoredValue(STORAGE_KEYS.autoRead, DEFAULTS.autoRead, (v) => v === "true")
  );

  const [selectedVoiceName, setSelectedVoiceNameState] = useState(() =>
    getStoredValue(STORAGE_KEYS.selectedVoice, DEFAULTS.selectedVoice)
  );

  const [rate, setRateState] = useState(() =>
    getStoredValue(STORAGE_KEYS.rate, DEFAULTS.rate, (v) => {
      const parsed = parseFloat(v);
      return !isNaN(parsed) && parsed >= 0.5 && parsed <= 2 ? parsed : DEFAULTS.rate;
    })
  );

  // Setters with persistence
  const setInputEnabled = useCallback((value) => {
    setInputEnabledState(value);
    setStoredValue(STORAGE_KEYS.inputEnabled, value);
  }, []);

  const setOutputEnabled = useCallback((value) => {
    setOutputEnabledState(value);
    setStoredValue(STORAGE_KEYS.outputEnabled, value);
  }, []);

  const setAutoRead = useCallback((value) => {
    setAutoReadState(value);
    setStoredValue(STORAGE_KEYS.autoRead, value);
  }, []);

  const setSelectedVoiceName = useCallback((value) => {
    setSelectedVoiceNameState(value);
    setStoredValue(STORAGE_KEYS.selectedVoice, value || "");
  }, []);

  const setRate = useCallback((value) => {
    const clamped = Math.max(0.5, Math.min(2, value));
    setRateState(clamped);
    setStoredValue(STORAGE_KEYS.rate, clamped);
  }, []);

  // Check browser support
  const [inputSupported, setInputSupported] = useState(false);
  const [outputSupported, setOutputSupported] = useState(false);

  useEffect(() => {
    // Check speech recognition support
    const SpeechRecognition =
      typeof window !== "undefined"
        ? window.SpeechRecognition || window.webkitSpeechRecognition
        : null;
    setInputSupported(Boolean(SpeechRecognition));

    // Check speech synthesis support
    setOutputSupported(
      typeof window !== "undefined" && "speechSynthesis" in window
    );
  }, []);

  const value = {
    // Voice input
    inputEnabled,
    setInputEnabled,
    inputSupported,

    // Voice output
    outputEnabled,
    setOutputEnabled,
    outputSupported,

    // Auto-read
    autoRead,
    setAutoRead,

    // Voice selection (name/URI)
    selectedVoiceName,
    setSelectedVoiceName,

    // Speech rate
    rate,
    setRate,
  };

  return (
    <VoiceSettingsContext.Provider value={value}>
      {children}
    </VoiceSettingsContext.Provider>
  );
}

/**
 * Hook to access voice settings
 */
export function useVoiceSettings() {
  const context = useContext(VoiceSettingsContext);
  if (!context) {
    throw new Error("useVoiceSettings must be used within a VoiceSettingsProvider");
  }
  return context;
}

export default VoiceSettingsContext;
