/**
 * DebugPanel - Shows router trace info when ?debug=1 is in the URL
 *
 * Displays:
 * - provider_used: Which LLM provider handled the request
 * - model_used: The actual model name
 * - intents_detected: What the router classified the query as
 * - agent_sequence: Which agents processed the request
 * - timing_ms: Performance breakdown
 */

import { useState } from "react";
import "./DebugPanel.css";

export default function DebugPanel({ trace }) {
  const [isExpanded, setIsExpanded] = useState(false);

  console.log("[DebugPanel] Rendering with trace:", trace);

  if (!trace) {
    console.log("[DebugPanel] No trace, returning null");
    return null;
  }

  const {
    provider_used,
    model_used,
    intents_detected = [],
    intent_source,
    agent_sequence = [],
    retrieval_used,
    retrieval_count,
    timing_ms = {},
    errors = [],
  } = trace;

  // Format timing info
  const timingEntries = Object.entries(timing_ms);
  const totalMs = timing_ms.total || timingEntries.reduce((sum, [, ms]) => sum + ms, 0);

  return (
    <div className="debug-panel">
      <button
        type="button"
        className="debug-panel-toggle"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
      >
        <span className="debug-icon">🔧</span>
        <span className="debug-label">Debug</span>
        <span className="debug-provider">
          {provider_used || "—"}
        </span>
        <span className="debug-chevron">{isExpanded ? "▼" : "▶"}</span>
      </button>

      {isExpanded && (
        <div className="debug-panel-content">
          {/* Provider & Model */}
          <div className="debug-row">
            <span className="debug-key">Provider:</span>
            <span className={`debug-value provider-${provider_used || "none"}`}>
              {provider_used || "none"}
            </span>
          </div>
          {model_used && (
            <div className="debug-row">
              <span className="debug-key">Model:</span>
              <span className="debug-value">{model_used}</span>
            </div>
          )}

          {/* Intent Classification */}
          {intents_detected.length > 0 && (
            <div className="debug-row">
              <span className="debug-key">Intents:</span>
              <span className="debug-value">
                {intents_detected.join(", ")}
                {intent_source && <span className="debug-source">({intent_source})</span>}
              </span>
            </div>
          )}

          {/* Agent Sequence */}
          {agent_sequence.length > 0 && (
            <div className="debug-row">
              <span className="debug-key">Agents:</span>
              <span className="debug-value debug-agents">
                {agent_sequence.map((agent, i) => (
                  <span key={i} className="debug-agent-tag">
                    {agent}
                  </span>
                ))}
              </span>
            </div>
          )}

          {/* Retrieval */}
          {retrieval_used && (
            <div className="debug-row">
              <span className="debug-key">Retrieval:</span>
              <span className="debug-value">{retrieval_count} chunks</span>
            </div>
          )}

          {/* Timing */}
          {timingEntries.length > 0 && (
            <div className="debug-row debug-timing">
              <span className="debug-key">Timing:</span>
              <span className="debug-value">
                {timingEntries.map(([key, ms]) => (
                  <span key={key} className="debug-timing-item">
                    {key}: {ms}ms
                  </span>
                ))}
              </span>
            </div>
          )}

          {/* Errors */}
          {errors.length > 0 && (
            <div className="debug-row debug-errors">
              <span className="debug-key">Errors:</span>
              <span className="debug-value">
                {errors.map((err, i) => (
                  <div key={i} className="debug-error">{err}</div>
                ))}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
