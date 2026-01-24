// ui/src/components/RightPanel/tabs/ReferencesTab.jsx
/**
 * Scripture reference lookup and management tab.
 * Provides passage lookup, translation comparison, and module management.
 */

import React, { useState, useEffect, useCallback } from "react";
import { useReferences } from "../../../hooks/useReferences";
import { parseReference } from "../../../utils/referenceParser";
import CitationCard from "../../CitationCard";

// localStorage key for recent lookups
const RECENT_LOOKUPS_KEY = "tamor_recent_scripture_lookups";
const MAX_RECENT = 10;

/**
 * Load recent lookups from localStorage.
 */
function loadRecentLookups() {
  try {
    const stored = localStorage.getItem(RECENT_LOOKUPS_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

/**
 * Save recent lookups to localStorage.
 */
function saveRecentLookups(lookups) {
  try {
    localStorage.setItem(RECENT_LOOKUPS_KEY, JSON.stringify(lookups));
  } catch {
    // ignore storage errors
  }
}

/**
 * Add a lookup to recent history.
 */
function addToRecent(ref, translation, recentList) {
  const entry = { ref, translation, timestamp: Date.now() };
  // Remove duplicate if exists
  const filtered = recentList.filter(
    (r) => !(r.ref === ref && r.translation === translation)
  );
  // Add to front
  const updated = [entry, ...filtered].slice(0, MAX_RECENT);
  saveRecentLookups(updated);
  return updated;
}

function ReferencesTab({ onSendToChat }) {
  const {
    lookup,
    compare,
    getTranslations,
    getInstalledModules,
    loading,
    error,
    clearError,
  } = useReferences();

  // Lookup state
  const [refInput, setRefInput] = useState("");
  const [selectedTranslation, setSelectedTranslation] = useState("KJV");
  const [lookupResult, setLookupResult] = useState(null);

  // Compare state
  const [compareRef, setCompareRef] = useState("");
  const [compareTranslations, setCompareTranslations] = useState([
    "KJV",
    "ASV",
  ]);
  const [compareResults, setCompareResults] = useState(null);
  const [comparingMode, setComparingMode] = useState(false);

  // Module management state
  const [translations, setTranslations] = useState([]);
  const [installedModules, setInstalledModules] = useState([]);
  const [modulesExpanded, setModulesExpanded] = useState(false);

  // Recent lookups
  const [recentLookups, setRecentLookups] = useState([]);

  // Load translations and installed modules on mount
  useEffect(() => {
    const loadData = async () => {
      const [trans, installed] = await Promise.all([
        getTranslations(),
        getInstalledModules(),
      ]);
      setTranslations(trans);
      setInstalledModules(installed);
    };
    loadData();
    setRecentLookups(loadRecentLookups());
  }, [getTranslations, getInstalledModules]);

  // Handle lookup
  const handleLookup = useCallback(async () => {
    if (!refInput.trim()) return;

    clearError();
    const parsed = parseReference(refInput);
    const normalizedRef = parsed ? parsed.normalized : refInput.trim();

    const results = await lookup(normalizedRef, {
      translations: [selectedTranslation],
      sources: ["sword"],
    });

    if (results && results.length > 0) {
      setLookupResult({
        ref: normalizedRef,
        translation: selectedTranslation,
        data: results[0],
      });
      setRecentLookups((prev) =>
        addToRecent(normalizedRef, selectedTranslation, prev)
      );
    } else {
      setLookupResult(null);
    }
  }, [refInput, selectedTranslation, lookup, clearError]);

  // Handle compare
  const handleCompare = useCallback(async () => {
    if (!compareRef.trim() || compareTranslations.length < 2) return;

    clearError();
    const parsed = parseReference(compareRef);
    const normalizedRef = parsed ? parsed.normalized : compareRef.trim();

    const results = await compare(normalizedRef, compareTranslations);

    if (results) {
      setCompareResults({
        ref: normalizedRef,
        translations: results,
      });
    } else {
      setCompareResults(null);
    }
  }, [compareRef, compareTranslations, compare, clearError]);

  // Handle recent lookup click
  const handleRecentClick = useCallback(
    async (recent) => {
      setRefInput(recent.ref);
      setSelectedTranslation(recent.translation);

      const results = await lookup(recent.ref, {
        translations: [recent.translation],
        sources: ["sword"],
      });

      if (results && results.length > 0) {
        setLookupResult({
          ref: recent.ref,
          translation: recent.translation,
          data: results[0],
        });
      }
    },
    [lookup]
  );

  // Handle send to chat
  const handleSendToChat = useCallback(
    (ref, text) => {
      if (onSendToChat) {
        const message = `Regarding ${ref}:\n\n"${text}"\n\nPlease discuss this passage.`;
        onSendToChat(message);
      }
    },
    [onSendToChat]
  );

  // Toggle compare translation
  const toggleCompareTranslation = useCallback((code) => {
    setCompareTranslations((prev) => {
      if (prev.includes(code)) {
        // Don't allow fewer than 2 translations
        if (prev.length <= 2) return prev;
        return prev.filter((c) => c !== code);
      } else {
        return [...prev, code];
      }
    });
  }, []);

  // Clear recent lookups
  const clearRecent = useCallback(() => {
    setRecentLookups([]);
    saveRecentLookups([]);
  }, []);

  return (
    <div className="rp-tab-content">
      {/* Lookup Section */}
      <div className="rp-section">
        <div className="rp-section-header">
          <span className="rp-section-title">Passage Lookup</span>
        </div>
        <div className="rp-section-body">
          <div className="rp-ref-lookup-row">
            <input
              type="text"
              className="rp-input rp-ref-input"
              placeholder="e.g., John 3:16, Gen 1:1-3"
              value={refInput}
              onChange={(e) => setRefInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLookup()}
            />
            <select
              className="rp-select rp-translation-select"
              value={selectedTranslation}
              onChange={(e) => setSelectedTranslation(e.target.value)}
            >
              {installedModules.length > 0
                ? installedModules.map((mod) => (
                    <option key={mod} value={mod}>
                      {mod}
                    </option>
                  ))
                : translations.map((t) => (
                    <option key={t.code} value={t.code}>
                      {t.code} - {t.name}
                    </option>
                  ))}
            </select>
            <button
              className="rp-button primary"
              onClick={handleLookup}
              disabled={loading || !refInput.trim()}
            >
              {loading ? "..." : "Look up"}
            </button>
          </div>

          {error && <div className="rp-error-text rp-ref-error">{error}</div>}

          {lookupResult && lookupResult.data && (
            <div className="rp-ref-result">
              <CitationCard
                reference={{
                  ref: lookupResult.ref,
                  translation: lookupResult.translation,
                  text: lookupResult.data.text,
                  source: lookupResult.data.source || "sword",
                }}
                defaultExpanded={true}
              />
              {onSendToChat && (
                <button
                  className="rp-button subtle rp-ref-chat-btn"
                  onClick={() =>
                    handleSendToChat(lookupResult.ref, lookupResult.data.text)
                  }
                >
                  Discuss in chat
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Compare Section */}
      <div className="rp-section">
        <div className="rp-section-header">
          <span className="rp-section-title">Compare Translations</span>
          <button
            className={`rp-btn rp-btn-sm ${comparingMode ? "rp-btn-primary" : ""}`}
            onClick={() => setComparingMode(!comparingMode)}
          >
            {comparingMode ? "Hide" : "Show"}
          </button>
        </div>

        {comparingMode && (
          <div className="rp-section-body">
            <div className="rp-ref-compare-input">
              <input
                type="text"
                className="rp-input"
                placeholder="Reference to compare"
                value={compareRef}
                onChange={(e) => setCompareRef(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCompare()}
              />
            </div>

            <div className="rp-ref-compare-translations">
              <span className="rp-label">Select translations:</span>
              <div className="rp-ref-translation-toggles">
                {installedModules.map((mod) => (
                  <label key={mod} className="rp-ref-translation-toggle">
                    <input
                      type="checkbox"
                      checked={compareTranslations.includes(mod)}
                      onChange={() => toggleCompareTranslation(mod)}
                    />
                    <span>{mod}</span>
                  </label>
                ))}
              </div>
            </div>

            <button
              className="rp-button primary"
              onClick={handleCompare}
              disabled={
                loading ||
                !compareRef.trim() ||
                compareTranslations.length < 2
              }
            >
              {loading ? "Comparing..." : "Compare"}
            </button>

            {compareResults && (
              <div className="rp-ref-compare-results">
                <div className="rp-ref-compare-header">
                  Comparing: {compareResults.ref}
                </div>
                {compareResults.translations.map((t) => (
                  <div key={t.translation} className="rp-ref-compare-item">
                    <div className="rp-ref-compare-label">{t.translation}</div>
                    <div className="rp-ref-compare-text">{t.text}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Recent Lookups Section */}
      {recentLookups.length > 0 && (
        <div className="rp-section">
          <div className="rp-section-header">
            <span className="rp-section-title">Recent Lookups</span>
            <button className="rp-btn rp-btn-sm" onClick={clearRecent}>
              Clear
            </button>
          </div>
          <div className="rp-section-body">
            <div className="rp-ref-recent-list">
              {recentLookups.map((recent, idx) => (
                <button
                  key={idx}
                  className="rp-ref-recent-item"
                  onClick={() => handleRecentClick(recent)}
                >
                  <span className="rp-ref-recent-ref">{recent.ref}</span>
                  <span className="rp-ref-recent-translation">
                    {recent.translation}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Module Management Section */}
      <div className="rp-section">
        <div className="rp-section-header">
          <span className="rp-section-title">Bible Modules</span>
          <button
            className="rp-btn rp-btn-sm"
            onClick={() => setModulesExpanded(!modulesExpanded)}
          >
            {modulesExpanded ? "Hide" : "Manage"}
          </button>
        </div>

        {modulesExpanded && (
          <div className="rp-section-body">
            <div className="rp-ref-modules-section">
              <div className="rp-section-subtitle">Installed</div>
              {installedModules.length === 0 ? (
                <div className="rp-info-text">No modules installed</div>
              ) : (
                <div className="rp-ref-module-list">
                  {installedModules.map((mod) => {
                    const info = translations.find((t) => t.code === mod);
                    return (
                      <div key={mod} className="rp-ref-module-item">
                        <span className="rp-tag rp-tag-positive">{mod}</span>
                        {info && (
                          <span className="rp-ref-module-name">
                            {info.name}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="rp-ref-modules-section">
              <div className="rp-section-subtitle">Available</div>
              <div className="rp-ref-module-list">
                {translations
                  .filter((t) => !installedModules.includes(t.code))
                  .slice(0, 10)
                  .map((t) => (
                    <div key={t.code} className="rp-ref-module-item">
                      <span className="rp-tag rp-tag-muted">{t.code}</span>
                      <span className="rp-ref-module-name">{t.name}</span>
                    </div>
                  ))}
              </div>
              <div className="rp-help-text">
                Run setup_references.py to install additional modules.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ReferencesTab;
