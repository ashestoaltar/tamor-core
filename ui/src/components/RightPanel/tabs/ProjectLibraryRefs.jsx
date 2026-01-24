import React, { useState, useEffect } from 'react';
import { useLibrary } from '../../../hooks/useLibrary';
import './ProjectLibraryRefs.css';

const getFileIcon = (mimeType) => {
  if (!mimeType) return '📄';
  if (mimeType.includes('pdf')) return '📕';
  if (mimeType.includes('epub')) return '📘';
  if (mimeType.includes('audio')) return '🎵';
  if (mimeType.includes('video')) return '🎬';
  return '📄';
};

function ProjectLibraryRefs({ projectId, onOpenLibrary }) {
  const { getProjectRefs, removeFromProject } = useLibrary();
  const [refs, setRefs] = useState([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (projectId) {
      loadRefs();
    }
  }, [projectId]);

  const loadRefs = async () => {
    const result = await getProjectRefs(projectId);
    if (result) {
      setRefs(result.references || []);
    }
  };

  const handleRemove = async (libraryFileId) => {
    if (!confirm('Remove this reference from the project?')) return;

    const result = await removeFromProject(projectId, libraryFileId);
    if (result) {
      loadRefs();
    }
  };

  if (!projectId) return null;
  if (refs.length === 0) {
    return (
      <div className="project-library-refs empty">
        <div className="refs-header">
          <span className="refs-icon">📚</span>
          <span>Library References</span>
        </div>
        <p className="refs-empty-text">
          No library files linked to this project.
          <button onClick={onOpenLibrary} className="link-btn">
            Browse library
          </button>
        </p>
      </div>
    );
  }

  return (
    <div className="project-library-refs">
      <div
        className="refs-header clickable"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="refs-icon">📚</span>
        <span>Library References ({refs.length})</span>
        <span className="expand-icon">{expanded ? '▼' : '▶'}</span>
      </div>

      {expanded && (
        <div className="refs-list">
          {refs.map((ref) => (
            <div key={ref.ref_id} className="ref-item">
              <span className="ref-icon">{getFileIcon(ref.mime_type)}</span>
              <div className="ref-info">
                <div className="ref-name">{ref.filename}</div>
                {ref.notes && (
                  <div className="ref-notes">{ref.notes}</div>
                )}
              </div>
              <button
                className="ref-remove"
                onClick={() => handleRemove(ref.id)}
                title="Remove from project"
              >
                ×
              </button>
            </div>
          ))}

          <button
            className="add-more-btn"
            onClick={onOpenLibrary}
          >
            + Add from library
          </button>
        </div>
      )}
    </div>
  );
}

export default ProjectLibraryRefs;
