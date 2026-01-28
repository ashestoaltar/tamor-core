// src/components/RightPanel/components/PipelinePanel.jsx
import React, { useState, useEffect } from "react";
import { apiFetch } from "../../../api/client";

function PipelinePanel({ currentProjectId }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [pipeline, setPipeline] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [showTemplates, setShowTemplates] = useState(false);
  const [stepNotes, setStepNotes] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    if (currentProjectId) {
      loadPipeline();
      loadTemplates();
    }
  }, [currentProjectId]);

  const loadPipeline = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch(`/projects/${currentProjectId}/pipeline`);
      setPipeline(data.pipeline || data);
    } catch (err) {
      // No pipeline is not an error
      if (err.message?.includes("no_pipeline")) {
        setPipeline(null);
      } else {
        console.error("Failed to load pipeline", err);
      }
    } finally {
      setLoading(false);
    }
  };

  const loadTemplates = async () => {
    try {
      const data = await apiFetch("/pipelines");
      setTemplates(data.templates || data.pipelines || []);
    } catch (err) {
      console.error("Failed to load templates", err);
    }
  };

  const handleStartPipeline = async (pipelineType) => {
    setActionLoading(true);
    setError("");
    try {
      const data = await apiFetch(`/projects/${currentProjectId}/pipeline/start`, {
        method: "POST",
        body: { pipeline_type: pipelineType },
      });
      setPipeline(data);
      setShowTemplates(false);
    } catch (err) {
      console.error("Failed to start pipeline", err);
      setError(err.message || "Failed to start pipeline");
    } finally {
      setActionLoading(false);
    }
  };

  const handleAdvance = async () => {
    setActionLoading(true);
    setError("");
    try {
      const data = await apiFetch(`/projects/${currentProjectId}/pipeline/advance`, {
        method: "POST",
        body: { notes: stepNotes || null },
      });
      setPipeline(data);
      setStepNotes("");
    } catch (err) {
      console.error("Failed to advance pipeline", err);
      setError(err.message || "Failed to advance pipeline");
    } finally {
      setActionLoading(false);
    }
  };

  const handleAbandon = async () => {
    if (!confirm("Abandon this pipeline? You can start a new one afterward.")) return;
    setActionLoading(true);
    try {
      await apiFetch(`/projects/${currentProjectId}/pipeline/abandon`, {
        method: "POST",
      });
      setPipeline(null);
    } catch (err) {
      console.error("Failed to abandon pipeline", err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReset = async () => {
    if (!confirm("Reset pipeline to step 1?")) return;
    setActionLoading(true);
    try {
      const data = await apiFetch(`/projects/${currentProjectId}/pipeline/reset`, {
        method: "POST",
      });
      setPipeline(data);
    } catch (err) {
      console.error("Failed to reset pipeline", err);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">Project Pipeline</h3>
        </div>
        <div className="rp-section-body">
          <div className="rp-info-text">Loading...</div>
        </div>
      </div>
    );
  }

  // No active pipeline - show template selector
  if (!pipeline || pipeline.error || pipeline.current_step == null) {
    return (
      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">Project Pipeline</h3>
          <button
            className="rp-button subtle"
            onClick={() => setShowTemplates(!showTemplates)}
          >
            {showTemplates ? "Cancel" : "Start Pipeline"}
          </button>
        </div>
        <div className="rp-section-body">
          {!showTemplates ? (
            <div className="rp-info-text">
              No active pipeline. Start a structured workflow to guide your
              project through defined stages.
            </div>
          ) : (
            <div className="rp-pipeline-templates">
              {templates.map((t) => (
                <div
                  key={t.type}
                  className="rp-pipeline-template"
                  onClick={() => handleStartPipeline(t.type)}
                >
                  <div className="rp-pipeline-template-name">{t.name}</div>
                  <div className="rp-pipeline-template-desc">{t.description}</div>
                  <div className="rp-pipeline-template-steps">
                    {t.steps_preview?.join(" → ")}
                  </div>
                </div>
              ))}
            </div>
          )}
          {error && <div className="rp-error-text">{error}</div>}
        </div>
      </div>
    );
  }

  // Active pipeline view
  const currentStep = pipeline.current_step_info;
  const progress = pipeline.progress_percent || 0;

  return (
    <div className="rp-section">
      <div className="rp-section-header">
        <h3 className="rp-section-title">{pipeline.pipeline_name}</h3>
        <span
          className={`rp-tag ${
            pipeline.status === "completed" ? "rp-tag-positive" : "rp-tag-muted"
          }`}
        >
          {pipeline.status}
        </span>
      </div>
      <div className="rp-section-body">
        {/* Progress bar */}
        <div className="rp-pipeline-progress">
          <div
            className="rp-pipeline-progress-bar"
            style={{ width: `${progress}%` }}
          />
          <span className="rp-pipeline-progress-text">
            Step {pipeline.current_step + 1} of {pipeline.total_steps}
          </span>
        </div>

        {/* Step list */}
        <div className="rp-pipeline-steps">
          {pipeline.all_steps?.map((step, idx) => (
            <div
              key={step.id}
              className={`rp-pipeline-step ${
                idx < pipeline.current_step
                  ? "completed"
                  : idx === pipeline.current_step
                  ? "active"
                  : "pending"
              }`}
            >
              <div className="rp-pipeline-step-marker">
                {idx < pipeline.current_step ? "✓" : idx + 1}
              </div>
              <div className="rp-pipeline-step-info">
                <div className="rp-pipeline-step-name">{step.name}</div>
                {idx === pipeline.current_step && (
                  <div className="rp-pipeline-step-desc">{step.description}</div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Current step details */}
        {currentStep && pipeline.status === "active" && (
          <div className="rp-pipeline-current">
            <div className="rp-pipeline-hint">{currentStep.completion_hint}</div>
            <div className="rp-pipeline-actions-label">Available actions:</div>
            <div className="rp-pipeline-action-tags">
              {currentStep.actions?.map((action) => (
                <span key={action} className="rp-tag rp-tag-muted">
                  {action.replace(/_/g, " ")}
                </span>
              ))}
            </div>
            <textarea
              className="rp-notes-textarea rp-small"
              placeholder="Notes for this step (optional)..."
              value={stepNotes}
              onChange={(e) => setStepNotes(e.target.value)}
            />
            <div className="rp-pipeline-buttons">
              <button
                className="rp-button primary"
                onClick={handleAdvance}
                disabled={actionLoading}
              >
                {actionLoading ? "..." : "Complete Step & Advance"}
              </button>
              <button
                className="rp-button subtle"
                onClick={handleReset}
                disabled={actionLoading}
              >
                Reset
              </button>
              <button
                className="rp-button subtle"
                onClick={handleAbandon}
                disabled={actionLoading}
              >
                Abandon
              </button>
            </div>
          </div>
        )}

        {/* Completed state */}
        {pipeline.status === "completed" && (
          <div className="rp-pipeline-completed">
            <div className="rp-success-text">Pipeline completed!</div>
            <button
              className="rp-button subtle"
              onClick={handleAbandon}
              disabled={actionLoading}
            >
              Clear & Start New
            </button>
          </div>
        )}

        {error && <div className="rp-error-text">{error}</div>}
      </div>
    </div>
  );
}

export default PipelinePanel;
