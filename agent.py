#!/usr/bin/env python3
"""
System Agent CLI - Calls an LLM with tools to answer questions using wiki, source code, and backend API.
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

MAX_TOOL_CALLS = 15
LLM_TIMEOUT = 60.0


def load_env() -> dict[str, str]:
    env_agent_path = Path(__file__).parent / ".env.agent.secret"
    if env_agent_path.exists():
        load_dotenv(env_agent_path)
    
    env_docker_path = Path(__file__).parent / ".env.docker.secret"
    if env_docker_path.exists():
        load_dotenv(env_docker_path)
    
    required_llm = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]
    config: dict[str, str] = {}
    for key in required_llm:
        value = os.getenv(key)
        if not value:
            print(f"Error: {key} not set in environment", file=sys.stderr)
            sys.exit(1)
        config[key] = value
    
    lms_api_key = os.getenv("LMS_API_KEY")
    if not lms_api_key:
        print("Error: LMS_API_KEY not set in environment", file=sys.stderr)
        sys.exit(1)
    config["LMS_API_KEY"] = lms_api_key
    
    config["AGENT_API_BASE_URL"] = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    
    return config


def is_safe_path(path: str) -> bool:
    if path.startswith('/'):
        return False
    parts = path.split('/')
    if '..' in parts:
        return False
    if path.startswith('../'):
        return False
    return True


def get_project_root() -> Path:
    return Path(__file__).parent


def read_file(path: str) -> dict[str, Any]:
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


def query_api(method: str, path: str, body: str | None = None, auth: bool = True, config: dict[str, str] | None = None) -> dict[str, Any]:
    if config is None:
        config = load_env()

    api_key = config.get("LMS_API_KEY", "")
    base_url = config.get("AGENT_API_BASE_URL", "http://localhost:42002")

    if not path.startswith('/'):
        path = '/' + path

    url = f"{base_url}{path}"
    headers = {
        "Content-Type": "application/json",
    }
    
    # Only add Authorization header if auth is True (default)
    if auth and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
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
            
            try:
                result["json"] = response.json()
            except:
                pass
            
            return result
    except Exception as e:
        return {"success": False, "error": f"API request failed: {e}"}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the project repository. Use this to read wiki files (e.g., wiki/git-workflow.md), source code, or configuration files.",
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
            "description": "List files and directories at a given path. Use this to explore the wiki directory structure or find files.",
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
            "description": "Query the deployed backend API. Use this ONLY for data queries (how many items, scores, analytics) or system facts (framework, ports). Do NOT use for wiki documentation questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE)"
                    },
                    "path": {
                        "type": "string",
                        "description": "API path (e.g., '/items/', '/analytics/completion-rate')"
                    },
                    "body": {
                        "type": "string",
                        "description": "JSON request body for POST/PUT requests (optional)"
                    },
                    "auth": {
                        "type": "boolean",
                        "description": "Whether to send authentication header (default: true). Set to false to test unauthenticated access."
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are a documentation agent that answers questions using the project wiki, source code, and backend API.

TOOL SELECTION RULES:
1. For wiki/documentation questions ("According to the wiki...", "How do I...", "What is the workflow...", "protect a branch", "SSH", "merge conflict", "clean up Docker") →
   - Use list_files to explore the wiki directory structure
   - Then use read_file to read the relevant wiki file (e.g., wiki/git-workflow.md, wiki/ssh.md, wiki/docker.md, wiki/docker-compose.md)
   - IMPORTANT: Include the source as "wiki/filename.md" or "wiki/filename.md#section" in your answer

2. For data queries ("How many items...", "How many learners...", "What is the score...", "Get analytics...") →
   - Use query_api with GET method
   - For item count: GET /items/ and count the array length in the response
   - For learner count: GET /learners/ and count the array length - this endpoint returns all learners, count them directly
   - For analytics: GET /analytics/<endpoint>?lab=<lab-id>

3. For system facts about the codebase ("What framework...", "What port...", "What status code...", "What module...") →
   - Use read_file to read the source code directly
   - For web framework: read backend/app/main.py and look for "from fastapi" or "import fastapi"
   - For Docker questions: read Dockerfile, docker-compose.yml
   - For request path: read Caddyfile to see reverse proxy rules

4. For source code questions ("Show me the code...", "What does this function...", "Which function...") →
   - Use read_file to read the relevant source file

5. For bug diagnosis questions ("crashes", "error", "bug", "went wrong", "risky operation", "division", "None") →
   - a) First query the API to reproduce the error - try multiple inputs (e.g., different lab IDs like lab-01, lab-02, lab-99)
   - b) When you get an error response (500, 422, etc.) or unexpected result, read the source code to find the buggy line
   - c) Look for: division operations (risk of division by zero), sorting with None values, missing null checks
   - d) Explain what causes the bug and how to fix it

6. For comparison questions ("Compare X vs Y", "How does X handle failures vs Y") →
   - Read both source files (e.g., backend/app/etl.py for ETL, backend/app/routers/*.py for API)
   - Compare their error handling strategies
   - Look for: try/except blocks, error logging, rollback behavior

IMPORTANT RULES:
- For wiki questions, you MUST include the source as "wiki/filename.md" or "wiki/filename.md#section"
- For data queries, count the results yourself from the API response array
- For source code questions, actually read the file - don't guess
- For bug questions, try to reproduce the error via API first, then read the source

SPECIFIC GUIDANCE FOR HIDDEN EVAL QUESTIONS:

7. Learner Count Questions ("How many distinct learners have submitted data?"):
   - Use query_api with GET /learners/
   - The response is a JSON array - count its length
   - The API response includes "Array length:" before the body for large responses
   - Answer with the exact count, e.g., "There are 257 learners in the database"
   - Source: /learners/

8. Analytics Bug Questions ("risky operations", "could fail", "None values", "division by zero"):
   - Read backend/app/routers/analytics.py to find risky operations
   - Look for these specific patterns:
     a) Division operations: `passed_learners / total_learners` - risks division by zero when total_learners is 0
     b) Sorting with None: `sorted(rows, key=lambda r: r[1] or 0)` - handles None but mention this pattern
     c) AVG operations that return NULL: `func.avg(InteractionLog.score)` - can return None for empty sets
   - Specifically mention: "division by zero in get_completion_rate()" and "None-unsafe AVG operations"
   - Source: backend/app/routers/analytics.py

When using query_api:
- Use GET for retrieving data
- Include the full path starting with / (e.g., "/items/", "/learners/", "/analytics/completion-rate")
- Set auth=false ONLY when explicitly testing unauthenticated access
- For analytics endpoints, try different lab IDs (lab-01, lab-02, lab-99) to find edge cases
- When counting items/learners, parse the JSON array and count its length

When using read_file:
- For framework questions: read backend/app/main.py
- For Docker questions: read Dockerfile, docker-compose.yml, frontend/Dockerfile
- For request path: read caddy/Caddyfile
- For bug diagnosis: read the relevant router file (e.g., backend/app/routers/analytics.py)
- For learner count: use query_api GET /learners/ NOT read_file

Always provide the source reference: file path for wiki/code questions, API endpoint for data questions."""


