// src/components/RightPanel/components/StructurePanel.jsx
import React from "react";

function StructurePanel({
  structureFileId,
  structureLoading,
  structureError,
  structureData,
}) {
  if (!structureFileId) return null;

  return (
    <div className="rp-section">
      <div className="rp-section-header">
        <h3 className="rp-section-title">File structure (beta)</h3>
      </div>

      {structureLoading && (
        <div className="rp-section-body rp-small-text">
          Loading structure…
        </div>
      )}

      {structureError && (
        <div className="rp-section-body rp-error">
          {structureError}
        </div>
      )}

      {!structureLoading && !structureError && !structureData && (
        <div className="rp-section-body rp-small-text">
          No structure info available for this file yet.
        </div>
      )}

      {!structureLoading && structureData && (
        <div className="rp-section-body">
          <pre className="rp-structure-pre">
            {JSON.stringify(structureData, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default StructurePanel;
