# api/services/agents/code_agent.py
"""
Code Agent: Agentic coding assistant with filesystem tools.

This is the core conversation loop that:
1. Sends user messages to Claude with tool definitions
2. Executes any tool calls the model makes
3. Sends tool results back to continue the conversation
4. Repeats until the model stops requesting tools

Usage:
    from services.agents.code_agent import CodeAgent

    agent = CodeAgent(
        working_dir="/path/to/project",
        allowed_read_paths=["/path/to/docs"],
    )

    # Single turn (returns final response)
    response = agent.run("Fix the bug in main.py")

    # Streaming (yields chunks as they arrive)
    for chunk in agent.stream("Add a docstring to the function"):
        print(chunk, end="", flush=True)
"""

import logging
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass, field

from services.llm_service import (
    get_agent_llm,
    LLMToolResponse,
    ToolCall,
)
from services.agents.code_tools import (
    PathSandbox,
    TOOL_DEFINITIONS,
    build_tool_dispatch,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for the Code Agent."""
    max_turns: int = 25
    model: str = "claude-sonnet-4-5"
    confirm_destructive: bool = True


@dataclass
class AgentTurn:
    """Record of a single turn in the agent loop."""
    role: str  # "user", "assistant", "tool_result"
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)


class CodeAgent:
    """
    Interactive coding agent with filesystem and shell tools.

    The agent maintains conversation history and can execute multiple
    tool calls per turn, continuing until the model stops requesting tools.
    """

    SYSTEM_PROMPT = """You are an expert software engineer working in a code project.
You have access to filesystem and shell tools to read, write, and modify code.

Key behaviors:
- ALWAYS read files before modifying them to understand context
- Use patch_file for surgical edits (preferred over write_file for existing files)
- When making changes, explain what you're doing and why
- Run tests or linters after making changes if appropriate
- If you encounter errors, analyze them and try to fix them

Available tools give you the ability to:
- Read and write files
- List directory contents
- Execute shell commands
- Check git status and diffs
- Create commits

Be thorough but efficient. Complete the user's request step by step."""

    def __init__(
        self,
        working_dir: str,
        allowed_read_paths: Optional[List[str]] = None,
        config: Optional[AgentConfig] = None,
    ):
        """
        Initialize the Code Agent.

        Args:
            working_dir: Directory where the agent can write files
            allowed_read_paths: Additional directories the agent can read from
            config: Optional configuration overrides
        """
        self.working_dir = working_dir
        self.config = config or AgentConfig()

        # Set up path sandboxing
        self.sandbox = PathSandbox(
            working_dir=working_dir,
            allowed_read_paths=allowed_read_paths,
        )

        # Build tool dispatch map
        self.dispatch = build_tool_dispatch(self.sandbox, working_dir)

        # Get LLM provider (code agent uses Anthropic)
        provider, model_name, provider_name = get_agent_llm("code")
        if provider is None:
            raise RuntimeError(
                "No LLM provider available for code agent. "
                "Check ANTHROPIC_API_KEY in environment."
            )
        if not provider.supports_tool_use():
            raise RuntimeError(
                f"Provider {provider_name} does not support tool use. "
                "Code agent requires a provider with tool_use_completion()."
            )

        self.provider = provider
        self.model_name = model_name
        self.provider_name = provider_name

        # Conversation history
        self.messages: List[Dict[str, Any]] = []
        self.turns: List[AgentTurn] = []

    def run(self, user_message: str) -> str:
        """
        Run the agent on a user message and return the final response.

        This executes the full agentic loop: sending the message, executing
        any tool calls, sending results, and repeating until completion.

        Args:
            user_message: The user's request

        Returns:
            The agent's final text response
        """
        # Add user message to history
        self.messages.append({"role": "user", "content": user_message})
        self.turns.append(AgentTurn(role="user", content=user_message))

        final_text = ""
        turn_count = 0

        while turn_count < self.config.max_turns:
            turn_count += 1
            logger.info(f"Agent turn {turn_count}/{self.config.max_turns}")

            # Call the LLM with tools
            response = self.provider.tool_use_completion(
                messages=self.messages,
                tools=TOOL_DEFINITIONS,
                system=self.SYSTEM_PROMPT,
                model=self.model_name,
            )

            # Record assistant response
            if response.text:
                final_text = response.text

            # Add assistant message to history
            assistant_message = self._build_assistant_message(response)
            self.messages.append(assistant_message)

            # If no tool calls, we're done
            if not response.wants_tool_use:
                self.turns.append(AgentTurn(
                    role="assistant",
                    content=response.text or "",
                ))
                break

            # Execute tool calls and collect results
            tool_results = self._execute_tool_calls(response.tool_calls)

            # Record turn with tools
            self.turns.append(AgentTurn(
                role="assistant",
                content=response.text or "",
                tool_calls=response.tool_calls,
                tool_results=tool_results,
            ))

            # Add tool results to history for next turn
            self.messages.append({
                "role": "user",
                "content": tool_results,
            })

        if turn_count >= self.config.max_turns:
            logger.warning(f"Agent hit max turns ({self.config.max_turns})")
            final_text += "\n\n[Agent reached maximum turn limit]"

        return final_text

    def stream(self, user_message: str) -> Generator[str, None, None]:
        """
        Stream the agent's response, yielding text chunks as they arrive.

        Note: Currently streams only the final response text, not intermediate
        tool execution. Full streaming support requires provider streaming.

        Args:
            user_message: The user's request

        Yields:
            Text chunks from the agent's response
        """
        # For now, we use run() and yield the full response
        # TODO: Add true streaming when provider supports it
        response = self.run(user_message)
        yield response

    def _build_assistant_message(self, response: LLMToolResponse) -> Dict[str, Any]:
        """Build the assistant message for conversation history."""
        content = []

        if response.text:
            content.append({
                "type": "text",
                "text": response.text,
            })

        for tool_call in response.tool_calls:
            content.append({
                "type": "tool_use",
                "id": tool_call.id,
                "name": tool_call.name,
                "input": tool_call.arguments,
            })

        return {
            "role": "assistant",
            "content": content,
        }

    def _execute_tool_calls(
        self, tool_calls: List[ToolCall]
    ) -> List[Dict[str, Any]]:
        """
        Execute a batch of tool calls and return results.

        Args:
            tool_calls: List of tool calls from the model

        Returns:
            List of tool result blocks for the API
        """
        results = []

        for call in tool_calls:
            logger.info(f"Executing tool: {call.name}")
            logger.debug(f"  Arguments: {call.arguments}")

            if call.name not in self.dispatch:
                result = f"ERROR: Unknown tool '{call.name}'"
            else:
                try:
                    # Check for destructive operations
                    if self.config.confirm_destructive:
                        self._check_destructive(call)

                    # Execute the tool
                    result = self.dispatch[call.name](call.arguments)
                except ConfirmationRequired as e:
                    result = f"ERROR: {e}"
                except Exception as e:
                    logger.exception(f"Tool execution failed: {call.name}")
                    result = f"ERROR: Tool execution failed: {e}"

            logger.debug(f"  Result: {result[:200]}...")

            results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": result,
            })

        return results

    def _check_destructive(self, call: ToolCall) -> None:
        """
        Check if a tool call is destructive and should require confirmation.

        Currently this is a no-op for CLI mode (confirmation handled externally).
        In future, could integrate with a callback for interactive confirmation.
        """
        # Potentially destructive commands that might need confirmation:
        # - git_commit (changes git history)
        # - run_command with rm, git push, etc.
        # - write_file overwriting important files
        #
        # For now, we trust the sandbox and let the CLI handle confirmation
        pass

    def reset(self) -> None:
        """Clear conversation history and start fresh."""
        self.messages = []
        self.turns = []

    def get_history(self) -> List[AgentTurn]:
        """Return the conversation history."""
        return self.turns.copy()


class ConfirmationRequired(Exception):
    """Raised when a destructive operation requires user confirmation."""
    pass


# ---------------------------------------------------------------------------
# Convenience function for one-shot use
# ---------------------------------------------------------------------------

def run_code_agent(
    prompt: str,
    working_dir: str,
    allowed_read_paths: Optional[List[str]] = None,
    max_turns: int = 25,
) -> str:
    """
    One-shot function to run the code agent on a prompt.

    Args:
        prompt: The user's request
        working_dir: Directory where the agent can write files
        allowed_read_paths: Additional directories the agent can read from
        max_turns: Maximum number of turns before stopping

    Returns:
        The agent's final response text
    """
    config = AgentConfig(max_turns=max_turns)
    agent = CodeAgent(
        working_dir=working_dir,
        allowed_read_paths=allowed_read_paths,
        config=config,
    )
    return agent.run(prompt)
