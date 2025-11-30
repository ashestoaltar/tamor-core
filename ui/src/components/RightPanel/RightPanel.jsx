import "./RightPanel.css";
import { useEffect, useState } from "react";
import axios from "axios";

export default function RightPanel({ lastMemoryMatches, activeMode }) {
  const [modes, setModes] = useState({});

  useEffect(() => {
    axios
      .get("/api/modes")
      .then((res) => setModes(res.data))
      .catch((err) => console.error(err));
  }, []);

  const currentMode = modes[activeMode] || null;

  return (
    <div className="right-panel">
      <h2>Insights</h2>

      <div className="mode-card">
        <div className="mode-title">
          Mode: <span>{activeMode}</span>
        </div>
        {currentMode ? (
          <>
            <div className="mode-summary">{currentMode.summary}</div>
            <div className="mode-when">
              <span className="label">Best for:</span>{" "}
              {currentMode.when_to_use}
            </div>
          </>
        ) : (
          <div className="mode-summary">
            Loading mode description...
          </div>
        )}
      </div>

      {!lastMemoryMatches || lastMemoryMatches.length === 0 ? (
        <p className="hint">
          Relevant memories will appear here after Tamor responds.
        </p>
      ) : (
        <div className="memory-insight">
          <h3>Relevant Memory</h3>
          {lastMemoryMatches.map((m) => (
            <div key={m.id} className="insight-item">
              <div className="insight-content">{m.content}</div>
              <div className="insight-meta">
                Score: {m.score.toFixed(2)} • #{m.id}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

