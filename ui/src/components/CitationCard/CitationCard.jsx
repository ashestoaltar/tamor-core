// ui/src/components/CitationCard/CitationCard.jsx
import React, { useState, useCallback } from "react";
import "./CitationCard.css";

/**
 * Display component for scripture citations.
 *
 * Supports two display modes:
 * - Compact: Reference string, source badge, text preview, expand button
 * - Expanded: Full text, Hebrew if available, translation selector, actions
 *
 * @param {Object} props
 * @param {Object} props.reference - The reference data object
 * @param {string} props.reference.ref_string - Display string (e.g., "Genesis 1:1-3")
 * @param {string} props.reference.source - Source identifier ("sword" or "sefaria")
 * @param {string} props.reference.translation - Translation code (e.g., "KJV")
 * @param {string} props.reference.text - The passage text
 * @param {string} [props.reference.hebrew] - Hebrew text if available
 * @param {string} props.reference.book - Book name
 * @param {number} props.reference.chapter - Chapter number
 * @param {number} props.reference.verse_start - Starting verse
 * @param {number} [props.reference.verse_end] - Ending verse
 * @param {boolean} [props.defaultExpanded=false] - Start in expanded mode
 * @param {function} [props.onCompare] - Callback for compare action
 * @param {boolean} [props.compact=false] - Ultra-compact inline mode
 * @param {string} [props.className] - Additional CSS classes
 */
export default function CitationCard({
  reference,
  defaultExpanded = false,
  onCompare,
  compact = false,
  className = "",
}) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [copiedText, setCopiedText] = useState(null);

  const {
    ref_string,
    source,
    translation,
    text,
    hebrew,
    book,
    chapter,
    verse_start,
    verse_end,
  } = reference;

  // Generate preview text (first ~100 chars)
  const previewText = text?.length > 100 ? `${text.slice(0, 100)}...` : text;

  // Format source badge text
  const sourceBadge =
    source === "sword"
      ? translation || "SWORD"
      : source === "sefaria"
      ? "Sefaria"
      : source;

  // Build external link URL
  const getExternalLink = useCallback(() => {
    if (source === "sefaria") {
      // Sefaria link format: https://www.sefaria.org/Genesis.1.1-3
      const ref = verse_end
        ? `${book}.${chapter}.${verse_start}-${verse_end}`
        : `${book}.${chapter}.${verse_start}`;
      return `https://www.sefaria.org/${ref.replace(/ /g, "_")}`;
    } else {
      // BibleGateway link
      const verseRef = verse_end
        ? `${book}+${chapter}:${verse_start}-${verse_end}`
        : `${book}+${chapter}:${verse_start}`;
      return `https://www.biblegateway.com/passage/?search=${encodeURIComponent(
        verseRef
      )}&version=${translation || "KJV"}`;
    }
  }, [source, book, chapter, verse_start, verse_end, translation]);

  // Copy text to clipboard
  const handleCopy = useCallback(
    async (textType) => {
      const textToCopy = textType === "hebrew" ? hebrew : text;
      if (!textToCopy) return;

      try {
        await navigator.clipboard.writeText(textToCopy);
        setCopiedText(textType);
        setTimeout(() => setCopiedText(null), 2000);
      } catch (err) {
        console.error("Failed to copy:", err);
      }
    },
    [text, hebrew]
  );

  // Toggle expanded state
  const toggleExpanded = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  // Handle compare action
  const handleCompare = useCallback(() => {
    if (onCompare) {
      onCompare(reference);
    }
  }, [onCompare, reference]);

  // Compact inline mode
  if (compact) {
    return (
      <span
        className={`citation-card citation-card-inline ${className}`}
        title={text}
      >
        <span className="citation-ref-inline">{ref_string}</span>
        <span className="citation-badge-inline">{sourceBadge}</span>
      </span>
    );
  }

  return (
    <div
      className={`citation-card ${isExpanded ? "citation-card-expanded" : ""} ${className}`}
    >
      {/* Header: Reference + Source Badge + Expand Button */}
      <div className="citation-header" onClick={toggleExpanded}>
        <div className="citation-ref-wrapper">
          <span className="citation-ref">{ref_string}</span>
          <span
            className={`citation-badge citation-badge-${source}`}
            title={`Source: ${source}`}
          >
            {sourceBadge}
          </span>
        </div>

        <button
          type="button"
          className="citation-expand-btn"
          onClick={(e) => {
            e.stopPropagation();
            toggleExpanded();
          }}
          aria-label={isExpanded ? "Collapse citation" : "Expand citation"}
          aria-expanded={isExpanded}
        >
          <svg
            className={`citation-expand-icon ${isExpanded ? "citation-expand-icon-rotated" : ""}`}
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
      </div>

      {/* Text Content */}
      <div className="citation-content">
        {isExpanded ? (
          <>
            {/* Full English Text */}
            <p className="citation-text citation-text-full">{text}</p>

            {/* Hebrew Text (if available) */}
            {hebrew && (
              <div className="citation-hebrew-wrapper">
                <div className="citation-hebrew-label">
                  <span>Hebrew</span>
                  <button
                    type="button"
                    className="citation-copy-btn citation-copy-btn-small"
                    onClick={() => handleCopy("hebrew")}
                    title="Copy Hebrew text"
                  >
                    {copiedText === "hebrew" ? (
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    ) : (
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                      </svg>
                    )}
                  </button>
                </div>
                <p className="citation-hebrew" dir="rtl" lang="he">
                  {hebrew}
                </p>
              </div>
            )}

            {/* Actions Bar */}
            <div className="citation-actions">
              {/* Copy Button */}
              <button
                type="button"
                className="citation-action-btn"
                onClick={() => handleCopy("text")}
                title="Copy text"
              >
                {copiedText === "text" ? (
                  <>
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    <span>Copied</span>
                  </>
                ) : (
                  <>
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                    </svg>
                    <span>Copy</span>
                  </>
                )}
              </button>

              {/* Compare Button (if callback provided) */}
              {onCompare && (
                <button
                  type="button"
                  className="citation-action-btn"
                  onClick={handleCompare}
                  title="Compare translations"
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <line x1="18" y1="20" x2="18" y2="10" />
                    <line x1="12" y1="20" x2="12" y2="4" />
                    <line x1="6" y1="20" x2="6" y2="14" />
                  </svg>
                  <span>Compare</span>
                </button>
              )}

              {/* External Link */}
              <a
                href={getExternalLink()}
                target="_blank"
                rel="noopener noreferrer"
                className="citation-action-btn citation-action-link"
                title={`Open in ${source === "sefaria" ? "Sefaria" : "BibleGateway"}`}
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
                <span>{source === "sefaria" ? "Sefaria" : "BibleGateway"}</span>
              </a>
            </div>
          </>
        ) : (
          /* Preview Text */
          <p className="citation-text citation-text-preview">{previewText}</p>
        )}
      </div>
    </div>
  );
}
