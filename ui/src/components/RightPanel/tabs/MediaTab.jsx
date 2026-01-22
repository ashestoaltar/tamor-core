// src/components/RightPanel/tabs/MediaTab.jsx
import React, { useState, useEffect } from "react";
import { apiFetch } from "../../../api/client";

function MediaTab({ currentProjectId }) {
  const [url, setUrl] = useState("");
  const [transcribing, setTranscribing] = useState(false);
  const [error, setError] = useState("");
  const [transcripts, setTranscripts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedTranscript, setSelectedTranscript] = useState(null);
  const [viewLoading, setViewLoading] = useState(false);

  // Load transcripts on mount and when project changes
  useEffect(() => {
    if (currentProjectId) {
      loadTranscripts();
    }
  }, [currentProjectId]);

  const loadTranscripts = async () => {
    setLoading(true);
    try {
      const data = await apiFetch(`/projects/${currentProjectId}/transcripts`);
      setTranscripts(data.transcripts || []);
    } catch (err) {
      console.error("Failed to load transcripts", err);
    } finally {
      setLoading(false);
    }
  };

  const handleTranscribe = async () => {
    if (!url.trim() || !currentProjectId) return;

    setTranscribing(true);
    setError("");

    try {
      const data = await apiFetch(
        `/projects/${currentProjectId}/transcribe-url`,
        {
          method: "POST",
          body: { url: url.trim() },
        }
      );

      if (data.error) {
        setError(data.error);
      } else {
        setUrl("");
        loadTranscripts();
        // Show the new transcript
        if (data.transcript_id) {
          handleViewTranscript(data.transcript_id);
        }
      }
    } catch (err) {
      console.error("Transcription failed", err);
      setError(err.message || "Transcription failed");
    } finally {
      setTranscribing(false);
    }
  };

  const handleViewTranscript = async (transcriptId) => {
    setViewLoading(true);
    try {
      const data = await apiFetch(
        `/projects/${currentProjectId}/transcripts/${transcriptId}`
      );
      setSelectedTranscript(data);
    } catch (err) {
      console.error("Failed to load transcript", err);
    } finally {
      setViewLoading(false);
    }
  };

  const handleDeleteTranscript = async (transcriptId) => {
    if (!confirm("Delete this transcript?")) return;

    try {
      await apiFetch(
        `/projects/${currentProjectId}/transcripts/${transcriptId}`,
        { method: "DELETE" }
      );
      loadTranscripts();
      if (selectedTranscript?.id === transcriptId) {
        setSelectedTranscript(null);
      }
    } catch (err) {
      console.error("Failed to delete transcript", err);
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds) return "";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const formatTimestamp = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="rp-tab-content">
      {/* Transcribe URL Section */}
      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">Transcribe URL</h3>
        </div>
        <div className="rp-section-body">
          <div className="rp-search-row">
            <input
              className="rp-input"
              placeholder="YouTube URL or video link..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !transcribing) {
                  handleTranscribe();
                }
              }}
              disabled={transcribing}
            />
            <button
              className="rp-btn rp-btn-primary"
              onClick={handleTranscribe}
              disabled={transcribing || !url.trim()}
            >
              {transcribing ? "Transcribing..." : "Transcribe"}
            </button>
          </div>
          {transcribing && (
            <div className="rp-info-text" style={{ marginTop: 8 }}>
              Downloading and transcribing... This may take 30-60 seconds.
            </div>
          )}
          {error && (
            <div className="rp-error-text" style={{ marginTop: 8 }}>
              {error}
            </div>
          )}
        </div>
      </div>

      {/* Transcripts List Section */}
      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">
            Transcripts {transcripts.length > 0 && `(${transcripts.length})`}
          </h3>
          <button
            className="rp-btn rp-btn-sm"
            onClick={loadTranscripts}
            disabled={loading}
          >
            Refresh
          </button>
        </div>
        <div className="rp-section-body">
          {loading && <div className="rp-info-text">Loading...</div>}
          {!loading && transcripts.length === 0 && (
            <div className="rp-info-text">
              No transcripts yet. Paste a YouTube URL above to get started.
            </div>
          )}
          {transcripts.map((t) => (
            <div
              key={t.id}
              className={`rp-list-item ${
                selectedTranscript?.id === t.id ? "rp-list-item-selected" : ""
              }`}
              onClick={() => handleViewTranscript(t.id)}
            >
              <div className="rp-list-item-main">
                <div className="rp-list-item-title">{t.title || "Untitled"}</div>
                <div className="rp-list-item-meta">
                  {t.source_type === "url" && "YouTube"}{" "}
                  {t.duration_seconds && `• ${formatDuration(t.duration_seconds)}`}{" "}
                  {t.language && `• ${t.language.toUpperCase()}`}
                </div>
              </div>
              <button
                className="rp-btn rp-btn-sm rp-btn-danger"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteTranscript(t.id);
                }}
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Transcript Viewer Section */}
      {selectedTranscript && (
        <div className="rp-section rp-section-flex">
          <div className="rp-section-header">
            <h3 className="rp-section-title">
              {selectedTranscript.title || "Transcript"}
            </h3>
            <button
              className="rp-btn rp-btn-sm"
              onClick={() => setSelectedTranscript(null)}
            >
              Close
            </button>
          </div>
          <div className="rp-section-body rp-section-scroll">
            {viewLoading && <div className="rp-info-text">Loading...</div>}
            {!viewLoading && selectedTranscript.segments && (
              <div className="rp-transcript-segments">
                {selectedTranscript.segments.map((seg, idx) => (
                  <div key={idx} className="rp-transcript-segment">
                    <span className="rp-transcript-time">
                      {formatTimestamp(seg.start)}
                    </span>
                    <span className="rp-transcript-text">{seg.text}</span>
                  </div>
                ))}
              </div>
            )}
            {!viewLoading && !selectedTranscript.segments && (
              <div className="rp-transcript-text">
                {selectedTranscript.text || "No transcript text available."}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default MediaTab;
