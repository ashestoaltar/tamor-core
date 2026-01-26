import React, { useState } from 'react';
import './EpistemicBadge.css';

/**
 * Epistemic Badge Component
 *
 * Shows answer classification with progressive disclosure:
 * - Badge (always visible)
 * - Popover (on hover/tap)
 * - Expandable explanation (in popover)
 */

const BADGE_CONFIG = {
  deterministic: {
    icon: '✔︎',
    label: 'Exact',
    color: 'var(--success-color)',
    description: 'Computed from data — this is factual.'
  },
  grounded: {
    icon: '●',
    label: 'Grounded',
    color: 'var(--info-color)',
    description: 'Based on cited sources.'
  },
  contested: {
    icon: '◐',
    label: 'Contested',
    color: 'var(--warning-color)',
    description: 'Grounded but interpretive — other readings exist.'
  }
};

const CONTESTATION_LABELS = {
  C1: 'Intra-tradition nuance',
  C2: 'Cross-tradition split',
  C3: 'Minority position'
};

function EpistemicBadge({ epistemic }) {
  const [showPopover, setShowPopover] = useState(false);
  const [showExpanded, setShowExpanded] = useState(false);

  if (!epistemic || !epistemic.badge) {
    return null;
  }

  const config = BADGE_CONFIG[epistemic.badge];
  if (!config) {
    return null;
  }

  const handleMouseEnter = () => setShowPopover(true);
  const handleMouseLeave = () => {
    setShowPopover(false);
    setShowExpanded(false);
  };
  const handleClick = () => setShowPopover(!showPopover);

  return (
    <div
      className="epistemic-badge-container"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <button
        className={`epistemic-badge badge-${epistemic.badge}`}
        onClick={handleClick}
        title={config.label}
        style={{ color: config.color }}
      >
        <span className="badge-icon">{config.icon}</span>
      </button>

      {showPopover && (
        <div className="epistemic-popover">
          <div className="popover-header">
            <span className="popover-icon" style={{ color: config.color }}>
              {config.icon}
            </span>
            <span className="popover-label">{config.label}</span>
          </div>

          <p className="popover-description">{config.description}</p>

          {epistemic.is_contested && (
            <div className="contestation-info">
              {epistemic.contestation_level && (
                <div className="contestation-level">
                  <strong>Level:</strong>{' '}
                  {CONTESTATION_LABELS[epistemic.contestation_level] || epistemic.contestation_level}
                </div>
              )}

              {epistemic.contested_domains?.length > 0 && (
                <div className="contested-domains">
                  <strong>Domains:</strong>{' '}
                  {epistemic.contested_domains.join(', ')}
                </div>
              )}

              {!showExpanded && epistemic.alternative_positions?.length > 0 && (
                <button
                  className="expand-btn"
                  onClick={() => setShowExpanded(true)}
                >
                  Why is this contested?
                </button>
              )}

              {showExpanded && epistemic.alternative_positions?.length > 0 && (
                <div className="alternatives">
                  <strong>Other positions:</strong>
                  <ul>
                    {epistemic.alternative_positions.map((pos, i) => (
                      <li key={i}>{pos}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {epistemic.has_sources && epistemic.sources?.length > 0 && (
            <div className="sources-info">
              <strong>Sources:</strong>
              <ul>
                {epistemic.sources.slice(0, 3).map((source, i) => (
                  <li key={i}>{source}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default EpistemicBadge;
