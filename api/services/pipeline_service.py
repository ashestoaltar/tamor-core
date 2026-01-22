"""
Project Pipeline Service

Phase 5.2: Structured workflows for different project types.

Provides predefined pipelines:
- Research: Gather, analyze, synthesize, report
- Writing: Outline, draft, revise, finalize
- Study: Read, summarize, test, review
- Long-form: Plan, research, draft, revise, polish

Pipelines guide users through structured processes and can auto-execute
steps using existing services (insights, reasoning, file actions).
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.db import get_db
from services.llm_service import get_llm_client, get_model_name, llm_is_configured

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline Templates
# ---------------------------------------------------------------------------

PIPELINE_TEMPLATES = {
    "research": {
        "name": "Research Pipeline",
        "description": "Systematic research workflow: gather sources, extract insights, synthesize findings",
        "steps": [
            {
                "id": 0,
                "name": "Gather Sources",
                "description": "Upload relevant documents, papers, and reference materials",
                "actions": ["upload_files"],
                "auto_actions": [],
                "completion_hint": "Add at least 2-3 source documents to proceed",
            },
            {
                "id": 1,
                "name": "Extract Insights",
                "description": "Generate insights from each source document",
                "actions": ["generate_insights"],
                "auto_actions": ["generate_insights"],
                "completion_hint": "Review generated insights for each file",
            },
            {
                "id": 2,
                "name": "Analyze Relationships",
                "description": "Find connections and contradictions across sources",
                "actions": ["analyze_reasoning"],
                "auto_actions": ["analyze_reasoning"],
                "completion_hint": "Review cross-document analysis results",
            },
            {
                "id": 3,
                "name": "Synthesize Findings",
                "description": "Create a synthesis document combining key findings",
                "actions": ["generate_spec", "rewrite"],
                "auto_actions": [],
                "completion_hint": "Generate a synthesis spec or summary document",
            },
            {
                "id": 4,
                "name": "Final Report",
                "description": "Review and finalize research findings",
                "actions": ["rewrite"],
                "auto_actions": [],
                "completion_hint": "Pipeline complete - export or continue refining",
            },
        ],
    },
    "writing": {
        "name": "Writing Pipeline",
        "description": "Structured writing workflow: outline, draft, revise, finalize",
        "steps": [
            {
                "id": 0,
                "name": "Outline",
                "description": "Create or upload an outline for your writing project",
                "actions": ["upload_files", "generate_spec"],
                "auto_actions": [],
                "completion_hint": "Add an outline document or generate one from notes",
            },
            {
                "id": 1,
                "name": "First Draft",
                "description": "Write or expand the outline into a full draft",
                "actions": ["rewrite", "upload_files"],
                "auto_actions": [],
                "completion_hint": "Upload your draft or use 'expand' rewrite mode",
            },
            {
                "id": 2,
                "name": "Review & Analyze",
                "description": "Analyze draft for gaps, inconsistencies, and improvements",
                "actions": ["generate_insights", "extract_parameters"],
                "auto_actions": ["generate_insights"],
                "completion_hint": "Review insights and address identified issues",
            },
            {
                "id": 3,
                "name": "Revise",
                "description": "Improve the draft based on analysis",
                "actions": ["rewrite"],
                "auto_actions": [],
                "completion_hint": "Use 'improve' or 'restructure' rewrite modes",
            },
            {
                "id": 4,
                "name": "Finalize",
                "description": "Final polish and formatting",
                "actions": ["rewrite"],
                "auto_actions": [],
                "completion_hint": "Pipeline complete - ready for export",
            },
        ],
    },
    "study": {
        "name": "Study Pipeline",
        "description": "Active learning workflow: read, summarize, test understanding, review",
        "steps": [
            {
                "id": 0,
                "name": "Gather Materials",
                "description": "Upload study materials (textbooks, notes, papers)",
                "actions": ["upload_files"],
                "auto_actions": [],
                "completion_hint": "Add study materials to proceed",
            },
            {
                "id": 1,
                "name": "Summarize Content",
                "description": "Generate summaries and extract key concepts",
                "actions": ["generate_insights", "extract_parameters"],
                "auto_actions": ["generate_insights"],
                "completion_hint": "Review summaries and key themes",
            },
            {
                "id": 2,
                "name": "Identify Connections",
                "description": "Find relationships between concepts across materials",
                "actions": ["analyze_reasoning"],
                "auto_actions": ["analyze_reasoning"],
                "completion_hint": "Review concept relationships and dependencies",
            },
            {
                "id": 3,
                "name": "Create Study Guide",
                "description": "Generate a consolidated study guide",
                "actions": ["generate_spec", "rewrite"],
                "auto_actions": [],
                "completion_hint": "Generate a study guide spec from your materials",
            },
            {
                "id": 4,
                "name": "Review & Reinforce",
                "description": "Review materials and identify areas needing more study",
                "actions": ["generate_insights"],
                "auto_actions": [],
                "completion_hint": "Pipeline complete - continue reviewing as needed",
            },
        ],
    },
    "long_form": {
        "name": "Long-Form Project Pipeline",
        "description": "Extended project workflow for books, theses, or major documents",
        "steps": [
            {
                "id": 0,
                "name": "Project Planning",
                "description": "Define scope, goals, and structure",
                "actions": ["upload_files", "generate_spec"],
                "auto_actions": [],
                "completion_hint": "Create a project plan or spec document",
            },
            {
                "id": 1,
                "name": "Research Phase",
                "description": "Gather and analyze source materials",
                "actions": ["upload_files", "generate_insights", "analyze_reasoning"],
                "auto_actions": ["generate_insights"],
                "completion_hint": "Complete research gathering and analysis",
            },
            {
                "id": 2,
                "name": "Outline & Structure",
                "description": "Create detailed outline based on research",
                "actions": ["generate_spec", "rewrite"],
                "auto_actions": [],
                "completion_hint": "Finalize document structure and outline",
            },
            {
                "id": 3,
                "name": "Draft Sections",
                "description": "Write individual sections/chapters",
                "actions": ["upload_files", "rewrite"],
                "auto_actions": [],
                "completion_hint": "Complete drafts of all major sections",
            },
            {
                "id": 4,
                "name": "Integration",
                "description": "Combine sections and ensure coherence",
                "actions": ["analyze_reasoning", "rewrite"],
                "auto_actions": ["analyze_reasoning"],
                "completion_hint": "Review cross-section consistency",
            },
            {
                "id": 5,
                "name": "Revision",
                "description": "Major revisions based on integrated review",
                "actions": ["rewrite", "generate_insights"],
                "auto_actions": [],
                "completion_hint": "Complete substantive revisions",
            },
            {
                "id": 6,
                "name": "Polish & Finalize",
                "description": "Final editing and formatting",
                "actions": ["rewrite"],
                "auto_actions": [],
                "completion_hint": "Pipeline complete - ready for final review",
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Pipeline State Management
# ---------------------------------------------------------------------------

def get_pipeline(project_id: int) -> Optional[Dict[str, Any]]:
    """Get active pipeline for a project."""
    conn = get_db()
    cur = conn.execute(
        """
        SELECT id, pipeline_type, current_step, status, step_data_json,
               started_at, updated_at, completed_at
        FROM project_pipelines
        WHERE project_id = ? AND status != 'abandoned'
        ORDER BY started_at DESC
        LIMIT 1
        """,
        (project_id,),
    )
    row = cur.fetchone()
    if not row:
        return None

    step_data = {}
    if row["step_data_json"]:
        try:
            step_data = json.loads(row["step_data_json"])
        except json.JSONDecodeError:
            pass

    pipeline_type = row["pipeline_type"]
    template = PIPELINE_TEMPLATES.get(pipeline_type)
    if not template:
        return None

    current_step = row["current_step"]
    steps = template["steps"]
    current_step_info = steps[current_step] if current_step < len(steps) else None

    return {
        "id": row["id"],
        "project_id": project_id,
        "pipeline_type": pipeline_type,
        "pipeline_name": template["name"],
        "description": template["description"],
        "current_step": current_step,
        "total_steps": len(steps),
        "status": row["status"],
        "current_step_info": current_step_info,
        "all_steps": steps,
        "step_data": step_data,
        "started_at": row["started_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
        "progress_percent": int((current_step / len(steps)) * 100) if steps else 0,
    }


def start_pipeline(project_id: int, pipeline_type: str) -> Dict[str, Any]:
    """Start a new pipeline for a project."""
    if pipeline_type not in PIPELINE_TEMPLATES:
        return {"error": "invalid_pipeline_type", "available": list(PIPELINE_TEMPLATES.keys())}

    # Check for existing active pipeline
    existing = get_pipeline(project_id)
    if existing and existing["status"] == "active":
        return {"error": "pipeline_already_active", "existing": existing}

    template = PIPELINE_TEMPLATES[pipeline_type]

    conn = get_db()
    cur = conn.execute(
        """
        INSERT INTO project_pipelines (project_id, pipeline_type, current_step, status, step_data_json)
        VALUES (?, ?, 0, 'active', '{}')
        """,
        (project_id, pipeline_type),
    )
    conn.commit()
    pipeline_id = cur.lastrowid

    return {
        "id": pipeline_id,
        "project_id": project_id,
        "pipeline_type": pipeline_type,
        "pipeline_name": template["name"],
        "current_step": 0,
        "total_steps": len(template["steps"]),
        "status": "active",
        "current_step_info": template["steps"][0],
        "message": f"Started {template['name']}",
    }


def advance_pipeline(project_id: int, step_notes: Optional[str] = None) -> Dict[str, Any]:
    """Advance pipeline to next step."""
    pipeline = get_pipeline(project_id)
    if not pipeline:
        return {"error": "no_active_pipeline"}

    if pipeline["status"] != "active":
        return {"error": "pipeline_not_active", "status": pipeline["status"]}

    current_step = pipeline["current_step"]
    total_steps = pipeline["total_steps"]
    step_data = pipeline.get("step_data", {})

    # Save notes for current step
    if step_notes:
        step_data[f"step_{current_step}_notes"] = step_notes
        step_data[f"step_{current_step}_completed_at"] = datetime.now().isoformat()

    new_step = current_step + 1
    new_status = "active"
    completed_at = None

    if new_step >= total_steps:
        new_status = "completed"
        completed_at = datetime.now().isoformat()

    conn = get_db()
    conn.execute(
        """
        UPDATE project_pipelines
        SET current_step = ?, status = ?, step_data_json = ?,
            updated_at = CURRENT_TIMESTAMP, completed_at = ?
        WHERE project_id = ? AND status = 'active'
        """,
        (new_step, new_status, json.dumps(step_data), completed_at, project_id),
    )
    conn.commit()

    # Get updated pipeline
    updated = get_pipeline(project_id)
    if new_status == "completed":
        updated["message"] = "Pipeline completed!"
    else:
        updated["message"] = f"Advanced to step {new_step + 1}: {updated['current_step_info']['name']}"

    return updated


def abandon_pipeline(project_id: int) -> Dict[str, Any]:
    """Abandon/cancel current pipeline."""
    pipeline = get_pipeline(project_id)
    if not pipeline:
        return {"error": "no_active_pipeline"}

    conn = get_db()
    conn.execute(
        """
        UPDATE project_pipelines
        SET status = 'abandoned', updated_at = CURRENT_TIMESTAMP
        WHERE project_id = ? AND status = 'active'
        """,
        (project_id,),
    )
    conn.commit()

    return {"message": "Pipeline abandoned", "project_id": project_id}


def reset_pipeline(project_id: int) -> Dict[str, Any]:
    """Reset pipeline to first step."""
    pipeline = get_pipeline(project_id)
    if not pipeline:
        return {"error": "no_pipeline"}

    conn = get_db()
    conn.execute(
        """
        UPDATE project_pipelines
        SET current_step = 0, status = 'active', step_data_json = '{}',
            updated_at = CURRENT_TIMESTAMP, completed_at = NULL
        WHERE project_id = ? AND id = ?
        """,
        (project_id, pipeline["id"]),
    )
    conn.commit()

    return get_pipeline(project_id)


# ---------------------------------------------------------------------------
# Pipeline Guidance
# ---------------------------------------------------------------------------

def get_step_guidance(project_id: int, user_id: int) -> Dict[str, Any]:
    """Get detailed guidance for current pipeline step."""
    pipeline = get_pipeline(project_id)
    if not pipeline:
        return {"error": "no_active_pipeline"}

    if pipeline["status"] != "active":
        return {"error": "pipeline_not_active", "status": pipeline["status"]}

    step_info = pipeline["current_step_info"]
    if not step_info:
        return {"error": "invalid_step"}

    # Build guidance based on available actions
    guidance = {
        "step_name": step_info["name"],
        "step_number": pipeline["current_step"] + 1,
        "total_steps": pipeline["total_steps"],
        "description": step_info["description"],
        "completion_hint": step_info["completion_hint"],
        "available_actions": [],
        "auto_actions": step_info.get("auto_actions", []),
    }

    # Map actions to API endpoints
    action_map = {
        "upload_files": {
            "action": "upload_files",
            "description": "Upload documents to the project",
            "endpoint": "POST /api/projects/{project_id}/files",
        },
        "generate_insights": {
            "action": "generate_insights",
            "description": "Generate insights for project files",
            "endpoint": "GET /api/projects/{project_id}/insights",
        },
        "analyze_reasoning": {
            "action": "analyze_reasoning",
            "description": "Analyze cross-document relationships and contradictions",
            "endpoint": "GET /api/projects/{project_id}/reasoning",
        },
        "generate_spec": {
            "action": "generate_spec",
            "description": "Generate specification from file content",
            "endpoint": "POST /api/files/{file_id}/generate-spec",
        },
        "rewrite": {
            "action": "rewrite",
            "description": "Rewrite/transform file content",
            "endpoint": "POST /api/files/{file_id}/rewrite",
        },
        "extract_parameters": {
            "action": "extract_parameters",
            "description": "Extract parameters from file",
            "endpoint": "POST /api/files/{file_id}/extract-parameters",
        },
    }

    for action in step_info.get("actions", []):
        if action in action_map:
            guidance["available_actions"].append(action_map[action])

    return guidance


def get_pipeline_summary(project_id: int, user_id: int) -> Dict[str, Any]:
    """Get LLM-generated summary of pipeline progress."""
    pipeline = get_pipeline(project_id)
    if not pipeline:
        return {"error": "no_pipeline"}

    if not llm_is_configured():
        return {
            "pipeline": pipeline,
            "summary": "LLM not configured - unable to generate summary",
        }

    # Build context about pipeline progress
    step_data = pipeline.get("step_data", {})
    completed_steps = []
    for i in range(pipeline["current_step"]):
        step = pipeline["all_steps"][i]
        notes = step_data.get(f"step_{i}_notes", "No notes")
        completed_steps.append(f"- Step {i+1} ({step['name']}): {notes}")

    context = f"""Pipeline: {pipeline['pipeline_name']}
