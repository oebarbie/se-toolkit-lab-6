#!/usr/bin/env python3
"""
System Agent CLI - Calls an LLM with tools to answer questions using wiki, source code, and backend API.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with 'answer', 'source' (optional), and 'tool_calls' fields to stdout.
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
MAX_TOOL_CALLS = 15
# Timeout for LLM requests in seconds
LLM_TIMEOUT = 60.0


def load_env() -> dict[str, str]:
    """Load environment variables from .env files."""
    # Load LLM config from .env.agent.secret
    env_agent_path = Path(__file__).parent / ".env.agent.secret"
    if env_agent_path.exists():
        load_dotenv(env_agent_path)
    
    # Load LMS API key from .env.docker.secret
    env_docker_path = Path(__file__).parent / ".env.docker.secret"
    if env_docker_path.exists():
        load_dotenv(env_docker_path)
    
    # Get LLM config (required)
    required_llm = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]
    config: dict[str, str] = {}
    for key in required_llm:
        value = os.getenv(key)
        if not value:
            print(f"Error: {key} not set in environment", file=sys.stderr)
            sys.exit(1)
        config[key] = value
    
    # Get LMS API key (required for query_api)
    lms_api_key = os.getenv("LMS_API_KEY")
    if not lms_api_key:
        print("Error: LMS_API_KEY not set in environment", file=sys.stderr)
        sys.exit(1)
    config["LMS_API_KEY"] = lms_api_key
    
    # Get agent API base URL (optional, defaults to localhost)
    config["AGENT_API_BASE_URL"] = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    
    return config


def is_safe_path(path: str) -> bool:
    """Check if path is safe (no traversal outside project root)."""
    if path.startswith('/'):
        return False
    parts = path.split('/')
    if '..' in parts:
        return False
    if path.startswith('../'):
        return False
    return True


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent


def read_file(path: str) -> dict[str, Any]:
    """Read a file from the project repository."""
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
    """List files and directories at a given path."""
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


def query_api(method: str, path: str, body: str | None = None, config: dict[str, str] | None = None) -> dict[str, Any]:
    """
    Query the deployed backend API.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: API path (e.g., /items/, /analytics/completion-rate)
        body: Optional JSON request body for POST/PUT
        config: Configuration dict with LMS_API_KEY and AGENT_API_BASE_URL
        
    Returns:
        Dict with status_code and body
    """
    if config is None:
        config = load_env()
    
    api_key = config.get("LMS_API_KEY", "")
    base_url = config.get("AGENT_API_BASE_URL", "http://localhost:42002")
    
    # Normalize path
    if not path.startswith('/'):
        path = '/' + path
    
    url = f"{base_url}{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = client.post(url, headers=headers, content=body or "{}")
            elif method.upper() == "PUT":
                response = client.put(url, headers=headers, content=body or "{}")
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}
            
            result = {
                "success": True,
                "status_code": response.status_code,
                "body": response.text,
            }
            
            # Try to parse JSON
            try:
                result["json"] = response.json()
            except:
                pass
            
            return result
    except Exception as e:
        return {"success": False, "error": f"API request failed: {e}"}


# Tool definitions for LLM function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the project repository. Use this to read wiki files, source code, or configuration files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md', 'backend/app/main.py')"
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
                        "description": "Relative directory path from project root (e.g., 'wiki', 'backend')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Query the deployed backend API. Use this to get data from the system (items, analytics, scores) or check system status (framework, ports, status codes).",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE)"
                    },
                    "path": {
                        "type": "string",
                        "description": "API path (e.g., '/items/', '/analytics/completion-rate', '/health')"
                    },
                    "body": {
                        "type": "string",
                        "description": "JSON request body for POST/PUT requests (optional)"
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]

# System prompt for the system agent
SYSTEM_PROMPT = """You are a system agent that answers questions using:
1. The project wiki (use list_files and read_file)
2. The deployed backend API (use query_api)
3. The source code (use read_file)

Tool selection guide:
- Use list_files/read_file for wiki documentation questions (e.g., "How do I...", "What is the workflow for...")
- Use query_api for data queries (e.g., "How many items...", "What is the score...", "Get analytics...")
- Use query_api for system facts (e.g., "What framework...", "What port...", "What status code...")
- Use read_file for source code questions (e.g., "Show me the code for...", "What does this function do...")

