"""
Multi-File Reasoning Service

Phase 4.2: Cross-document analysis for project files.

Provides:
- File relationship analysis (dependencies, references)
- Cross-file contradiction detection
- Logic flow and coherence checking

Results are cached in the project_reasoning table.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from utils.db import get_db
from services.llm_service import get_llm_client, get_model_name, llm_is_configured
from services.insights_service import get_project_insights, aggregate_project_insights

logger = logging.getLogger(__name__)

# Maximum context for LLM calls
MAX_CONTEXT_CHARS = 10000


# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

RELATIONSHIPS_PROMPT = """You are an analytical assistant that identifies relationships between documents in a project.

Analyze the provided file summaries and insights to identify:
1. **Dependencies**: Which files depend on or reference information from other files
2. **Hierarchies**: Which files define concepts that others build upon
3. **Cross-references**: Explicit or implicit references between documents

Respond in JSON format:
{
    "relationships": [
        {
            "source_file": "filename that references or depends",
            "target_file": "filename being referenced",
            "relationship_type": "depends_on|references|implements|extends|contradicts",
            "description": "Brief explanation of the relationship",
            "confidence": 0.0-1.0
        }
    ],
    "summary": "Brief overview of the document structure and key relationships"
}

Be specific. Only report relationships you can clearly identify from the content."""


CONTRADICTIONS_PROMPT = """You are a critical analyst that identifies contradictions and inconsistencies BETWEEN documents.

Analyze the provided file contents and insights to find:
1. **Direct contradictions**: Statements in one file that conflict with another
2. **Inconsistent assumptions**: Different files assuming different things
3. **Conflicting requirements**: Specifications that cannot all be true

Respond in JSON format:
{
    "contradictions": [
        {
            "file_1": "first filename",
            "file_2": "second filename",
            "issue": "Clear description of the contradiction",
            "file_1_position": "What file 1 says or implies",
            "file_2_position": "What file 2 says or implies",
            "severity": "high|medium|low",
            "confidence": 0.0-1.0
        }
    ],
    "summary": "Overall assessment of consistency across documents"
}

Only report genuine contradictions, not mere differences in focus or detail level."""


LOGIC_FLOW_PROMPT = """You are a logic analyst that checks coherence across a set of documents.

Analyze the provided insights to evaluate:
1. **Assumption coverage**: Are assumptions in one file supported by evidence in others?
2. **Logical gaps**: Are there conclusions without supporting evidence?
3. **Circular dependencies**: Do any files form circular logical chains?
4. **Missing links**: What information is assumed but never defined?

Respond in JSON format:
{
    "coverage_analysis": [
        {
            "file": "filename with assumption",
            "assumption": "The assumption being made",
            "status": "supported|unsupported|partially_supported",
            "supporting_files": ["files that provide evidence"],
            "gaps": ["what's missing"]
        }
    ],
    "logical_issues": [
        {
            "issue_type": "circular_dependency|missing_evidence|undefined_term",
            "description": "What the issue is",
            "affected_files": ["list of files"],
            "severity": "high|medium|low"
        }
    ],
    "coherence_score": 0.0-1.0,
    "summary": "Overall assessment of logical coherence"
}

Focus on substantive logical issues, not stylistic differences."""


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------

def get_cached_reasoning(project_id: int, reasoning_type: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached reasoning results."""
    conn = get_db()
    cur = conn.execute(
        """
        SELECT result_json, generated_at, model_used
        FROM project_reasoning
        WHERE project_id = ? AND reasoning_type = ?
        ORDER BY generated_at DESC
        LIMIT 1
        """,
        (project_id, reasoning_type),
    )
    row = cur.fetchone()
    if not row:
        return None

    try:
        result = json.loads(row["result_json"])
    except json.JSONDecodeError:
        return None

    return {
        "reasoning_type": reasoning_type,
        "result": result,
        "generated_at": row["generated_at"],
        "model_used": row["model_used"],
    }


