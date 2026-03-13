"""Regression tests for agent.py CLI."""

import json
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).parent.parent


def run_agent(question: str, project_root: Path) -> dict:
    result = subprocess.run(
        ["uv", "run", "agent.py", question],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=project_root,
    )
    stdout_lines = result.stdout.strip().split("\n")
    return json.loads(stdout_lines[-1])


class TestTask1BasicOutput:
    def test_agent_returns_valid_json(self, project_root: Path) -> None:
        output = run_agent("What is 2+2?", project_root)
        assert "answer" in output
        assert "tool_calls" in output
        assert isinstance(output["answer"], str)
        assert isinstance(output["tool_calls"], list)


class TestTask2DocumentationAgent:
    def test_list_files_tool(self, project_root: Path) -> None:
        output = run_agent("What files are in the wiki?", project_root)
        assert "answer" in output
        assert "source" in output
        assert "tool_calls" in output
        tool_names = [tc.get("tool") for tc in output["tool_calls"]]
        assert "list_files" in tool_names

    def test_read_file_tool(self, project_root: Path) -> None:
        output = run_agent("How do you resolve a merge conflict?", project_root)
        assert "answer" in output
        tool_names = [tc.get("tool") for tc in output["tool_calls"]]
        assert "read_file" in tool_names or "list_files" in tool_names


class TestTask3SystemAgent:
    def test_query_api_tool(self, project_root: Path) -> None:
        output = run_agent("How many items are in the database?", project_root)
        assert "answer" in output
        assert "tool_calls" in output
        tool_names = [tc.get("tool") for tc in output["tool_calls"]]
        assert "query_api" in tool_names

    def test_system_facts(self, project_root: Path) -> None:
        output = run_agent("What framework does the backend use?", project_root)
        assert "answer" in output
        assert len(output["answer"].strip()) > 0