When using query_api:
- Use GET for retrieving data
- Use POST for creating items
- Include the full path starting with /

Always provide the source reference when applicable (file path or API endpoint)."""


def execute_tool(name: str, args: dict[str, Any], config: dict[str, str]) -> str:
    """Execute a tool and return the result as a string."""
    if name == "read_file":
        path = args.get("path", "")
        if not path:
            return "Error: Missing required argument 'path'"
        result = read_file(path)
        if result["success"]:
            content = result["content"]
            if len(content) > 8000:
                content = content[:8000] + "\n... [truncated]"
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
    elif name == "query_api":
        method = args.get("method", "")
        path = args.get("path", "")
        body = args.get("body")
        if not method or not path:
            return "Error: Missing required arguments 'method' and/or 'path'"
        result = query_api(method, path, body, config)
        if result["success"]:
            response = f"Status: {result['status_code']}\nBody: {result['body']}"
            if len(response) > 4000:
                response = response[:4000] + "\n... [truncated]"
            return response
        else:
            return f"Error: {result['error']}"
    else:
        return f"Error: Unknown tool '{name}'"


async def call_llm(
    messages: list[dict[str, Any]],
    config: dict[str, str],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Call the LLM API and return the response."""
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
    # Match API endpoints
    match = re.search(r'(/[\w/-]+)', answer)
    if match:
        return match.group(1)
    return ""


async def run_agentic_loop(
    question: str,
    config: dict[str, str],
) -> tuple[str, str, list[dict[str, Any]]]:
    """Run the agentic loop to answer a question."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    
    tool_calls: list[dict[str, Any]] = []
    tool_call_count = 0
    
    while tool_call_count < MAX_TOOL_CALLS:
        print(f"Calling LLM (iteration {tool_call_count + 1})...", file=sys.stderr)
        
        response_data = await call_llm(messages, config, tools=TOOLS)
        
        if response_data is None:
            return ("Error: Failed to get response from LLM", "", tool_calls)
        
        try:
            choice = response_data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError) as e:
            print(f"Error parsing LLM response: {e}", file=sys.stderr)
            return ("Error: Failed to parse LLM response", "", tool_calls)
        
        tool_calls_in_response = message.get("tool_calls", [])
        
        if not tool_calls_in_response:
            answer = message.get("content") or "No answer provided"
            source = extract_source(answer)
            return (answer, source, tool_calls)
        
        for tool_call in tool_calls_in_response:
            if tool_call_count >= MAX_TOOL_CALLS:
                break
            
            tool_call_id = tool_call.get("id", "")
            function = tool_call.get("function", {})
            tool_name = function.get("name", "")
            
            tool_args = {}
            args_str = function.get("arguments", "{}")
            try:
                tool_args = json.loads(args_str)
            except json.JSONDecodeError:
                tool_args = {}
            
            print(f"Executing tool: {tool_name} with args: {tool_args}", file=sys.stderr)
            
            result = execute_tool(tool_name, tool_args, config)
            
            tool_calls.append({
                "tool": tool_name,
                "args": tool_args,
                "result": result[:500] if len(result) > 500 else result,
            })
            
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [tool_call],
            })
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            })
            
            tool_call_count += 1
    
    print("Max tool calls reached, requesting final answer...", file=sys.stderr)
    messages.append({
        "role": "user",
        "content": "Please provide your final answer based on the information gathered.",
    })
    
    response_data = await call_llm(messages, config, tools=None)
    
    if response_data is None:
        return ("Error: Max tool calls reached without a final answer", "", tool_calls)
    
    try:
        choice = response_data["choices"][0]
        message = choice["message"]
        answer = message.get("content") or "No answer provided"
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
    
    config = load_env()
    print(f"Using model: {config['LLM_MODEL']}", file=sys.stderr)
    print(f"API Base: {config['AGENT_API_BASE_URL']}", file=sys.stderr)
    
    answer, source, tool_calls = asyncio.run(run_agentic_loop(question, config))
    
    result = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
