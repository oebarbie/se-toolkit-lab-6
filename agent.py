#!/usr/bin/env python3
"""
Documentation Agent CLI - Calls an LLM with tools to answer questions using the project wiki.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with 'answer', 'source', and 'tool_calls' fields to stdout.
    All debug output goes to stderr.
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Maximum tool calls per question
MAX_TOOL_CALLS = 10
# Timeout for LLM requests in seconds
LLM_TIMEOUT = 60.0


def load_env() -> dict[str, str]:
    """Load environment variables from .env.agent.secret."""
    env_path = Path(__file__).parent / ".env.agent.secret"
    if not env_path.exists():
        print(f"Error: {env_path} not found", file=sys.stderr)
        sys.exit(1)
    
    load_dotenv(env_path)
    
    required = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]
    config = {}
    for key in required:
        value = os.getenv(key)
        if not value:
            print(f"Error: {key} not set in .env.agent.secret", file=sys.stderr)
            sys.exit(1)
        config[key] = value
    
    return config


def is_safe_path(path: str) -> bool:
    """Check if path is safe (no traversal outside project root)."""
    # Reject absolute paths
    if path.startswith('/'):
        return False
    # Reject path traversal
    parts = path.split('/')
    if '..' in parts:
        return False
    # Reject paths starting with ../
    if path.startswith('../'):
        return False
    return True


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent


def read_file(path: str) -> dict[str, Any]:
    """
    Read a file from the project repository.
    
    Args:
        path: Relative path from project root
        
    Returns:
        Dict with 'success' boolean and 'content' or 'error' message
    """
    if not is_safe_path(path):
        return {"success": False, "error": f"Unsafe path: {path}"}
    
    project_root = get_project_root()
    file_path = project_root / path
    
    if not file_path.exists():
        return {"success": False, "error": f"File not found: {path}"}
    
    if not file_path.is_file():
        return {"success": False, "error": f"Not a file: {path}"}
    
    try:
        content = file_path.read_text()
        return {"success": True, "content": content}
    except Exception as e:
        return {"success": False, "error": f"Error reading file: {e}"}


def list_files(path: str) -> dict[str, Any]:
    """
    List files and directories at a given path.
    
    Args:
        path: Relative directory path from project root
        
    Returns:
        Dict with 'success' boolean and 'entries' list or 'error' message
    """
    if not is_safe_path(path):
        return {"success": False, "error": f"Unsafe path: {path}"}
    
    project_root = get_project_root()
    dir_path = project_root / path
    
    if not dir_path.exists():
        return {"success": False, "error": f"Directory not found: {path}"}
    
    if not dir_path.is_dir():
        return {"success": False, "error": f"Not a directory: {path}"}
    
    try:
        entries = [entry.name for entry in dir_path.iterdir()]
        return {"success": True, "entries": entries}
    except Exception as e:
        return {"success": False, "error": f"Error listing directory: {e}"}


# Tool definitions for LLM function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the project repository. Use this to read wiki files or other documentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path in the project repository. Use this to explore directory structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki')"
                    }
                },
                "required": ["path"]
            }
        }
    }
]

# System prompt for the documentation agent
SYSTEM_PROMPT = """You are a documentation agent that answers questions using the project wiki.

You have access to two tools:
- list_files: List files in a directory. Use this to explore the wiki directory structure.
- read_file: Read contents of a file. Use this to read wiki files and find answers.

To answer questions:
1. Use list_files to explore the wiki directory and find relevant files
2. Use read_file to read the contents of relevant files
3. Find the specific section that answers the question
4. Include the source as "filepath.md#section-anchor" format

Always provide the source reference for your answer. The source should be the specific file and section that contains the answer.

