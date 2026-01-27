import React, { useState } from 'react';
import './GHMBadge.css';

function GHMBadge({ active, mode, profile, onClick }) {
  const [showTooltip, setShowTooltip] = useState(false);

  if (!active) {
    return null;
  }

  const label = mode === 'soft_ghm' ? 'GHM (soft)' : 'GHM';
  const description = mode === 'soft_ghm'
    ? 'Soft hermeneutic mode: framework disclosure active'
    : 'Global Hermeneutic Mode: full constraint checking active';

  return (
    <div
      className="ghm-badge-container"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <button
        className={`ghm-badge ${mode === 'soft_ghm' ? 'soft' : 'full'}`}
        onClick={onClick}
        title={description}
      >
        {label}
      </button>

      {profile && (
        <span className="ghm-profile-badge" title="Trajectory Lens: weights evidence toward canonical continuity">
          Trajectory Lens
        </span>
      )}

      {showTooltip && (
        <div className="ghm-tooltip">
          <strong>{label}</strong>
          <p>{description}</p>
          <ul>
            <li>Chronological constraint enforced</li>
            <li>Framework disclosure required</li>
            <li>No premature harmonization</li>
          </ul>
          {profile && (
            <>
              <strong style={{ marginTop: 8 }}>Profile: Trajectory Lens</strong>
              <p>Weights evidence toward canonical continuity. Interpretive framework, not doctrinal assertion.</p>
            </>
          )}
          {onClick && (
            <span className="ghm-tooltip-hint">Click to view details</span>
          )}
        </div>
      )}
    </div>
  );
}

export default GHMBadge;
