# api/services/agents/planner.py
"""
Planner Agent (Phase M.3)

Purpose: Orchestrate multi-step writing projects
- Breaks complex requests into research → draft → review → revise tasks
- Creates pipeline_tasks entries for user approval
- Does NOT recursively call other agents (external loop design)

Constraints:
- Plans only, never writes content directly
- User must approve before tasks execute
- Each task runs through normal router when triggered
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentOutput, RequestContext
from services.llm_service import get_agent_llm
from utils.db import get_db

logger = logging.getLogger(__name__)


PLANNER_SYSTEM_PROMPT = """You are a Project Planner. Your role is to break down complex writing projects into clear, sequential tasks.

## Your Responsibilities
1. Analyze the user's writing request
2. Identify what research is needed
3. Plan the writing structure and approach
4. Create a logical sequence of tasks

## Task Types You Can Plan
- **research**: Gather information on a specific topic or question
- **draft**: Write a section or complete piece based on research
- **review**: Check a draft for accuracy, completeness, and style
- **revise**: Improve a draft based on review feedback

## Output Format
Respond with a JSON object containing:
{
    "project_summary": "Brief description of the overall project",
    "clarifying_questions": ["Any questions needed before planning"],
    "tasks": [
        {
            "task_type": "research|draft|review|revise",
            "description": "What this task should accomplish",
            "agent": "researcher|writer",
            "depends_on": [0, 1],  // indices of tasks this depends on (empty for first)
            "estimated_scope": "brief|moderate|extensive"
        }
    ],
    "notes": "Any additional context or recommendations"
}

## Guidelines
- Start with research tasks before writing tasks
- Keep individual tasks focused and achievable
- Include review tasks for quality control
- If the request is unclear, ask clarifying questions instead of planning
- For simple requests, a 2-3 task plan is sufficient
- For complex projects, break into 5-8 tasks maximum"""


class PlannerAgent(BaseAgent):
    """
    Planner agent for multi-step project orchestration.

    The Planner analyzes complex writing requests and creates a sequence
    of tasks (stored in pipeline_tasks) for user approval and execution.
    """

    name = "planner"
    description = "Breaks complex projects into research and writing tasks for step-by-step execution."

    def can_handle(self, ctx: RequestContext, intent: str) -> bool:
        """Handle planning, project, and multi-step intents."""
        planning_intents = {
            "plan",
            "project",
            "outline",
            "breakdown",
            "organize",
            "steps",
        }
        return intent.lower() in planning_intents

    def run(self, ctx: RequestContext, input_payload: Optional[Dict] = None) -> AgentOutput:
        """
        Create a project plan for a complex writing request.

        Args:
            ctx: Request context
            input_payload: Optional overrides

        Returns:
            AgentOutput with project plan or clarifying questions
        """
        start_time = time.time()

        # Check if there's an existing active plan for this project
        if ctx.project_id:
            existing_plan = self._get_active_plan(ctx.project_id)
            if existing_plan:
                return self._handle_existing_plan(ctx, existing_plan, start_time)

        # Build the prompt
        system_prompt = PLANNER_SYSTEM_PROMPT

        # Add project context if available
        if ctx.project_id:
            project_context = self._get_project_context(ctx.project_id)
            if project_context:
                system_prompt += f"\n\n## Project Context\n{project_context}"

        # Add memory context if available
        if ctx.memories:
            memory_context = self._format_memories(ctx.memories)
            system_prompt += f"\n\n## User Preferences\n{memory_context}"

        user_message = f"""## Planning Request
{ctx.user_message}

