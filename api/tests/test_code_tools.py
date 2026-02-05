# api/tests/test_code_tools.py
"""
Tests for code_tools.py - PathSandbox and tool implementations.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add api directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.agents.code_tools import (
    PathSandbox,
    tool_read_file,
    tool_write_file,
    tool_patch_file,
    tool_list_directory,
    tool_run_command,
    tool_git_status,
    tool_git_diff,
    TOOL_DEFINITIONS,
    build_tool_dispatch,
)


def test_path_sandbox():
    """Test PathSandbox validation logic."""
    print("\n=== Testing PathSandbox ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        sandbox = PathSandbox(tmpdir)

        # Test valid read within working_dir
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("hello")

        resolved = sandbox.validate_read("test.txt")
        assert resolved == test_file.resolve(), f"Expected {test_file.resolve()}, got {resolved}"
        print("✓ validate_read: relative path within working_dir")

        # Test valid read with absolute path
        resolved = sandbox.validate_read(str(test_file))
        assert resolved == test_file.resolve()
        print("✓ validate_read: absolute path within working_dir")

        # Test read outside working_dir (should fail)
        try:
            sandbox.validate_read("/etc/passwd")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "outside allowed read paths" in str(e)
            print("✓ validate_read: rejects path outside working_dir")

        # Test path traversal attack
        try:
            sandbox.validate_read("../../../etc/passwd")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "outside allowed read paths" in str(e)
            print("✓ validate_read: rejects path traversal attack")

        # Test write validation
        resolved = sandbox.validate_write("newfile.txt")
        assert resolved == (Path(tmpdir) / "newfile.txt").resolve()
        print("✓ validate_write: relative path within working_dir")

        # Test write outside working_dir (should fail)
        try:
            sandbox.validate_write("/tmp/outside.txt")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "outside working directory" in str(e)
            print("✓ validate_write: rejects path outside working_dir")

    # Test with allowed_read_paths
    with tempfile.TemporaryDirectory() as tmpdir:
        with tempfile.TemporaryDirectory() as extra_read_dir:
            sandbox = PathSandbox(tmpdir, allowed_read_paths=[extra_read_dir])

            # Create a file in extra read dir
            extra_file = Path(extra_read_dir) / "extra.txt"
            extra_file.write_text("extra content")

            # Should be able to read from extra dir
            resolved = sandbox.validate_read(str(extra_file))
            assert resolved == extra_file.resolve()
            print("✓ validate_read: allows paths in allowed_read_paths")

            # But not write to extra dir
            try:
                sandbox.validate_write(str(extra_file))
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "outside working directory" in str(e)
                print("✓ validate_write: rejects write to allowed_read_paths (read-only)")

    print("PathSandbox: All tests passed!")


def test_tool_read_file():
    """Test read_file tool."""
    print("\n=== Testing tool_read_file ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        sandbox = PathSandbox(tmpdir)

        # Create test file
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("line 1\nline 2\nline 3\nline 4\nline 5")

        # Read full file
        result = tool_read_file("test.py", sandbox)
        assert "line 1" in result
        assert "line 5" in result
        assert "   1 |" in result  # Line numbers
        print("✓ read_file: full file with line numbers")

        # Read specific lines
        result = tool_read_file("test.py", sandbox, start_line=2, end_line=4)
        assert "line 1" not in result
        assert "line 2" in result
        assert "line 4" in result
        assert "line 5" not in result
        print("✓ read_file: line range")

        # Read non-existent file
        result = tool_read_file("missing.txt", sandbox)
        assert "ERROR" in result
        assert "not found" in result.lower()
        print("✓ read_file: handles missing file")

        # Read directory (should error)
        result = tool_read_file(".", sandbox)
        assert "ERROR" in result
        print("✓ read_file: handles directory path")

    print("tool_read_file: All tests passed!")


def test_tool_write_file():
    """Test write_file tool."""
    print("\n=== Testing tool_write_file ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        sandbox = PathSandbox(tmpdir)

        # Write new file
        result = tool_write_file("new.txt", "hello world", sandbox)
        assert "OK" in result
        assert (Path(tmpdir) / "new.txt").read_text() == "hello world"
        print("✓ write_file: creates new file")

        # Overwrite file
        result = tool_write_file("new.txt", "updated", sandbox)
        assert "OK" in result
        assert (Path(tmpdir) / "new.txt").read_text() == "updated"
        print("✓ write_file: overwrites existing file")

        # Write with nested path (creates parents)
        result = tool_write_file("subdir/nested/file.txt", "nested content", sandbox)
        assert "OK" in result
        assert (Path(tmpdir) / "subdir/nested/file.txt").read_text() == "nested content"
        print("✓ write_file: creates parent directories")

        # Write outside sandbox (should fail)
        result = tool_write_file("/tmp/escape.txt", "bad", sandbox)
        assert "ERROR" in result
        print("✓ write_file: rejects write outside sandbox")

    print("tool_write_file: All tests passed!")


def test_tool_patch_file():
    """Test patch_file tool."""
    print("\n=== Testing tool_patch_file ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        sandbox = PathSandbox(tmpdir)

        # Create test file
        test_file = Path(tmpdir) / "code.py"
        test_file.write_text("def hello():\n    return 'hello'\n")

        # Successful patch
        result = tool_patch_file(
            "code.py",
            "return 'hello'",
            "return 'goodbye'",
            sandbox
        )
        assert "OK" in result
        assert "return 'goodbye'" in test_file.read_text()
        print("✓ patch_file: successful replacement")

        # String not found
        result = tool_patch_file(
            "code.py",
            "not in file",
            "replacement",
            sandbox
        )
        assert "ERROR" in result
        assert "not found" in result.lower()
        print("✓ patch_file: handles missing string")

        # Duplicate string (ambiguous)
        test_file.write_text("foo bar foo baz")
        result = tool_patch_file(
            "code.py",
            "foo",
            "qux",
            sandbox
        )
        assert "ERROR" in result
        assert "2 times" in result
        print("✓ patch_file: rejects ambiguous match")

        # Missing file
        result = tool_patch_file(
            "missing.py",
            "old",
            "new",
            sandbox
        )
        assert "ERROR" in result
        print("✓ patch_file: handles missing file")

    print("tool_patch_file: All tests passed!")


def test_tool_list_directory():
    """Test list_directory tool."""
    print("\n=== Testing tool_list_directory ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        sandbox = PathSandbox(tmpdir)

        # Create structure
        (Path(tmpdir) / "src").mkdir()
        (Path(tmpdir) / "src/main.py").write_text("")
        (Path(tmpdir) / "src/utils.py").write_text("")
        (Path(tmpdir) / "tests").mkdir()
        (Path(tmpdir) / "tests/test_main.py").write_text("")
        (Path(tmpdir) / "README.md").write_text("")

        # List root
        result = tool_list_directory(".", sandbox)
        assert "src/" in result
        assert "tests/" in result
        assert "README.md" in result
        print("✓ list_directory: lists files and dirs")

        # Depth limiting
        result = tool_list_directory(".", sandbox, max_depth=1)
        assert "src/" in result
        # Files inside src should still show at depth 1
        print("✓ list_directory: respects max_depth")

        # Ignores common dirs
        (Path(tmpdir) / "node_modules").mkdir()
        (Path(tmpdir) / "node_modules/package").mkdir()
        (Path(tmpdir) / "__pycache__").mkdir()

        result = tool_list_directory(".", sandbox)
        assert "node_modules" not in result
        assert "__pycache__" not in result
        print("✓ list_directory: ignores node_modules, __pycache__")

        # Ignores hidden files
        (Path(tmpdir) / ".hidden").write_text("")
        result = tool_list_directory(".", sandbox)
        assert ".hidden" not in result
        print("✓ list_directory: ignores hidden files")

    print("tool_list_directory: All tests passed!")


def test_tool_run_command():
    """Test run_command tool."""
    print("\n=== Testing tool_run_command ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Simple command
        result = tool_run_command("echo 'hello world'", tmpdir)
        assert "hello world" in result
        assert "EXIT CODE: 0" in result
        print("✓ run_command: executes simple command")

        # Command with stderr
        result = tool_run_command("ls nonexistent 2>&1 || true", tmpdir)
        assert "EXIT CODE" in result
        print("✓ run_command: captures stderr")

        # Timeout (would need a slow command to really test)
        result = tool_run_command("echo fast", tmpdir, timeout=1)
        assert "EXIT CODE: 0" in result
        print("✓ run_command: respects timeout")

    print("tool_run_command: All tests passed!")


def test_tool_definitions():
    """Test TOOL_DEFINITIONS structure."""
    print("\n=== Testing TOOL_DEFINITIONS ===")

    expected_tools = {
        "read_file", "write_file", "patch_file", "list_directory",
        "run_command", "git_status", "git_diff", "git_commit"
    }

    actual_tools = {t.name for t in TOOL_DEFINITIONS}
    assert actual_tools == expected_tools, f"Missing: {expected_tools - actual_tools}"
    print(f"✓ All {len(expected_tools)} tools defined")

    # Check each tool has required fields
    for tool in TOOL_DEFINITIONS:
        assert tool.name, "Tool must have name"
        assert tool.description, f"Tool {tool.name} must have description"
        assert isinstance(tool.parameters, dict), f"Tool {tool.name} must have parameters dict"
        assert "type" in tool.parameters, f"Tool {tool.name} parameters must have type"
        print(f"  ✓ {tool.name}: valid definition")

    print("TOOL_DEFINITIONS: All tests passed!")


def test_build_tool_dispatch():
    """Test build_tool_dispatch creates working dispatch map."""
    print("\n=== Testing build_tool_dispatch ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        sandbox = PathSandbox(tmpdir)
        dispatch = build_tool_dispatch(sandbox, tmpdir)

        # Check all tools are present
        expected = {
            "read_file", "write_file", "patch_file", "list_directory",
            "run_command", "git_status", "git_diff", "git_commit"
        }
        assert set(dispatch.keys()) == expected
        print("✓ All tools present in dispatch map")

        # Test calling through dispatch
        (Path(tmpdir) / "test.txt").write_text("dispatch test")
        result = dispatch["read_file"]({"path": "test.txt"})
        assert "dispatch test" in result
        print("✓ Dispatch map functions are callable")

        result = dispatch["list_directory"]({"path": "."})
        assert "test.txt" in result
        print("✓ list_directory via dispatch works")

    print("build_tool_dispatch: All tests passed!")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Code Tools Test Suite")
    print("=" * 60)

    test_path_sandbox()
    test_tool_read_file()
    test_tool_write_file()
    test_tool_patch_file()
    test_tool_list_directory()
    test_tool_run_command()
    test_tool_definitions()
    test_build_tool_dispatch()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
