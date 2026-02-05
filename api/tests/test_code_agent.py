# api/tests/test_code_agent.py
"""
Integration tests for CodeAgent.

These tests make real API calls to Anthropic, so they require:
1. ANTHROPIC_API_KEY in .env
2. Network connectivity

Run with: python tests/test_code_agent.py
"""

import os
import sys
import tempfile
from pathlib import Path

# Add api directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment
from dotenv import load_dotenv
load_dotenv()


def test_agent_initialization():
    """Test that CodeAgent initializes correctly."""
    print("\n=== Testing CodeAgent Initialization ===")

    from services.agents.code_agent import CodeAgent, AgentConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CodeAgent(working_dir=tmpdir)

        assert agent.working_dir == tmpdir
        assert agent.sandbox is not None
        assert agent.dispatch is not None
        assert agent.provider is not None
        assert agent.provider.supports_tool_use()
        print("✓ Agent initialized with sandbox, dispatch, and provider")

        # Test with custom config
        config = AgentConfig(max_turns=10, confirm_destructive=False)
        agent2 = CodeAgent(working_dir=tmpdir, config=config)
        assert agent2.config.max_turns == 10
        print("✓ Agent accepts custom configuration")

    print("Initialization tests passed!")


def test_agent_simple_query():
    """Test agent with a simple query that uses tools."""
    print("\n=== Testing CodeAgent Simple Query ===")

    from services.agents.code_agent import CodeAgent

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file
        test_file = Path(tmpdir) / "hello.py"
        test_file.write_text("print('hello')\n")

        agent = CodeAgent(working_dir=tmpdir)

        # Simple query that should trigger read_file
        response = agent.run("What's in hello.py?")

        print(f"Response: {response[:200]}...")

        # Should have read the file and described its contents
        assert "hello" in response.lower() or "print" in response.lower(), \
            "Response should mention the file contents"
        print("✓ Agent read file and responded about contents")

        # Check turn history
        history = agent.get_history()
        assert len(history) >= 2, "Should have at least user and assistant turns"
        print(f"✓ Agent completed in {len(history)} turns")

    print("Simple query test passed!")


def test_agent_file_creation():
    """Test agent creating a new file."""
    print("\n=== Testing CodeAgent File Creation ===")

    from services.agents.code_agent import CodeAgent

    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CodeAgent(working_dir=tmpdir)

        # Ask agent to create a file
        response = agent.run(
            "Create a file called greet.py that defines a function greet(name) "
            "that returns 'Hello, {name}!'. Just create the file, nothing else."
        )

        print(f"Response: {response[:300]}...")

        # Check if file was created
        greet_file = Path(tmpdir) / "greet.py"
        assert greet_file.exists(), "Agent should have created greet.py"
        print("✓ Agent created greet.py")

        content = greet_file.read_text()
        assert "def greet" in content, "File should contain greet function"
        assert "Hello" in content, "File should contain greeting"
        print(f"✓ File content:\n{content}")

    print("File creation test passed!")


def test_agent_patch():
    """Test agent patching an existing file."""
    print("\n=== Testing CodeAgent File Patching ===")

    from services.agents.code_agent import CodeAgent

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create initial file
        calc_file = Path(tmpdir) / "calc.py"
        calc_file.write_text("def add(a, b):\n    return a + b\n")

        agent = CodeAgent(working_dir=tmpdir)

        # Ask agent to modify the file
        response = agent.run(
            "In calc.py, add a docstring to the add function. "
            "Use patch_file to make this change."
        )

        print(f"Response: {response[:300]}...")

        # Check if file was patched
        content = calc_file.read_text()
        assert '"""' in content or "'''" in content, "Should have added docstring"
        print(f"✓ Patched content:\n{content}")

    print("File patching test passed!")


def test_agent_command_execution():
    """Test agent running shell commands."""
    print("\n=== Testing CodeAgent Command Execution ===")

    from services.agents.code_agent import CodeAgent

    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CodeAgent(working_dir=tmpdir)

        # Ask agent to run a command
        response = agent.run("Run 'echo hello from agent' and tell me what it outputs.")

        print(f"Response: {response[:200]}...")

        assert "hello from agent" in response.lower(), \
            "Response should include command output"
        print("✓ Agent executed command and reported output")

    print("Command execution test passed!")


def test_agent_reset():
    """Test agent reset functionality."""
    print("\n=== Testing CodeAgent Reset ===")

    from services.agents.code_agent import CodeAgent

    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CodeAgent(working_dir=tmpdir)

        # Run a query
        agent.run("List the current directory")
        assert len(agent.messages) > 0
        assert len(agent.turns) > 0
        print("✓ Agent has history after query")

        # Reset
        agent.reset()
        assert len(agent.messages) == 0
        assert len(agent.turns) == 0
        print("✓ Agent history cleared after reset")

    print("Reset test passed!")


def main():
    """Run all tests."""
    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set. Cannot run integration tests.")
        print("Set the key in .env or environment before running.")
        sys.exit(1)

    print("=" * 60)
    print("CodeAgent Integration Tests")
    print("=" * 60)
    print("Note: These tests make real API calls to Anthropic")
    print()

    test_agent_initialization()
    test_agent_simple_query()
    test_agent_file_creation()
    test_agent_patch()
    test_agent_command_execution()
    test_agent_reset()

    print("\n" + "=" * 60)
    print("ALL INTEGRATION TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