def cache_reasoning(
    project_id: int,
    reasoning_type: str,
    result: Dict[str, Any],
    model_used: str,
) -> None:
    """Store reasoning results in the database."""
    conn = get_db()
    # Remove old results of this type for this project
    conn.execute(
        "DELETE FROM project_reasoning WHERE project_id = ? AND reasoning_type = ?",
        (project_id, reasoning_type),
    )
    conn.execute(
        """
        INSERT INTO project_reasoning (project_id, reasoning_type, result_json, model_used)
        VALUES (?, ?, ?, ?)
        """,
        (project_id, reasoning_type, json.dumps(result), model_used),
    )
    conn.commit()


def invalidate_reasoning(project_id: int) -> int:
    """Delete all cached reasoning for a project. Returns rows deleted."""
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM project_reasoning WHERE project_id = ?",
        (project_id,),
    )
    conn.commit()
    return cur.rowcount


# ---------------------------------------------------------------------------
# LLM Response Parsing
# ---------------------------------------------------------------------------

def _parse_llm_json(response: str) -> Dict[str, Any]:
    """Parse LLM response, handling markdown code blocks."""
    response = response.strip()

    # Handle markdown code blocks
    if response.startswith("```"):
        lines = response.split("\n")
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
        return json.loads(response)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON")
        return {"error": "parse_failed", "raw_response": response[:500]}


def _build_file_context(file_insights: List[Dict[str, Any]], max_chars: int) -> str:
    """Build context string from file insights."""
    parts = []
    used = 0

    for fi in file_insights:
        filename = fi.get("filename", "unknown")
        summary = fi.get("summary", "")
        insights = fi.get("insights", {})

        themes = insights.get("themes", [])
        assumptions = insights.get("assumptions", [])

        section = f"## {filename}\n"
        if summary:
            section += f"Summary: {summary}\n"
        if themes:
            section += f"Themes: {', '.join(themes[:5])}\n"
        if assumptions:
            section += f"Assumptions: {', '.join(assumptions[:3])}\n"

        if used + len(section) > max_chars:
            break

        parts.append(section)
        used += len(section)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Reasoning Functions
# ---------------------------------------------------------------------------

