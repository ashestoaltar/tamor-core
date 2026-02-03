# api/services/agents/engineer.py
"""
Engineer Agent (Phase 6.2)

Purpose: Technical output and code generation
- Generates code, patches, configs
- Respects repository context and patterns
- Outputs drop-in artifacts

Constraints:
- Must respect existing codebase patterns
- Cannot execute code (that's Executor's job)
- Should produce complete, working artifacts
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentOutput, Citation, RequestContext
from services.llm_service import get_agent_llm

logger = logging.getLogger(__name__)


ENGINEER_SYSTEM_PROMPT = """You are an Engineer Agent. Your role is to generate high-quality code, patches, and technical artifacts.

## Your Responsibilities
1. Generate clean, working code based on requirements
2. Follow existing patterns and conventions from the codebase
3. Produce complete, drop-in artifacts (not fragments)
4. Include necessary imports, error handling, and documentation
5. Respect the project's architecture and style

## Constraints
- Follow existing code patterns shown in the context
- Do NOT execute code - only generate it
- Do NOT make assumptions about undefined requirements - ask or note them
- Include all necessary imports and dependencies
- Add brief inline comments for complex logic only

## Code Style Guidelines
- Match the style of existing code in the project
- Use clear, descriptive names
- Keep functions focused and small
- Handle errors appropriately
- Type hints where the project uses them

## Output Format
For code generation, output the complete file or patch:
```language
// Full code here
```

For multiple files, separate with clear headers:
```
## File: path/to/file.py
```python
# code
```

## File: path/to/other.py
```python
# code
```
```

If you need clarification on requirements, state what's unclear before providing code."""


class EngineerAgent(BaseAgent):
    """
    Engineer agent for code generation and technical artifacts.

    The Engineer generates code that respects existing patterns and
    produces complete, working artifacts.
    """

    name = "engineer"
    description = "Generates code, patches, and configs following project patterns."

    def can_handle(self, ctx: RequestContext, intent: str) -> bool:
        """Handle code, implementation, and technical intents."""
        code_intents = {
            "code",
            "implement",
            "create",
            "build",
            "fix",
            "patch",
            "generate",
            "add",
            "update",
            "refactor",
        }
        return intent.lower() in code_intents

    def run(self, ctx: RequestContext, input_payload: Optional[Dict] = None) -> AgentOutput:
        """
        Generate code based on the request.

        Args:
            ctx: Request context (may include file context from retrieval)
            input_payload: Optional specs from Researcher

        Returns:
            AgentOutput with generated code
        """
        start_time = time.time()

        # Build the prompt
        system_prompt = ENGINEER_SYSTEM_PROMPT

        # Add project context if available
        if ctx.retrieved_chunks:
            code_context = self._format_code_context(ctx.retrieved_chunks)
            system_prompt += f"\n\n## Existing Code Context\n{code_context}"

        # Add memory context (preferences, patterns)
        if ctx.memories:
            prefs = self._extract_code_preferences(ctx.memories)
            if prefs:
                system_prompt += f"\n\n## User Preferences\n{prefs}"

        # Check for research input (specs from Researcher)
        specs = ""
        if input_payload and "research" in input_payload:
            specs = self._format_specs(input_payload["research"])
        elif ctx.prior_outputs:
            for output in ctx.prior_outputs:
                if output.agent_name == "researcher":
                    specs = self._format_specs(output.content)
                    break

        # Build user message
        user_message = ctx.user_message
        if specs:
            user_message = f"{ctx.user_message}\n\n## Technical Specifications\n{specs}"

        # Call LLM with agent-specific provider routing
        try:
            llm, model, provider_name = get_agent_llm("engineer")
            if not llm:
                return AgentOutput(
                    agent_name=self.name,
                    content="No LLM provider available.",
                    is_final=True,
                    error="No LLM provider configured",
                    processing_ms=int((time.time() - start_time) * 1000),
                )

            logger.info(f"Engineer using provider: {provider_name}, model: {model}")

            response = llm.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                model=model,
            )

            # Extract code artifacts from response
            artifacts = self._extract_code_artifacts(response)

            processing_ms = int((time.time() - start_time) * 1000)

            return AgentOutput(
                agent_name=self.name,
                content=response,
                is_final=True,  # Code output is user-facing
                artifacts=artifacts,
                processing_ms=processing_ms,
                provider_used=provider_name,
                model_used=model,
            )

        except Exception as e:
            logger.error(f"Engineer agent error: {e}")
            return AgentOutput(
                agent_name=self.name,
                content=f"Error generating code: {str(e)}",
                is_final=True,
                error=str(e),
                processing_ms=int((time.time() - start_time) * 1000),
            )

    def _format_code_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Format retrieved code chunks for context."""
        if not chunks:
            return "No existing code context available."

        lines = []
        seen_files = set()

        for chunk in chunks[:10]:  # Limit context size
            filename = chunk.get("filename", "unknown")
            content = chunk.get("text") or chunk.get("content", "")

            # Skip if we've seen this file
            if filename in seen_files:
                continue
            seen_files.add(filename)

            # Detect language from filename
            lang = self._detect_language(filename)

            lines.append(f"### {filename}")
            lines.append(f"```{lang}")
            lines.append(content[:1500])  # Truncate long files
            lines.append("```\n")

        return "\n".join(lines)

    def _detect_language(self, filename: str) -> str:
        """Detect programming language from filename."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "jsx",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".html": "html",
            ".css": "css",
            ".sql": "sql",
            ".sh": "bash",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
        }
        for ext, lang in ext_map.items():
            if filename.endswith(ext):
                return lang
        return ""

    def _extract_code_preferences(self, memories: List[Dict[str, Any]]) -> str:
        """Extract coding preferences from user memories."""
        prefs = []
        for mem in memories:
            category = mem.get("category", "")
            content = mem.get("content", "").lower()

            if category in ("preference", "engineering"):
                if any(w in content for w in ["code", "style", "prefer", "always", "never", "use"]):
                    prefs.append(f"- {mem.get('content', '')}")

        return "\n".join(prefs) if prefs else ""

    def _format_specs(self, research: Any) -> str:
        """Format research output as technical specs."""
        if isinstance(research, str):
            return research

        if not isinstance(research, dict):
            return str(research)

        lines = []

        if research.get("summary"):
            lines.append(f"**Overview:** {research['summary']}")

        findings = research.get("key_findings", [])
        if findings:
            lines.append("\n**Requirements:**")
            for f in findings:
                if isinstance(f, dict):
                    lines.append(f"- {f.get('finding', '')}")
                else:
                    lines.append(f"- {f}")

        return "\n".join(lines)

    def _extract_code_artifacts(self, response: str) -> List[Dict[str, Any]]:
        """Extract code blocks as artifacts from response."""
        import re

        artifacts = []

        # Find all code blocks
        pattern = r"```(\w*)\n(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)

        for i, (lang, code) in enumerate(matches):
            artifacts.append({
                "type": "code",
                "language": lang or "text",
                "content": code.strip(),
                "index": i,
            })

        # Check for file headers
        file_pattern = r"##\s*File:\s*(.+?)(?:\n|$)"
        file_matches = re.findall(file_pattern, response)

        if file_matches and len(file_matches) == len(artifacts):
            for i, filepath in enumerate(file_matches):
                artifacts[i]["filepath"] = filepath.strip()

        return artifacts
