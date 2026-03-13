"""Regression tests for agent.py CLI."""

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


class TestAgentOutput:
    """Test agent.py output format."""

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

        # Parse stdout as JSON (only the last line, which is the JSON output)
        stdout_lines = result.stdout.strip().split("\n")
        json_line = stdout_lines[-1]  # Last line should be the JSON

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
