import React, { useState } from 'react';
import './GHMBadge.css';

function GHMBadge({ active, mode, onClick }) {
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

      {showTooltip && (
        <div className="ghm-tooltip">
          <strong>{label}</strong>
          <p>{description}</p>
          <ul>
            <li>Chronological constraint enforced</li>
            <li>Framework disclosure required</li>
            <li>No premature harmonization</li>
          </ul>
          {onClick && (
            <span className="ghm-tooltip-hint">Click to view details</span>
          )}
        </div>
      )}
    </div>
  );
}

export default GHMBadge;
