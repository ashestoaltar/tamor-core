"""
File Actions Service

Phase 5.1: AI-powered file transformations.

Provides:
- Rewrite: Transform file content (simplify, expand, improve, restructure)
- Generate Specs: Create specification documents from existing files
- Extract Parameters: Identify and extract key parameters/config values

All actions use LLM and return transformed content without modifying originals.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from services.llm_service import get_llm_client, get_model_name, llm_is_configured

logger = logging.getLogger(__name__)

# Maximum input text for LLM
MAX_INPUT_CHARS = 15000


# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

REWRITE_PROMPTS = {
    "simplify": """You are a technical writer. Simplify the following content to make it clearer and more accessible.
- Use plain language
- Break down complex concepts
- Maintain accuracy while improving readability
- Keep the same general structure

Return only the rewritten content, no explanations.""",

    "expand": """You are a technical writer. Expand the following content with more detail and explanation.
- Add context and background where helpful
- Elaborate on key points
- Include examples where appropriate
- Maintain the original structure and intent

Return only the expanded content, no explanations.""",

    "improve": """You are an expert editor. Improve the following content for clarity, coherence, and professionalism.
- Fix any grammatical or structural issues
- Improve flow and readability
- Strengthen weak arguments or explanations
- Maintain the author's voice and intent

Return only the improved content, no explanations.""",

    "restructure": """You are a document architect. Restructure the following content for better organization.
- Create clear sections and headings
- Group related information together
- Improve logical flow
- Add transitions between sections

Return only the restructured content, no explanations.""",

    "technical": """You are a technical documentation expert. Rewrite the following for a technical audience.
- Use precise technical terminology
- Add technical details where appropriate
- Structure for reference use
- Include any relevant specifications

Return only the rewritten content, no explanations.""",

    "executive": """You are a business writer. Rewrite the following as an executive summary.
- Focus on key points and decisions
- Lead with conclusions
- Be concise and action-oriented
- Highlight business impact

Return only the rewritten content, no explanations.""",
}


SPEC_GENERATION_PROMPT = """You are a specifications writer. Generate a formal specification document based on the provided content.

Create a structured specification that includes (as applicable):
1. **Overview**: Brief description of what this specifies
2. **Requirements**: Functional and non-functional requirements
3. **Constraints**: Limitations and boundaries
4. **Dependencies**: External dependencies or prerequisites
5. **Acceptance Criteria**: How to verify requirements are met
6. **Open Questions**: Unresolved issues or decisions needed

Format the specification clearly with headers and bullet points.
If certain sections aren't applicable based on the content, omit them.

Return only the specification document."""


PARAMETER_EXTRACTION_PROMPT = """You are a configuration analyst. Extract all parameters, settings, and configurable values from the provided content.

For each parameter found, identify:
- **name**: The parameter name or key
- **value**: The current/default value (if specified)
- **type**: Data type (string, number, boolean, list, etc.)
- **description**: What this parameter controls
- **source**: Where in the document this was found

Return as JSON:
{
    "parameters": [
        {
            "name": "parameter_name",
            "value": "current_value or null",
            "type": "string|number|boolean|list|object",
            "description": "What this parameter does",
            "required": true/false,
            "source": "section or context where found"
        }
    ],
    "summary": "Brief overview of the configuration structure"
}

Only extract actual parameters/settings, not general content."""


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------

def rewrite_file(
    text: str,
    filename: str,
    mode: str = "improve",
    custom_instructions: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Rewrite file content using LLM.

    Args:
        text: Original file content
        filename: For context
        mode: One of 'simplify', 'expand', 'improve', 'restructure', 'technical', 'executive'
        custom_instructions: Optional custom rewrite instructions (overrides mode)

    Returns:
        Dict with 'result' (rewritten content) or 'error'
    """
    if not llm_is_configured():
        return {"error": "llm_not_configured", "result": None}

    if not text or len(text.strip()) < 50:
        return {"error": "insufficient_content", "result": None}

    # Truncate if too long
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS] + "\n\n[Content truncated...]"

    # Get system prompt
    if custom_instructions:
        system_prompt = f"""You are a document transformation assistant. Follow these instructions to rewrite the content:

{custom_instructions}

Return only the rewritten content, no explanations."""
    else:
        system_prompt = REWRITE_PROMPTS.get(mode, REWRITE_PROMPTS["improve"])

    try:
        client = get_llm_client()
        model = get_model_name()

        response = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Filename: {filename}\n\n---\n\n{text}"},
            ],
            model=model,
            temperature=0.4,
        )

        return {
            "result": response,
            "mode": mode if not custom_instructions else "custom",
            "model_used": model,
            "original_length": len(text),
            "result_length": len(response),
        }

    except Exception as e:
        logger.error(f"Rewrite failed for {filename}: {e}")
        return {"error": str(e), "result": None}


