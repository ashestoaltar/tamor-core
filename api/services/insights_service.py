"""
Auto-Insights Service

Phase 4.1: Automatically generates insights when project files are processed.

Detects:
- Key themes and patterns
- Contradictions or inconsistencies
- Missing information or gaps
- Unstated assumptions

Insights are cached in the file_insights table and generated on first access.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from utils.db import get_db
from services.llm_service import get_llm_client, get_model_name, llm_is_configured

logger = logging.getLogger(__name__)

# Maximum text length to send to LLM (to avoid token limits)
MAX_TEXT_LENGTH = 12000


INSIGHTS_SYSTEM_PROMPT = """You are an analytical assistant that examines documents to extract insights.

Your task is to analyze the provided content and identify:

1. **Key Themes**: The main topics, patterns, or recurring ideas in the document
2. **Contradictions**: Any internal inconsistencies, conflicting statements, or logical tensions
3. **Missing Information**: Gaps in the content, unanswered questions, or areas that need more detail
4. **Assumptions**: Unstated premises, implicit beliefs, or things taken for granted

Respond in JSON format with this exact structure:
{
    "themes": ["theme 1", "theme 2", ...],
    "contradictions": ["contradiction 1", ...],
    "missing_info": ["missing item 1", ...],
    "assumptions": ["assumption 1", ...],
    "summary": "A 2-3 sentence summary of the document's main purpose and content"
}

Guidelines:
- Be specific and cite relevant details from the document
- If a category has no findings, use an empty array []
- Keep each item concise (1-2 sentences max)
- Focus on actionable, useful insights
- The summary should help someone quickly understand what this document is about"""


def get_cached_insights(file_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve cached insights for a file."""
    conn = get_db()
    cur = conn.execute(
        """
        SELECT insights_json, summary, generated_at, model_used
        FROM file_insights
        WHERE file_id = ?
        """,
        (file_id,),
    )
    row = cur.fetchone()
    if not row:
        return None

    insights_json = row["insights_json"]
    try:
        insights = json.loads(insights_json) if insights_json else {}
    except json.JSONDecodeError:
        insights = {}

    return {
        "file_id": file_id,
        "insights": insights,
        "summary": row["summary"],
        "generated_at": row["generated_at"],
        "model_used": row["model_used"],
    }


def cache_insights(
    file_id: int,
    project_id: int,
    insights: Dict[str, Any],
    summary: str,
    model_used: str,
) -> None:
    """Store insights in the database."""
    conn = get_db()
    conn.execute(
        """
        INSERT OR REPLACE INTO file_insights
            (file_id, project_id, insights_json, summary, model_used)
        VALUES (?, ?, ?, ?, ?)
        """,
        (file_id, project_id, json.dumps(insights), summary, model_used),
    )
    conn.commit()


def invalidate_insights(file_id: int) -> int:
    """Delete cached insights for a file. Returns rows deleted."""
    conn = get_db()
    cur = conn.execute("DELETE FROM file_insights WHERE file_id = ?", (file_id,))
    conn.commit()
    return cur.rowcount


def invalidate_project_insights(project_id: int) -> int:
    """Delete cached insights for all files in a project. Returns rows deleted."""
    conn = get_db()
    cur = conn.execute("DELETE FROM file_insights WHERE project_id = ?", (project_id,))
    conn.commit()
    return cur.rowcount


def _parse_llm_response(response: str) -> Dict[str, Any]:
    """Parse LLM response into structured insights."""
    # Try to extract JSON from response
    response = response.strip()

    # Handle markdown code blocks
    if response.startswith("```"):
        lines = response.split("\n")
        # Remove first and last lines (```json and ```)
        json_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            if line.startswith("```") and in_block:
                break
            if in_block:
                json_lines.append(line)
        response = "\n".join(json_lines)

    try:
        data = json.loads(response)
        # Validate expected structure
        return {
            "themes": data.get("themes", []),
            "contradictions": data.get("contradictions", []),
            "missing_info": data.get("missing_info", []),
            "assumptions": data.get("assumptions", []),
            "summary": data.get("summary", ""),
        }
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON, using fallback")
        # Fallback: treat entire response as summary
        return {
            "themes": [],
            "contradictions": [],
            "missing_info": [],
            "assumptions": [],
            "summary": response[:500] if response else "",
        }


