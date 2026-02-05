#!/usr/bin/env python3
# tools/tamor_code.py
"""
Tamor Code: Interactive coding assistant CLI.

A Claude Code-like interface for assisted coding within Tamor projects.

Usage:
    # Interactive mode (default)
    cd ~/tamor-core/api && source venv/bin/activate && python ../tools/tamor_code.py

    # Or use the wrapper script
    tamor-code

    # Single prompt
    tamor-code -c "Fix the bug in main.py"

    # Specify working directory
    tamor-code --working-dir /path/to/project

    # Allow reading from additional directories
    tamor-code --allow-read /path/to/docs --allow-read /path/to/libs

Examples:
    cd ~/my-project && tamor-code
    tamor-code -c "Add docstrings to all functions in utils.py"
    tamor-code --working-dir ~/project --allow-read ~/shared-libs
"""

import os
import sys
from pathlib import Path

# Determine paths
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
API_DIR = PROJECT_ROOT / "api"
VENV_PYTHON = API_DIR / "venv" / "bin" / "python"

# If we're not running from the venv, re-exec with venv Python
if VENV_PYTHON.exists() and sys.executable != str(VENV_PYTHON):
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__] + sys.argv[1:])

import argparse
import readline  # Enables command history in input()

# Add api directory to Python path
sys.path.insert(0, str(API_DIR))

# Change to API directory so relative config paths work
# (core/config.py loads config/personality.json relative to cwd)
os.chdir(API_DIR)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(API_DIR / ".env")


def print_header():
    """Print the CLI header."""
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                      Tamor Code                            ║")
    print("║              Interactive Coding Assistant                  ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()


def print_help():
    """Print interactive mode help."""
    print("""
Commands:
  /help     - Show this help
  /clear    - Clear conversation history
  /status   - Show current working directory and settings
  /quit     - Exit the assistant

Tips:
  - The agent can read, write, and modify files in your project
  - It will explain what it's doing as it works
  - Multi-line input: end a line with \\ to continue
""")


def get_multiline_input(prompt: str) -> str:
    """Get input that may span multiple lines (backslash continuation)."""
    lines = []
    current_prompt = prompt

    while True:
        try:
            line = input(current_prompt)
        except EOFError:
            return ""

        if line.endswith("\\"):
            lines.append(line[:-1])  # Remove trailing backslash
            current_prompt = "... "
        else:
            lines.append(line)
            break

    return "\n".join(lines)


def run_interactive(agent, verbose: bool = False):
    """Run the interactive REPL loop."""
    print_help()
    print(f"Working directory: {agent.working_dir}")
    print()

    while True:
        try:
            user_input = get_multiline_input("\n► You: ").strip()
        except KeyboardInterrupt:
            print("\n")
            continue

        if not user_input:
            continue

        # Handle commands
        if user_input.startswith("/"):
            cmd = user_input.lower()
            if cmd == "/quit" or cmd == "/exit":
                print("Goodbye!")
                break
            elif cmd == "/help":
                print_help()
            elif cmd == "/clear":
                agent.reset()
                print("Conversation cleared.")
            elif cmd == "/status":
                print(f"Working directory: {agent.working_dir}")
                print(f"Provider: {agent.provider_name}")
                print(f"Model: {agent.model_name}")
                print(f"Turns in session: {len(agent.turns)}")
            else:
                print(f"Unknown command: {user_input}")
                print("Type /help for available commands.")
            continue

        # Run the agent
        print()
        print("┌" + "─" * 58 + "┐")
        print("│ Agent:                                                   │")
        print("└" + "─" * 58 + "┘")

        try:
            response = agent.run(user_input)
            print(response)
        except KeyboardInterrupt:
            print("\n[Interrupted]")
        except Exception as e:
            print(f"\n[Error: {e}]")
            if verbose:
                import traceback
                traceback.print_exc()

        print()
        print("─" * 60)


def run_single_prompt(agent, prompt: str, verbose: bool = False):
    """Run a single prompt and exit."""
    try:
        response = agent.run(prompt)
        print(response)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Tamor Code: Interactive coding assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Interactive mode in current directory
  %(prog)s -c "Fix the bug"             # Single command
  %(prog)s --working-dir ~/project      # Specify project directory
  %(prog)s --allow-read /docs           # Allow reading from additional paths
""",
    )

    parser.add_argument(
        "-c", "--command",
        metavar="PROMPT",
        help="Run a single prompt and exit",
    )

    parser.add_argument(
        "--working-dir", "-w",
        metavar="DIR",
        default=os.getcwd(),
        help="Working directory for the agent (default: current directory)",
    )

    parser.add_argument(
        "--allow-read", "-r",
        metavar="DIR",
        action="append",
        default=[],
        help="Additional directories the agent can read from (can be repeated)",
    )

    parser.add_argument(
        "--max-turns",
        type=int,
        default=25,
        help="Maximum turns per request (default: 25)",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed error traces",
    )

    args = parser.parse_args()

    # Validate working directory
    working_dir = Path(args.working_dir).resolve()
    if not working_dir.exists():
        print(f"Error: Working directory does not exist: {working_dir}", file=sys.stderr)
        sys.exit(1)
    if not working_dir.is_dir():
        print(f"Error: Not a directory: {working_dir}", file=sys.stderr)
        sys.exit(1)

    # Validate read paths
    allowed_read = []
    for path in args.allow_read:
        resolved = Path(path).resolve()
        if resolved.exists():
            allowed_read.append(str(resolved))
        else:
            print(f"Warning: --allow-read path does not exist: {path}", file=sys.stderr)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        print("Set it in api/.env or export it in your shell.", file=sys.stderr)
        sys.exit(1)

    # Import and create agent
    try:
        from services.agents.code_agent import CodeAgent, AgentConfig

        config = AgentConfig(max_turns=args.max_turns)
        agent = CodeAgent(
            working_dir=str(working_dir),
            allowed_read_paths=allowed_read if allowed_read else None,
            config=config,
        )
    except Exception as e:
        print(f"Error initializing agent: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    # Run in appropriate mode
    if args.command:
        run_single_prompt(agent, args.command, args.verbose)
    else:
        print_header()
        run_interactive(agent, args.verbose)


if __name__ == "__main__":
    main()
