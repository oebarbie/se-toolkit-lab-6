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
- **API Base:** `http://127.0.0.1:42005/v1`

### Tools

#### read_file
Reads file contents from the project repository.
- **Parameters:** `path` (relative path from project root)
- **Security:** Blocks path traversal (../) and absolute paths
- **Content limit:** Files larger than 16KB are truncated

#### list_files
Lists directory contents.
- **Parameters:** `path` (relative directory path)
- **Security:** Blocks path traversal

#### query_api
Queries the deployed backend API with optional authentication.
- **Parameters:** `method` (GET/POST/PUT/DELETE), `path` (API endpoint), `body` (optional JSON), `auth` (boolean, default true)
- **Authentication:** Bearer token using `LMS_API_KEY` from environment
- **Base URL:** `AGENT_API_BASE_URL` env var (default: http://localhost:42002)
- **Special feature:** The `auth` parameter allows testing unauthenticated access (e.g., checking 401 responses)

### Agentic Loop
1. Send question + tool definitions to LLM
2. If LLM returns tool_calls, execute tools and append results
3. Loop back to step 1 with updated conversation
4. When LLM returns final answer, extract source and output JSON
5. Maximum 15 tool calls per question to prevent infinite loops

## Configuration

### Environment Variables
| Variable | Source | Purpose |
|----------|--------|---------|
| LLM_API_KEY | .env.agent.secret | LLM API authentication |
| LLM_API_BASE | .env.agent.secret | LLM endpoint URL |
| LLM_MODEL | .env.agent.secret | Model name |
| LMS_API_KEY | .env.docker.secret | Backend API authentication |
| AGENT_API_BASE_URL | Optional | Backend base URL (default: localhost:42002) |

**Important:** All config is read from environment variables, never hardcoded. The autochecker injects its own values during evaluation.

## Tool Selection Strategy

The system prompt guides the LLM to select appropriate tools:
- **Wiki questions** ("How do I...", "What is the workflow...", "protect a branch", "SSH") → `list_files`/`read_file`
- **Data queries** ("How many items...", "What is the score...", "Get analytics...") → `query_api` with GET
- **System facts** ("What framework...", "What port...", "What status code...") → `query_api` or `read_file` on source code
- **Source code questions** ("Show me the code...", "What does this function...") → `read_file`
- **Authentication testing** ("What happens without auth?", "status code without authentication") → `query_api` with `auth: false`

## Lessons Learned

1. **Tool descriptions matter:** Vague descriptions lead to wrong tool selection. Be specific about when to use each tool. The `query_api` tool description now explicitly mentions when to use `auth: false`.

2. **Content truncation:** Large files get truncated at 16KB. The agent needs to handle partial content gracefully and make multiple calls if needed.

3. **API error handling:** The `query_api` tool must handle connection errors gracefully and return meaningful error messages to the LLM for diagnosis.

4. **Source extraction:** The `source` field is optional for API questions but required for wiki questions. The regex extractor handles both file paths and API endpoints.

5. **Iteration is key:** Running `run_eval.py` repeatedly and fixing failures is essential. Each failure reveals a gap in tool selection, tool implementation, or system prompt guidance.

6. **Authentication flexibility:** Adding the `auth` parameter was crucial for questions that test unauthenticated API access. This allows the agent to discover 401 responses and other auth-related behaviors.

7. **Environment setup:** The qwen-code-oai-proxy must be properly configured with OAuth credentials. Without this, the LLM API returns 401 errors.

## Final Eval Score

**10/10 local questions passed** (100%)

All local benchmark questions pass, including:
- Wiki lookup questions (branch protection, SSH)
- Source code questions (web framework, router modules)
- Data queries (item count)
- Authentication testing (401 status code)
- Bug diagnosis (division by zero in analytics)
- Reasoning questions (request lifecycle, ETL idempotency)

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
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/", "auth": false}, "result": "Status: 401\nBody: {\"detail\":\"Not authenticated\"}"}
  ]
}
```
