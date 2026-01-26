import React, { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useDevMode } from "../../context/DevModeContext";
import { useVoiceSettings } from "../../context/VoiceSettingsContext";
import { useFocusMode } from "../../contexts/FocusModeContext";
import AboutTamor from "../AboutTamor/AboutTamor";
import "./Settings.css";

/**
 * Settings panel for app configuration.
 * Used in mobile drawer and potentially desktop settings modal.
 */
export default function Settings() {
  const { user, logout } = useAuth();
  const { devMode, toggleDevMode } = useDevMode();
  const { focusSettings, updateFocusSettings, enterFocusMode } = useFocusMode();
  const {
    inputEnabled,
    setInputEnabled,
    inputSupported,
    outputEnabled,
    setOutputEnabled,
    outputSupported,
    autoRead,
    setAutoRead,
    selectedVoiceName,
    setSelectedVoiceName,
    rate,
    setRate,
  } = useVoiceSettings();

  // Available voices (loaded async)
  const [voices, setVoices] = useState([]);
  const [testingSpeech, setTestingSpeech] = useState(false);
  const [showAbout, setShowAbout] = useState(false);

  // Load available voices
  useEffect(() => {
    if (!outputSupported) return;

    const loadVoices = () => {
      const availableVoices = window.speechSynthesis.getVoices();
      if (availableVoices.length > 0) {
        setVoices(availableVoices);
      }
    };

    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;

    return () => {
      window.speechSynthesis.onvoiceschanged = null;
    };
  }, [outputSupported]);

  // Test speech
  const handleTestSpeech = () => {
    if (!outputSupported || testingSpeech) return;

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(
      "Hello! I'm Tamor, your AI companion. How can I help you today?"
    );

    // Find selected voice
    if (selectedVoiceName) {
      const voice = voices.find((v) => v.name === selectedVoiceName);
      if (voice) utterance.voice = voice;
    }

    utterance.rate = rate;

    utterance.onstart = () => setTestingSpeech(true);
    utterance.onend = () => setTestingSpeech(false);
    utterance.onerror = () => setTestingSpeech(false);

    window.speechSynthesis.speak(utterance);
  };

  const handleStopTest = () => {
    window.speechSynthesis.cancel();
    setTestingSpeech(false);
  };

  return (
    <div className="settings-panel">
      {/* Account Section */}
      <section className="settings-section">
        <h3 className="settings-section-title">Account</h3>
        <div className="settings-section-content">
          <div className="settings-user-info">
            <div className="settings-user-avatar">
              {(user?.display_name || user?.username || "U").charAt(0).toUpperCase()}
            </div>
            <div className="settings-user-details">
              <div className="settings-user-name">
                {user?.display_name || user?.username || "Guest"}
              </div>
              {user?.username && (
                <div className="settings-user-username">@{user.username}</div>
              )}
            </div>
          </div>
          <button className="settings-button settings-button-outline" onClick={logout}>
            Sign Out
          </button>
        </div>
      </section>

      {/* Appearance Section */}
      <section className="settings-section">
        <h3 className="settings-section-title">Appearance</h3>
        <div className="settings-section-content">
          <div className="settings-row">
            <div className="settings-row-info">
              <div className="settings-row-label">Theme</div>
              <div className="settings-row-description">
                Dark theme is currently the only option
              </div>
            </div>
            <div className="settings-row-control">
              <span className="settings-value-label">Dark</span>
            </div>
          </div>
        </div>
      </section>

      {/* Voice Section */}
      <section className="settings-section">
        <h3 className="settings-section-title">Voice</h3>
        <div className="settings-section-content">
          {/* Voice Input Toggle */}
          <div className="settings-row">
            <div className="settings-row-info">
              <div className="settings-row-label">Voice Input</div>
              <div className="settings-row-description">
                {inputSupported
                  ? "Enable microphone button for speech-to-text"
                  : "Voice input is not supported in this browser"}
              </div>
            </div>
            <div className="settings-row-control">
              {inputSupported ? (
                <button
                  className={`settings-toggle ${inputEnabled ? "active" : ""}`}
                  onClick={() => setInputEnabled(!inputEnabled)}
                  role="switch"
                  aria-checked={inputEnabled}
                  aria-label="Voice Input"
                >
                  <span className="settings-toggle-track">
                    <span className="settings-toggle-thumb" />
                  </span>
                </button>
              ) : (
                <span className="settings-value-label settings-not-supported">
                  Not Supported
                </span>
              )}
            </div>
          </div>

          {/* Voice Output Toggle */}
          <div className="settings-row">
            <div className="settings-row-info">
              <div className="settings-row-label">Read Aloud</div>
              <div className="settings-row-description">
                {outputSupported
                  ? "Show read aloud buttons on messages"
                  : "Text-to-speech is not supported in this browser"}
              </div>
            </div>
            <div className="settings-row-control">
              {outputSupported ? (
                <button
                  className={`settings-toggle ${outputEnabled ? "active" : ""}`}
                  onClick={() => setOutputEnabled(!outputEnabled)}
                  role="switch"
                  aria-checked={outputEnabled}
                  aria-label="Read Aloud"
                >
                  <span className="settings-toggle-track">
                    <span className="settings-toggle-thumb" />
                  </span>
                </button>
              ) : (
                <span className="settings-value-label settings-not-supported">
                  Not Supported
                </span>
              )}
            </div>
          </div>

          {/* Auto-read Toggle */}
          {outputSupported && outputEnabled && (
            <div className="settings-row">
              <div className="settings-row-info">
                <div className="settings-row-label">Auto-Read Responses</div>
                <div className="settings-row-description">
                  Automatically read Tamor's responses aloud
                </div>
              </div>
              <div className="settings-row-control">
                <button
                  className={`settings-toggle ${autoRead ? "active" : ""}`}
                  onClick={() => setAutoRead(!autoRead)}
                  role="switch"
                  aria-checked={autoRead}
                  aria-label="Auto-Read Responses"
                >
                  <span className="settings-toggle-track">
                    <span className="settings-toggle-thumb" />
                  </span>
                </button>
              </div>
            </div>
          )}

          {/* Voice Selection */}
          {outputSupported && outputEnabled && voices.length > 0 && (
            <div className="settings-row">
              <div className="settings-row-info">
                <div className="settings-row-label">Voice</div>
                <div className="settings-row-description">
                  Select the voice for text-to-speech
                </div>
              </div>
              <div className="settings-row-control settings-row-control-wide">
                <select
                  className="settings-select"
                  value={selectedVoiceName || ""}
                  onChange={(e) => setSelectedVoiceName(e.target.value || null)}
                  aria-label="Voice selection"
                >
                  <option value="">System Default</option>
                  {voices.map((voice) => (
                    <option key={voice.name} value={voice.name}>
                      {voice.name} ({voice.lang})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* Speech Rate */}
          {outputSupported && outputEnabled && (
            <div className="settings-row">
              <div className="settings-row-info">
                <div className="settings-row-label">Speech Rate</div>
                <div className="settings-row-description">
                  {rate.toFixed(1)}x speed
                </div>
              </div>
              <div className="settings-row-control settings-row-control-wide">
                <input
                  type="range"
                  className="settings-slider"
                  min="0.5"
                  max="2"
                  step="0.1"
                  value={rate}
                  onChange={(e) => setRate(parseFloat(e.target.value))}
                  aria-label="Speech rate"
                />
              </div>
            </div>
          )}

          {/* Test Button */}
          {outputSupported && outputEnabled && (
            <div className="settings-row">
              <div className="settings-row-info">
                <div className="settings-row-label">Test Voice</div>
                <div className="settings-row-description">
                  Hear a sample with current settings
                </div>
              </div>
              <div className="settings-row-control">
                <button
                  className={`settings-button settings-button-outline ${testingSpeech ? "active" : ""}`}
                  onClick={testingSpeech ? handleStopTest : handleTestSpeech}
                >
                  {testingSpeech ? "Stop" : "Test"}
                </button>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Focus Mode Section */}
      <section className="settings-section">
        <h3 className="settings-section-title">Focus Mode</h3>
        <div className="settings-section-content">
          {/* Enter Focus Mode button */}
          <div className="settings-row">
            <div className="settings-row-info">
              <div className="settings-row-label">Focus Mode</div>
              <div className="settings-row-description">
                Minimal, distraction-free interface
              </div>
            </div>
            <div className="settings-row-control">
              <button
                className="settings-button settings-button-outline"
                onClick={enterFocusMode}
              >
                Enter
              </button>
            </div>
          </div>

          {/* Voice-first toggle */}
          <div className="settings-row">
            <div className="settings-row-info">
              <div className="settings-row-label">Voice-First Input</div>
              <div className="settings-row-description">
                Show large microphone button as primary input
              </div>
            </div>
            <div className="settings-row-control">
              <button
                className={`settings-toggle ${focusSettings.voiceFirst ? "active" : ""}`}
                onClick={() => updateFocusSettings({ voiceFirst: !focusSettings.voiceFirst })}
                role="switch"
                aria-checked={focusSettings.voiceFirst}
                aria-label="Voice-First Input"
              >
                <span className="settings-toggle-track">
                  <span className="settings-toggle-thumb" />
                </span>
              </button>
            </div>
          </div>

          {/* Auto-enter on mobile */}
          <div className="settings-row">
            <div className="settings-row-info">
              <div className="settings-row-label">Auto-Enter on Mobile</div>
              <div className="settings-row-description">
                Automatically enter Focus Mode on mobile devices
              </div>
            </div>
            <div className="settings-row-control">
              <button
                className={`settings-toggle ${focusSettings.autoEnterOnMobile ? "active" : ""}`}
                onClick={() => updateFocusSettings({ autoEnterOnMobile: !focusSettings.autoEnterOnMobile })}
                role="switch"
                aria-checked={focusSettings.autoEnterOnMobile}
                aria-label="Auto-Enter on Mobile"
              >
                <span className="settings-toggle-track">
                  <span className="settings-toggle-thumb" />
                </span>
              </button>
            </div>
          </div>

          {/* Show project indicator */}
          <div className="settings-row">
            <div className="settings-row-info">
              <div className="settings-row-label">Show Project Indicator</div>
              <div className="settings-row-description">
                Display current project name in Focus Mode
              </div>
            </div>
            <div className="settings-row-control">
              <button
                className={`settings-toggle ${focusSettings.showProjectIndicator ? "active" : ""}`}
                onClick={() => updateFocusSettings({ showProjectIndicator: !focusSettings.showProjectIndicator })}
                role="switch"
                aria-checked={focusSettings.showProjectIndicator}
                aria-label="Show Project Indicator"
              >
                <span className="settings-toggle-track">
                  <span className="settings-toggle-thumb" />
                </span>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Advanced Section */}
      <section className="settings-section settings-section-subtle">
        <h3 className="settings-section-title">Advanced</h3>
        <div className="settings-section-content">
          <div className="settings-row">
            <div className="settings-row-info">
              <div className="settings-row-label">Developer Mode</div>
              <div className="settings-row-description">
                Show debugging tools and technical panels
              </div>
            </div>
            <div className="settings-row-control">
              <button
                className={`settings-toggle ${devMode ? "active" : ""}`}
                onClick={toggleDevMode}
                role="switch"
                aria-checked={devMode}
                aria-label="Developer Mode"
              >
                <span className="settings-toggle-track">
                  <span className="settings-toggle-thumb" />
                </span>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Documentation Section */}
      <section className="settings-section">
        <h3 className="settings-section-title">Documentation</h3>
        <div className="settings-section-content">
          <div className="settings-row">
            <div className="settings-row-info">
              <div className="settings-row-label">Learn about Tamor</div>
              <div className="settings-row-description">
                Features, design principles, and API reference
              </div>
            </div>
            <div className="settings-row-control">
              <button
                className="settings-button settings-button-outline"
                onClick={() => setShowAbout(true)}
              >
                About
              </button>
            </div>
          </div>
          <div className="settings-docs-links">
            <a
              href="https://github.com/ashestoaltar/tamor-core/blob/main/docs/INDEX.md"
              target="_blank"
              rel="noopener noreferrer"
              className="settings-doc-link"
            >
              Documentation Index
            </a>
            <a
              href="https://github.com/ashestoaltar/tamor-core/blob/main/docs/Features.md"
              target="_blank"
              rel="noopener noreferrer"
              className="settings-doc-link"
            >
              Features Guide
            </a>
            <a
              href="https://github.com/ashestoaltar/tamor-core/blob/main/docs/BOUNDARIES.md"
              target="_blank"
              rel="noopener noreferrer"
              className="settings-doc-link"
            >
              Boundaries & Principles
            </a>
          </div>
        </div>
      </section>

      {/* Version info */}
      <div className="settings-footer">
        <div className="settings-version">Tamor v1.32</div>
        <div className="settings-tagline">Wholeness • Light • Insight</div>
      </div>

      {/* About Tamor Modal */}
      {showAbout && (
        <div className="settings-modal-overlay" onClick={() => setShowAbout(false)}>
          <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
            <AboutTamor onClose={() => setShowAbout(false)} />
          </div>
        </div>
      )}
    </div>
  );
}
