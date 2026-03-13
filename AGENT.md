# System Agent Documentation

## Overview

This agent answers questions using three information sources:
1. **Project wiki** - via `list_files` and `read_file` tools
2. **Source code** - via `read_file` tool
3. **Deployed backend API** - via `query_api` tool

## Architecture

### LLM Provider
- **Provider:** Qwen Code API (via qwen-code-oai-proxy)
- **Model:** `qwen3-coder-plus`

### Tools

#### read_file
Reads file contents from the project repository.
- **Parameters:** `path` (relative path from project root)
- **Security:** Blocks path traversal (../) and absolute paths

#### list_files
Lists directory contents.
- **Parameters:** `path` (relative directory path)
- **Security:** Blocks path traversal

#### query_api
Queries the deployed backend API with authentication.
- **Parameters:** `method` (GET/POST/PUT/DELETE), `path` (API endpoint), `body` (optional JSON)
- **Authentication:** Bearer token using `LMS_API_KEY`
- **Base URL:** `AGENT_API_BASE_URL` env var (default: http://localhost:42002)

### Agentic Loop
1. Send question + tool definitions to LLM
2. If LLM returns tool_calls, execute tools and append results
3. Loop back to step 1 with updated conversation
4. When LLM returns final answer, extract source and output JSON
5. Maximum 15 tool calls per question

## Configuration

### Environment Variables
| Variable | Source | Purpose |
|----------|--------|---------|
| LLM_API_KEY | .env.agent.secret | LLM API authentication |
| LLM_API_BASE | .env.agent.secret | LLM endpoint URL |
| LLM_MODEL | .env.agent.secret | Model name |
| LMS_API_KEY | .env.docker.secret | Backend API authentication |
| AGENT_API_BASE_URL | Optional | Backend base URL (default: localhost:42002) |

**Important:** All config is read from environment variables, never hardcoded. The autochecker injects its own values.

## Tool Selection Strategy

The system prompt guides the LLM:
- **Wiki questions** ("How do I...", "What is the workflow...") → `list_files`/`read_file`
- **Data queries** ("How many items...", "What is the score...") → `query_api`
- **System facts** ("What framework...", "What port...") → `query_api` or `read_file`
- **Source code** ("Show me the code...") → `read_file`

## Lessons Learned

1. **Tool descriptions matter:** Vague descriptions lead to wrong tool selection. Be specific about when to use each tool.

2. **Content truncation:** Large files get truncated. The agent needs to handle partial content gracefully.

3. **API error handling:** The query_api tool must handle connection errors and return meaningful error messages.

4. **Source extraction:** The source field is optional for API questions but required for wiki questions. The regex extractor handles both file paths and API endpoints.

5. **Iteration is key:** Running run_eval.py repeatedly and fixing failures is essential. Each failure reveals a gap in tool selection or implementation.

## Final Eval Score

(To be updated after passing all 10 local questions)

## Usage

```bash
# Basic usage
uv run agent.py "Your question here"

# Run local evaluation
uv run run_eval.py

# Run single question for debugging
uv run run_eval.py --index 3
```

## Output Format

```json
{
  "answer": "The answer text",
  "source": "wiki/file.md#section or /api/endpoint",
  "tool_calls": [
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": "..."}
  ]
}
```
