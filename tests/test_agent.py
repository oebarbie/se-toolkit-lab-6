"""Regression tests for agent.py CLI - Task 2: Documentation Agent."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def agent_script(project_root: Path) -> Path:
    """Return the path to agent.py."""
    return project_root / "agent.py"


def run_agent(question: str, project_root: Path) -> dict:
    """Run the agent and return the parsed JSON output."""
    result = subprocess.run(
        ["uv", "run", "agent.py", question],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=project_root,
    )
    
    # Parse stdout as JSON (last line)
    stdout_lines = result.stdout.strip().split("\n")
    json_line = stdout_lines[-1]
    return json.loads(json_line)


class TestTask1BasicOutput:
    """Test basic JSON output format (Task 1)."""

    def test_agent_returns_valid_json(self, agent_script: Path) -> None:
        """Test that agent.py outputs valid JSON with required fields."""
        result = subprocess.run(
            ["uv", "run", str(agent_script), "What is 2+2?"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=agent_script.parent,
        )

        # Check exit code
        assert result.returncode == 0, f"Agent failed: {result.stderr}"

        # Parse stdout as JSON
        stdout_lines = result.stdout.strip().split("\n")
        json_line = stdout_lines[-1]

        try:
            output = json.loads(json_line)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON output: {e}\nStdout: {result.stdout}")

        # Check required fields
        assert "answer" in output, "Missing 'answer' field in output"
        assert "tool_calls" in output, "Missing 'tool_calls' field in output"

        # Check field types
        assert isinstance(output["answer"], str), "'answer' must be a string"
        assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"

        # Check answer is non-empty
        assert len(output["answer"].strip()) > 0, "'answer' must not be empty"


class TestTask2DocumentationAgent:
    """Test documentation agent with tools (Task 2)."""

    def test_list_files_tool(self, project_root: Path) -> None:
        """Test that agent uses list_files tool for wiki directory question."""
        output = run_agent("What files are in the wiki?", project_root)
        
        # Check required fields exist
        assert "answer" in output, "Missing 'answer' field"
        assert "source" in output, "Missing 'source' field"
        assert "tool_calls" in output, "Missing 'tool_calls' field"
        
        # Check that list_files was called
        tool_names = [tc.get("tool") for tc in output["tool_calls"]]
        assert "list_files" in tool_names, "Expected list_files tool to be called"
        
        # Check that list_files was called with wiki path
        list_files_calls = [tc for tc in output["tool_calls"] if tc.get("tool") == "list_files"]
        assert len(list_files_calls) > 0, "list_files was not called"
        
        for call in list_files_calls:
            args = call.get("args", {})
            if args.get("path") == "wiki":
                break
        else:
            pytest.fail("list_files was not called with path='wiki'")
        
        # Check answer is non-empty
        assert len(output["answer"].strip()) > 0, "'answer' must not be empty"

    def test_read_file_tool_for_merge_conflict(self, project_root: Path) -> None:
        """Test that agent uses read_file tool for merge conflict question."""
        output = run_agent("How do you resolve a merge conflict?", project_root)
        
        # Check required fields exist
        assert "answer" in output, "Missing 'answer' field"
        assert "source" in output, "Missing 'source' field"
        assert "tool_calls" in output, "Missing 'tool_calls' field"
        
        # Check that read_file was called
        tool_names = [tc.get("tool") for tc in output["tool_calls"]]
        assert "read_file" in tool_names, "Expected read_file tool to be called"
        
        # Check that list_files was also called (to discover files)
        assert "list_files" in tool_names, "Expected list_files tool to be called"
        
        # Check answer is non-empty
        assert len(output["answer"].strip()) > 0, "'answer' must not be empty"