def analyze_file_relationships(
    project_id: int,
    user_id: int,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Analyze relationships and dependencies between project files.

    Returns dict with relationships, summary, and metadata.
    """
    reasoning_type = "relationships"

    # Check cache
    if not force:
        cached = get_cached_reasoning(project_id, reasoning_type)
        if cached:
            return cached

    # Check LLM availability
    if not llm_is_configured():
        return {"error": "llm_not_configured", "result": None}

    # Get file insights
    file_insights = get_project_insights(project_id, user_id)
    if not file_insights:
        return {
            "reasoning_type": reasoning_type,
            "result": {"relationships": [], "summary": "No files with insights found"},
            "generated_at": None,
            "model_used": None,
        }

    # Build context
    context = _build_file_context(file_insights, MAX_CONTEXT_CHARS)

    # Query LLM
    try:
        client = get_llm_client()
        model = get_model_name()

        response = client.chat_completion(
            messages=[
                {"role": "system", "content": RELATIONSHIPS_PROMPT},
                {"role": "user", "content": f"Analyze relationships between these files:\n\n{context}"},
            ],
            model=model,
            temperature=0.3,
        )

        result = _parse_llm_json(response)

        # Cache results
        cache_reasoning(project_id, reasoning_type, result, model)

        return {
            "reasoning_type": reasoning_type,
            "result": result,
            "generated_at": None,
            "model_used": model,
        }

    except Exception as e:
        logger.error(f"Failed to analyze relationships for project {project_id}: {e}")
        return {"error": str(e), "result": None}


def detect_cross_file_contradictions(
    project_id: int,
    user_id: int,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Detect contradictions and inconsistencies between project files.

    Returns dict with contradictions, summary, and metadata.
    """
    reasoning_type = "contradictions"

    # Check cache
    if not force:
        cached = get_cached_reasoning(project_id, reasoning_type)
        if cached:
            return cached

    # Check LLM availability
    if not llm_is_configured():
        return {"error": "llm_not_configured", "result": None}

    # Get aggregated insights (includes all themes, contradictions, assumptions)
    aggregated = aggregate_project_insights(project_id, user_id)
    file_insights = get_project_insights(project_id, user_id)

    if aggregated.get("file_count", 0) < 2:
        return {
            "reasoning_type": reasoning_type,
            "result": {"contradictions": [], "summary": "Need at least 2 files for cross-file analysis"},
            "generated_at": None,
            "model_used": None,
        }

    # Build rich context with themes and assumptions per file
    context = _build_file_context(file_insights, MAX_CONTEXT_CHARS)

    # Also include within-file contradictions as hints
    within_file = aggregated.get("contradictions", [])
    if within_file:
        context += "\n\n## Known within-file issues:\n"
        for c in within_file[:5]:
            context += f"- [{c.get('file', '?')}] {c.get('text', '')}\n"

    # Query LLM
    try:
        client = get_llm_client()
        model = get_model_name()

        response = client.chat_completion(
            messages=[
                {"role": "system", "content": CONTRADICTIONS_PROMPT},
                {"role": "user", "content": f"Find contradictions BETWEEN these files:\n\n{context}"},
            ],
            model=model,
            temperature=0.3,
        )

        result = _parse_llm_json(response)

        # Cache results
        cache_reasoning(project_id, reasoning_type, result, model)

        return {
            "reasoning_type": reasoning_type,
            "result": result,
            "generated_at": None,
            "model_used": model,
        }

    except Exception as e:
        logger.error(f"Failed to detect contradictions for project {project_id}: {e}")
        return {"error": str(e), "result": None}


def analyze_logic_flow(
    project_id: int,
    user_id: int,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Analyze logical coherence and assumption coverage across files.

    Returns dict with coverage analysis, issues, coherence score, and metadata.
    """
    reasoning_type = "logic_flow"

    # Check cache
    if not force:
        cached = get_cached_reasoning(project_id, reasoning_type)
        if cached:
            return cached

    # Check LLM availability
    if not llm_is_configured():
        return {"error": "llm_not_configured", "result": None}

    # Get insights
    aggregated = aggregate_project_insights(project_id, user_id)
    file_insights = get_project_insights(project_id, user_id)

    if not file_insights:
        return {
            "reasoning_type": reasoning_type,
            "result": {"coverage_analysis": [], "logical_issues": [], "coherence_score": 0, "summary": "No insights available"},
            "generated_at": None,
            "model_used": None,
        }

    # Build context focused on assumptions
    context = "# File Assumptions and Themes\n\n"
    for fi in file_insights:
        filename = fi.get("filename", "unknown")
        insights = fi.get("insights", {})
        assumptions = insights.get("assumptions", [])
        themes = insights.get("themes", [])

        context += f"## {filename}\n"
        if assumptions:
            context += f"Assumptions: {'; '.join(assumptions)}\n"
        if themes:
            context += f"Themes: {', '.join(themes)}\n"
        context += "\n"

        if len(context) > MAX_CONTEXT_CHARS:
            break

    # Query LLM
    try:
        client = get_llm_client()
        model = get_model_name()

        response = client.chat_completion(
            messages=[
                {"role": "system", "content": LOGIC_FLOW_PROMPT},
                {"role": "user", "content": f"Analyze the logical coherence of this document set:\n\n{context}"},
            ],
            model=model,
            temperature=0.3,
        )

        result = _parse_llm_json(response)

        # Cache results
        cache_reasoning(project_id, reasoning_type, result, model)

        return {
            "reasoning_type": reasoning_type,
            "result": result,
            "generated_at": None,
            "model_used": model,
        }

    except Exception as e:
        logger.error(f"Failed to analyze logic flow for project {project_id}: {e}")
        return {"error": str(e), "result": None}


def get_full_reasoning(
    project_id: int,
    user_id: int,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Get all reasoning analyses for a project.

    Runs all three analyses (relationships, contradictions, logic_flow)
    and combines results.
    """
    relationships = analyze_file_relationships(project_id, user_id, force)
    contradictions = detect_cross_file_contradictions(project_id, user_id, force)
    logic_flow = analyze_logic_flow(project_id, user_id, force)

    return {
        "project_id": project_id,
        "relationships": relationships.get("result"),
        "contradictions": contradictions.get("result"),
        "logic_flow": logic_flow.get("result"),
        "model_used": relationships.get("model_used") or contradictions.get("model_used") or logic_flow.get("model_used"),
    }