def generate_insights(
    file_id: int,
    project_id: int,
    text: str,
    filename: str,
    mime_type: Optional[str] = None,
    force: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Generate insights for a file using LLM.

    Args:
        file_id: The file ID
        project_id: The project ID
        text: Extracted text content
        filename: Original filename (for context)
        mime_type: File MIME type (for context)
        force: If True, regenerate even if cached

    Returns:
        Dict with insights, or None if generation failed/skipped
    """
    # Check cache first (unless forcing regeneration)
    if not force:
        cached = get_cached_insights(file_id)
        if cached:
            return cached

    # Check if LLM is available
    if not llm_is_configured():
        logger.debug("LLM not configured, skipping insights generation")
        return None

    # Skip empty or very short content
    if not text or len(text.strip()) < 100:
        logger.debug(f"File {file_id} has insufficient content for insights")
        return None

    # Truncate text if too long
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH] + "\n\n[Content truncated for analysis...]"

    # Build user prompt with context
    file_context = f"Filename: {filename}"
    if mime_type:
        file_context += f"\nType: {mime_type}"

    user_prompt = f"{file_context}\n\n---\n\n{text}"

    # Generate insights
    try:
        client = get_llm_client()
        model = get_model_name()

        response = client.chat_completion(
            messages=[
                {"role": "system", "content": INSIGHTS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            temperature=0.3,  # Lower temperature for more consistent analysis
        )

        insights = _parse_llm_response(response)
        summary = insights.pop("summary", "")

        # Cache the results
        cache_insights(file_id, project_id, insights, summary, model)

        return {
            "file_id": file_id,
            "insights": insights,
            "summary": summary,
            "generated_at": None,  # Just generated, not from cache
            "model_used": model,
        }

    except Exception as e:
        logger.error(f"Failed to generate insights for file {file_id}: {e}")
        return None


def get_project_insights(project_id: int, user_id: int) -> List[Dict[str, Any]]:
    """
    Get insights for all files in a project.

    Returns list of insights with file metadata.
    """
    conn = get_db()
    cur = conn.execute(
        """
        SELECT
            fi.file_id,
            fi.insights_json,
            fi.summary,
            fi.generated_at,
            fi.model_used,
            pf.filename,
            pf.mime_type
        FROM file_insights fi
        JOIN project_files pf ON fi.file_id = pf.id
        JOIN projects p ON fi.project_id = p.id
        WHERE fi.project_id = ? AND p.user_id = ?
        ORDER BY fi.generated_at DESC
        """,
        (project_id, user_id),
    )

    results = []
    for row in cur.fetchall():
        try:
            insights = json.loads(row["insights_json"]) if row["insights_json"] else {}
        except json.JSONDecodeError:
            insights = {}

        results.append({
            "file_id": row["file_id"],
            "filename": row["filename"],
            "mime_type": row["mime_type"],
            "insights": insights,
            "summary": row["summary"],
            "generated_at": row["generated_at"],
            "model_used": row["model_used"],
        })

    return results


def aggregate_project_insights(project_id: int, user_id: int) -> Dict[str, Any]:
    """
    Aggregate insights across all files in a project.

    Returns combined themes, contradictions, etc. with file attribution.
    """
    file_insights = get_project_insights(project_id, user_id)

    if not file_insights:
        return {
            "file_count": 0,
            "themes": [],
            "contradictions": [],
            "missing_info": [],
            "assumptions": [],
        }

    # Aggregate with file attribution
    all_themes: List[Dict[str, Any]] = []
    all_contradictions: List[Dict[str, Any]] = []
    all_missing: List[Dict[str, Any]] = []
    all_assumptions: List[Dict[str, Any]] = []

    for fi in file_insights:
        filename = fi["filename"]
        insights = fi.get("insights", {})

        for theme in insights.get("themes", []):
            all_themes.append({"text": theme, "file": filename})

        for contradiction in insights.get("contradictions", []):
            all_contradictions.append({"text": contradiction, "file": filename})

        for missing in insights.get("missing_info", []):
            all_missing.append({"text": missing, "file": filename})

        for assumption in insights.get("assumptions", []):
            all_assumptions.append({"text": assumption, "file": filename})

    return {
        "file_count": len(file_insights),
        "themes": all_themes,
        "contradictions": all_contradictions,
        "missing_info": all_missing,
        "assumptions": all_assumptions,
    }
