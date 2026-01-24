import React from "react";
import { useAuth } from "../../context/AuthContext";
import { useDevMode } from "../../context/DevModeContext";
import "./Settings.css";

/**
 * Settings panel for app configuration.
 * Used in mobile drawer and potentially desktop settings modal.
 */
export default function Settings() {
  const { user, logout } = useAuth();
  const { devMode, toggleDevMode } = useDevMode();

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

      {/* Voice Section (placeholder) */}
      <section className="settings-section">
        <h3 className="settings-section-title">Voice</h3>
        <div className="settings-section-content">
          <div className="settings-row">
            <div className="settings-row-info">
              <div className="settings-row-label">Voice Input</div>
              <div className="settings-row-description">
                Coming in Phase 3.4.3
              </div>
            </div>
            <div className="settings-row-control">
              <span className="settings-value-label settings-coming-soon">Soon</span>
            </div>
          </div>
          <div className="settings-row">
            <div className="settings-row-info">
              <div className="settings-row-label">Voice Output</div>
              <div className="settings-row-description">
                Text-to-speech for responses
              </div>
            </div>
            <div className="settings-row-control">
              <span className="settings-value-label settings-coming-soon">Soon</span>
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

      {/* Version info */}
      <div className="settings-footer">
        <div className="settings-version">Tamor v1.15</div>
        <div className="settings-tagline">Wholeness • Light • Insight</div>
      </div>
    </div>
  );
}
