// src/components/RightPanel/tabs/WorkspaceTab.jsx
import React, { useEffect, useState } from "react";
import { apiFetch } from "../../../api/client";
import PipelinePanel from "../components/PipelinePanel.jsx";

function WorkspaceTab({ currentProjectId }) {
  const [notes, setNotes] = useState("");
  const [notesLoading, setNotesLoading] = useState(false);
  const [notesSaving, setNotesSaving] = useState(false);
  const [notesError, setNotesError] = useState("");

  useEffect(() => {
    if (!currentProjectId) {
      setNotes("");
      setNotesLoading(false);
      setNotesSaving(false);
      setNotesError("");
      return;
    }

    const fetchNotes = async () => {
      setNotesLoading(true);
      setNotesError("");
      try {
        const data = await apiFetch(`/projects/${currentProjectId}/notes`);
        setNotes(data.content || "");
      } catch (err) {
        console.error("Failed to fetch project notes", err);
        setNotesError("Error loading notes");
      } finally {
        setNotesLoading(false);
      }
    };

    fetchNotes();
  }, [currentProjectId]);

  const handleSaveNotes = async () => {
    if (!currentProjectId) return;
    setNotesSaving(true);
    setNotesError("");
    try {
      await apiFetch(`/projects/${currentProjectId}/notes`, {
        method: "POST",
        body: { content: notes },
      });
    } catch (err) {
      console.error("Failed to save project notes", err);
      setNotesError("Error saving notes");
    } finally {
      setNotesSaving(false);
    }
  };

  return (
    <div className="rp-tab-content">
      {/* Project Pipeline */}
      <PipelinePanel currentProjectId={currentProjectId} />

      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">Project Notes</h3>
          {notesSaving && (
            <span className="rp-tag rp-tag-muted">Saving…</span>
          )}
        </div>
        {notesLoading && (
          <div className="rp-section-body rp-small-text">
            Loading notes…
          </div>
        )}
        {notesError && (
          <div className="rp-section-body rp-error">{notesError}</div>
        )}
        <div className="rp-section-body">
          <textarea
            className="rp-notes-textarea"
            placeholder="Scratchpad for this project. Requirements, todos, quick notes, etc."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
        <div className="rp-section-footer">
          <button
            className="rp-button primary"
            onClick={handleSaveNotes}
            disabled={notesSaving}
          >
            Save notes
          </button>
        </div>
      </div>
    </div>
  );
}

export default WorkspaceTab;