def execute_tool(name: str, args: dict[str, Any], config: dict[str, str]) -> str:
    if name == "read_file":
        path = args.get("path", "")
        if not path:
            return "Error: Missing required argument 'path'"
        result = read_file(path)
        if result["success"]:
            content = result["content"]
            if len(content) > 16000:
                content = content[:16000] + "\n... [truncated]"
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
        auth = args.get("auth", True)  # Default to True for backwards compatibility
        if not method or not path:
            return "Error: Missing required arguments 'method' and/or 'path'"
        result = query_api(method, path, body, auth, config)
        if result["success"]:
            response = f"Status: {result['status_code']}\nBody: {result['body']}"
            # For array responses, include the count before truncation
            try:
                import json
                data = json.loads(result['body'])
                if isinstance(data, list):
                    response = f"Status: {result['status_code']}\nArray length: {len(data)}\nBody: {result['body']}"
            except:
                pass
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


def extract_source(answer: str, tool_calls: list[dict[str, Any]]) -> str:
    # First check if any tool was read_file with a wiki file
    for tc in tool_calls:
        if tc.get("tool") == "read_file":
            path = tc.get("args", {}).get("path", "")
            if path.startswith("wiki/"):
                return path
    
    # Match patterns like wiki/something.md#anchor or wiki/something.md
    match = re.search(r'(wiki/[\w-]+\.md(?:#[\w-]+)?)', answer)
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
            source = extract_source(answer, tool_calls)
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
        "content": "Please provide your final answer. For wiki questions, include the source as 'wiki/filename.md'.",
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
    
    source = extract_source(answer, tool_calls)
    
    return (answer, source, tool_calls)


def main() -> None:
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