def generate_spec(
    text: str,
    filename: str,
    focus: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a specification document from file content.

    Args:
        text: Source content
        filename: For context
        focus: Optional focus area (e.g., "security", "api", "data model")

    Returns:
        Dict with 'result' (spec document) or 'error'
    """
    if not llm_is_configured():
        return {"error": "llm_not_configured", "result": None}

    if not text or len(text.strip()) < 50:
        return {"error": "insufficient_content", "result": None}

    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS] + "\n\n[Content truncated...]"

    system_prompt = SPEC_GENERATION_PROMPT
    if focus:
        system_prompt += f"\n\nFocus particularly on aspects related to: {focus}"

    try:
        client = get_llm_client()
        model = get_model_name()

        response = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Source document: {filename}\n\n---\n\n{text}"},
            ],
            model=model,
            temperature=0.3,
        )

        return {
            "result": response,
            "source_file": filename,
            "focus": focus,
            "model_used": model,
        }

    except Exception as e:
        logger.error(f"Spec generation failed for {filename}: {e}")
        return {"error": str(e), "result": None}


def extract_parameters(
    text: str,
    filename: str,
    parameter_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Extract parameters and configuration values from file content.

    Args:
        text: Source content
        filename: For context
        parameter_types: Optional filter for types (e.g., ["env", "config", "api"])

    Returns:
        Dict with 'parameters' list and 'summary', or 'error'
    """
    if not llm_is_configured():
        return {"error": "llm_not_configured", "parameters": None}

    if not text or len(text.strip()) < 20:
        return {"error": "insufficient_content", "parameters": None}

    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS] + "\n\n[Content truncated...]"

    system_prompt = PARAMETER_EXTRACTION_PROMPT
    if parameter_types:
        system_prompt += f"\n\nFocus on these parameter types: {', '.join(parameter_types)}"

    try:
        client = get_llm_client()
        model = get_model_name()

        response = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"File: {filename}\n\n---\n\n{text}"},
            ],
            model=model,
            temperature=0.2,  # Lower temp for structured extraction
        )

        # Parse JSON response
        result = _parse_json_response(response)

        return {
            "parameters": result.get("parameters", []),
            "summary": result.get("summary", ""),
            "source_file": filename,
            "model_used": model,
        }

    except Exception as e:
        logger.error(f"Parameter extraction failed for {filename}: {e}")
        return {"error": str(e), "parameters": None}


def _parse_json_response(response: str) -> Dict[str, Any]:
    """Parse JSON from LLM response, handling markdown code blocks."""
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
        logger.warning("Failed to parse parameter extraction response as JSON")
        return {"parameters": [], "summary": response[:500]}


# ---------------------------------------------------------------------------
# Batch Operations
# ---------------------------------------------------------------------------

def batch_extract_parameters(
    files: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Extract parameters from multiple files and consolidate.

    Args:
        files: List of {"filename": str, "text": str}

    Returns:
        Dict with consolidated parameters across all files
    """
    all_params: List[Dict[str, Any]] = []
    file_results: List[Dict[str, Any]] = []

    for f in files:
        result = extract_parameters(f["text"], f["filename"])
        if result.get("parameters"):
            for param in result["parameters"]:
                param["file"] = f["filename"]
                all_params.append(param)
            file_results.append({
                "filename": f["filename"],
                "parameter_count": len(result["parameters"]),
            })

    # Deduplicate by name, keeping all sources
    consolidated: Dict[str, Dict[str, Any]] = {}
    for param in all_params:
        name = param.get("name", "")
        if name in consolidated:
            # Add to sources
            existing = consolidated[name]
            if "sources" not in existing:
                existing["sources"] = [existing.pop("file", "unknown")]
            existing["sources"].append(param.get("file", "unknown"))
        else:
            consolidated[name] = param

    return {
        "parameters": list(consolidated.values()),
        "total_parameters": len(consolidated),
        "files_processed": len(file_results),
        "file_details": file_results,
    }