Status: {pipeline['status']}
Progress: Step {pipeline['current_step'] + 1} of {pipeline['total_steps']}

Completed steps:
{chr(10).join(completed_steps) if completed_steps else 'No steps completed yet'}

Current step: {pipeline['current_step_info']['name'] if pipeline['current_step_info'] else 'N/A'}
"""

    try:
        client = get_llm_client()
        model = get_model_name()

        response = client.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are a project assistant. Provide a brief, encouraging summary of the user's progress through their workflow pipeline. Mention what's been accomplished and what's next.",
                },
                {"role": "user", "content": context},
            ],
            model=model,
            temperature=0.5,
        )

        return {
            "pipeline": pipeline,
            "summary": response,
            "model_used": model,
        }

    except Exception as e:
        logger.error(f"Failed to generate pipeline summary: {e}")
        return {
            "pipeline": pipeline,
            "summary": f"Error generating summary: {e}",
        }


# ---------------------------------------------------------------------------
# Template Listing
# ---------------------------------------------------------------------------

def list_pipeline_templates() -> List[Dict[str, Any]]:
    """List all available pipeline templates."""
    templates = []
    for key, template in PIPELINE_TEMPLATES.items():
        templates.append({
            "type": key,
            "name": template["name"],
            "description": template["description"],
            "step_count": len(template["steps"]),
            "steps_preview": [s["name"] for s in template["steps"]],
        })
    return templates