If the question is not about the project documentation, you can answer directly without using tools."""


def execute_tool(name: str, args: dict[str, Any]) -> str:
    """
    Execute a tool and return the result as a string.
    
    Args:
        name: Tool name
        args: Tool arguments
        
    Returns:
        Tool result as string
    """
    if name == "read_file":
        path = args.get("path", "")
        if not path:
            return "Error: Missing required argument 'path'"
        result = read_file(path)
        if result["success"]:
            # Truncate very long file contents
            content = result["content"]
            if len(content) > 4000:
                content = content[:4000] + "\n... [truncated]"
            return content
        else:
            return f"Error: {result['error']}"
    elif name == "list_files":
        path = args.get("path", "")
        if not path:
            return "Error: Missing required argument 'path'"
        result = list_files(path)
        if result["success"]:
            return "\n".join(result["entries"])
        else:
            return f"Error: {result['error']}"
    else:
        return f"Error: Unknown tool '{name}'"


async def call_llm(
    messages: list[dict[str, Any]],
    config: dict[str, str],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """
    Call the LLM API and return the response.
    
    Args:
        messages: Conversation messages
        config: LLM configuration
        tools: Optional tool definitions for function calling
        
    Returns:
        LLM response data or None on error
    """
    api_base = config["LLM_API_BASE"]
    api_key = config["LLM_API_KEY"]
    model = config["LLM_MODEL"]
    
    url = f"{api_base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools
    
    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error calling LLM: {e}", file=sys.stderr)
        return None


def extract_source(answer: str) -> str:
    """Extract source reference from answer text."""
    # Match patterns like wiki/something.md#anchor or wiki/something.md
    match = re.search(r'(\w+/[\w-]+\.md(?:#[\w-]+)?)', answer)
    if match:
        return match.group(1)
    return ""


async def run_agentic_loop(
    question: str,
    config: dict[str, str],
) -> tuple[str, str, list[dict[str, Any]]]:
    """
    Run the agentic loop to answer a question.
    
    Args:
        question: User's question
        config: LLM configuration
        
    Returns:
        Tuple of (answer, source, tool_calls)
    """
    # Initialize conversation with system prompt
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    
    tool_calls: list[dict[str, Any]] = []
    tool_call_count = 0
    
    while tool_call_count < MAX_TOOL_CALLS:
        print(f"Calling LLM (iteration {tool_call_count + 1})...", file=sys.stderr)
        
        # Call LLM with tools
        response_data = await call_llm(messages, config, tools=TOOLS)
        
        if response_data is None:
            return ("Error: Failed to get response from LLM", "", tool_calls)
        
        try:
            choice = response_data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError) as e:
            print(f"Error parsing LLM response: {e}", file=sys.stderr)
            print(f"Response: {response_data}", file=sys.stderr)
            return ("Error: Failed to parse LLM response", "", tool_calls)
        
        # Check for tool calls
        tool_calls_in_response = message.get("tool_calls", [])
        
        if not tool_calls_in_response:
            # No tool calls - this is the final answer
            answer = message.get("content", "No answer provided")
            source = extract_source(answer)
            return (answer, source, tool_calls)
        
        # Execute tool calls
        for tool_call in tool_calls_in_response:
            if tool_call_count >= MAX_TOOL_CALLS:
                break
            
            tool_call_id = tool_call.get("id", "")
            function = tool_call.get("function", {})
            tool_name = function.get("name", "")
            
            # Parse arguments - API returns 'arguments' as JSON string
            tool_args = {}
            args_str = function.get("arguments", "{}")
            try:
                tool_args = json.loads(args_str)
            except json.JSONDecodeError:
                tool_args = {}
            
            print(f"Executing tool: {tool_name} with args: {tool_args}", file=sys.stderr)
            
            # Execute the tool
            result = execute_tool(tool_name, tool_args)
            
            # Record the tool call
            tool_calls.append({
                "tool": tool_name,
                "args": tool_args,
                "result": result[:500] if len(result) > 500 else result,  # Truncate for output
            })
            
            # Add assistant message with tool call
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [tool_call],
            })
            
            # Add tool response to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            })
            
            tool_call_count += 1
    
    # Max tool calls reached - try to get an answer
    print("Max tool calls reached, requesting final answer...", file=sys.stderr)
    messages.append({
        "role": "user",
        "content": "Please provide your final answer based on the information gathered so far. Include the source reference.",
    })
    
    response_data = await call_llm(messages, config, tools=None)
    
    if response_data is None:
        return ("Error: Max tool calls reached without a final answer", "", tool_calls)
    
    try:
        choice = response_data["choices"][0]
        message = choice["message"]
        answer = message.get("content", "No answer provided")
    except (KeyError, IndexError):
        answer = "Error: Max tool calls reached without a final answer"
    
    source = extract_source(answer)
    
    return (answer, source, tool_calls)


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"Your question here\"", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    
    # Load configuration
    config = load_env()
    print(f"Using model: {config['LLM_MODEL']}", file=sys.stderr)
    
    # Run agentic loop
    answer, source, tool_calls = asyncio.run(run_agentic_loop(question, config))
    
    # Output result as JSON
    result = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
