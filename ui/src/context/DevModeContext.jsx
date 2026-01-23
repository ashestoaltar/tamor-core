import React, { createContext, useContext, useState, useEffect } from "react";

const STORAGE_KEY = "tamor_dev_mode";

const DevModeContext = createContext(null);

export function DevModeProvider({ children }) {
  const [devMode, setDevModeState] = useState(() => {
    // Initialize from localStorage, default to false
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored === "true";
    } catch {
      return false;
    }
  });

  // Persist to localStorage when devMode changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, devMode ? "true" : "false");
    } catch (err) {
      console.warn("Failed to persist dev mode to localStorage:", err);
    }
  }, [devMode]);

  const setDevMode = (value) => {
    setDevModeState(Boolean(value));
  };

  const toggleDevMode = () => {
    setDevModeState((prev) => !prev);
  };

  const value = {
    devMode,
    setDevMode,
    toggleDevMode,
  };

  return (
    <DevModeContext.Provider value={value}>{children}</DevModeContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useDevMode() {
  const context = useContext(DevModeContext);
  if (context === null) {
    throw new Error("useDevMode must be used within a DevModeProvider");
  }
  return context;
}