Create a project plan for this request. If clarification is needed, ask questions. Otherwise, provide a task breakdown."""

        try:
            llm, model, provider_name = get_agent_llm("planner")
            if not llm:
                return AgentOutput(
                    agent_name=self.name,
                    content={"error": "No LLM provider available"},
                    is_final=False,
                    error="No LLM provider configured",
                    processing_ms=int((time.time() - start_time) * 1000),
                )

            logger.info(f"Planner using provider: {provider_name}, model: {model}")

            response = llm.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                model=model,
            )

            # Parse the response
            plan_data = self._parse_response(response)

            # If there are clarifying questions, return them without creating tasks
            if plan_data.get("clarifying_questions"):
                return self._return_questions(plan_data, start_time, provider_name, model)

            # If we have a valid plan and a project, save the tasks
            if plan_data.get("tasks") and ctx.project_id:
                self._save_pipeline_tasks(ctx.project_id, plan_data)

            # Format the plan for display
            formatted_plan = self._format_plan(plan_data)

            processing_ms = int((time.time() - start_time) * 1000)

            return AgentOutput(
                agent_name=self.name,
                content=formatted_plan,
                is_final=True,
                artifacts=[
                    {
                        "type": "project_plan",
                        "data": plan_data,
                    }
                ],
                processing_ms=processing_ms,
                provider_used=provider_name,
                model_used=model,
            )

        except Exception as e:
            logger.error(f"Planner agent error: {e}")
            return AgentOutput(
                agent_name=self.name,
                content=f"Error creating plan: {str(e)}",
                is_final=True,
                error=str(e),
                processing_ms=int((time.time() - start_time) * 1000),
            )

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response as JSON, with fallback."""
        text = response.strip()

        # Handle markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse planner response as JSON")
            return {
                "project_summary": "Could not parse structured plan",
                "clarifying_questions": [],
                "tasks": [],
                "notes": response,
            }

    def _return_questions(
        self, plan_data: Dict, start_time: float, provider: str, model: str
    ) -> AgentOutput:
        """Return clarifying questions to the user."""
        questions = plan_data.get("clarifying_questions", [])
        formatted = "I need some clarification before I can create a plan:\n\n"
        for i, q in enumerate(questions, 1):
            formatted += f"{i}. {q}\n"

        return AgentOutput(
            agent_name=self.name,
            content=formatted,
            is_final=True,
            artifacts=[{"type": "clarifying_questions", "data": questions}],
            processing_ms=int((time.time() - start_time) * 1000),
            provider_used=provider,
            model_used=model,
        )

    def _format_plan(self, plan_data: Dict) -> str:
        """Format a plan for display to the user."""
        lines = []

        # Summary
        if plan_data.get("project_summary"):
            lines.append(f"## Project: {plan_data['project_summary']}\n")

        # Tasks
        tasks = plan_data.get("tasks", [])
        if tasks:
            lines.append("### Task Plan\n")
            for i, task in enumerate(tasks, 1):
                task_type = task.get("task_type", "unknown")
                description = task.get("description", "")
                agent = task.get("agent", "")
                scope = task.get("estimated_scope", "")

                lines.append(f"**{i}. [{task_type.upper()}]** {description}")
                if agent:
                    lines.append(f"   - Agent: {agent}")
                if scope:
                    lines.append(f"   - Scope: {scope}")
                lines.append("")

        # Notes
        if plan_data.get("notes"):
            lines.append(f"### Notes\n{plan_data['notes']}")

        # Status message
        if tasks:
            lines.append("\n---")
            lines.append("*Tasks have been saved. Use `/next-task` to begin execution.*")

        return "\n".join(lines)

    def _save_pipeline_tasks(self, project_id: int, plan_data: Dict) -> None:
        """Save planned tasks to the pipeline_tasks table."""
        conn = get_db()
        try:
            tasks = plan_data.get("tasks", [])

            for i, task in enumerate(tasks):
                # Build input context from dependencies
                depends_on = task.get("depends_on", [])
                input_context = json.dumps({"depends_on": depends_on}) if depends_on else None

                conn.execute(
                    """
                    INSERT INTO pipeline_tasks
                    (project_id, task_type, task_description, agent, status,
                     input_context, sequence_order)
                    VALUES (?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        project_id,
                        task.get("task_type", "research"),
                        task.get("description", ""),
                        task.get("agent", "researcher"),
                        input_context,
                        i + 1,
                    )
                )

            conn.commit()
            logger.info(f"Saved {len(tasks)} pipeline tasks for project {project_id}")

        except Exception as e:
            logger.error(f"Failed to save pipeline tasks: {e}")
            conn.rollback()
        finally:
            conn.close()

    def _get_active_plan(self, project_id: int) -> Optional[List[Dict]]:
        """Get any pending/active tasks for a project."""
        conn = get_db()
        try:
            cur = conn.execute(
                """
                SELECT id, task_type, task_description, agent, status, sequence_order
                FROM pipeline_tasks
                WHERE project_id = ? AND status IN ('pending', 'active')
                ORDER BY sequence_order
                """,
                (project_id,)
            )
            rows = cur.fetchall()
            if rows:
                return [dict(row) for row in rows]
            return None
        finally:
            conn.close()

    def _handle_existing_plan(
        self, ctx: RequestContext, tasks: List[Dict], start_time: float
    ) -> AgentOutput:
        """Handle request when there's an existing active plan."""
        lines = ["## Existing Plan in Progress\n"]
        lines.append("You have pending tasks for this project:\n")

        for task in tasks:
            status_icon = "⏳" if task["status"] == "pending" else "▶️"
            lines.append(
                f"{status_icon} **{task['sequence_order']}. [{task['task_type'].upper()}]** "
                f"{task['task_description']}"
            )

        lines.append("\n---")
        lines.append("*Use `/next-task` to execute the next pending task,")
        lines.append("or `/clear-plan` to start fresh.*")

        return AgentOutput(
            agent_name=self.name,
            content="\n".join(lines),
            is_final=True,
            processing_ms=int((time.time() - start_time) * 1000),
        )

    def _get_project_context(self, project_id: int) -> Optional[str]:
        """Get project info for context."""
        conn = get_db()
        try:
            cur = conn.execute(
                "SELECT name, description FROM projects WHERE id = ?",
                (project_id,)
            )
            row = cur.fetchone()
            if row:
                return f"Project: {row['name']}\nDescription: {row['description'] or 'None'}"
            return None
        finally:
            conn.close()

    def _format_memories(self, memories: List[Dict[str, Any]]) -> str:
        """Format relevant memories for context."""
        if not memories:
            return ""

        lines = []
        for mem in memories[:5]:
            category = mem.get("category", "general")
            content = mem.get("content", "")
            lines.append(f"- [{category}] {content}")

        return "\n".join(lines)
