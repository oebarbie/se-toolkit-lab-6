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

The system prompt guides the LLM to select appropriate tools based on question type:

**1. Wiki/Documentation Questions** ("According to the wiki...", "How do I...", "What is the workflow...", "protect a branch", "SSH", "merge conflict", "clean up Docker")
- Use `list_files` to explore the wiki directory structure
- Then use `read_file` to read the relevant wiki file (e.g., `wiki/git-workflow.md`, `wiki/ssh.md`, `wiki/docker.md`)
- Include the source as "wiki/filename.md" or "wiki/filename.md#section" in the answer

**2. Data Queries** ("How many items...", "How many learners...", "What is the score...", "Get analytics...")
- Use `query_api` with GET method
- For item count: GET `/items/` and count the array length in the response
- For learner count: GET `/learners/` and count the array length
- For analytics: GET `/analytics/<endpoint>?lab=<lab-id>`

**3. System Facts** ("What framework...", "What port...", "What status code...", "What module...")
- Use `read_file` to read the source code directly
- For web framework: read `backend/app/main.py` and look for "from fastapi" imports
- For Docker questions: read `Dockerfile`, `docker-compose.yml`
- For request path: read `caddy/Caddyfile` to see reverse proxy rules

**4. Source Code Questions** ("Show me the code...", "What does this function...", "Which function...")
- Use `read_file` to read the relevant source file

**5. Bug Diagnosis** ("crashes", "error", "bug", "went wrong", "risky operation", "division", "None")
- First query the API to reproduce the error (try multiple inputs like lab-01, lab-02, lab-99)
- When getting error responses (500, 422), read the source code to find the buggy line
- Look for: division operations (division by zero), sorting with None values, missing null checks
- Explain the bug cause and fix

**6. Comparison Questions** ("Compare X vs Y", "How does X handle failures vs Y")
- Read both source files (e.g., `backend/app/etl.py` for ETL, `backend/app/routers/*.py` for API)
- Compare error handling strategies (try/except blocks, logging, rollback behavior)

### Authentication Handling

The `query_api` tool supports an `auth` parameter:
- `auth=true` (default): Sends `Authorization: Bearer <LMS_API_KEY>` header
- `auth=false`: Omits authentication header (useful for testing 401 responses)

This allows the agent to discover authentication requirements by testing both authenticated and unauthenticated requests.

## Lessons Learned

### Task 1: Basic LLM Integration
1. **Environment setup:** The qwen-code-oai-proxy must be properly configured with OAuth credentials. Without this, the LLM API returns 401 errors.
2. **Error handling:** The agent must gracefully handle LLM API failures and return meaningful error messages.

### Task 2: Documentation Agent
3. **Tool descriptions matter:** Vague descriptions lead to wrong tool selection. Be specific about when to use each tool.
4. **Content truncation:** Large files get truncated at 16KB. The agent needs to handle partial content gracefully.
5. **Source extraction:** The `source` field is required for wiki questions. The regex extractor handles both file paths and API endpoints.
6. **Iteration is key:** Running `run_eval.py` repeatedly and fixing failures is essential.

### Task 3: System Agent
7. **Authentication flexibility:** Adding the `auth` parameter was crucial for questions that test unauthenticated API access. This allows the agent to discover 401 responses.
8. **Data query interpretation:** The agent must parse JSON responses and count array elements for "how many" questions.
9. **Bug diagnosis workflow:** The agent can diagnose backend bugs by:
   - First reproducing errors through API calls with different inputs
   - Reading source code to identify the root cause
   - Looking for common patterns (division by zero, None-unsafe operations)
10. **Multi-file reasoning:** Complex questions require reading multiple files (e.g., Dockerfile + docker-compose.yml + Caddyfile for request path).
11. **System prompt specificity:** Detailed tool selection rules in the system prompt significantly improve accuracy.

## Final Eval Score

**10/10 local questions passed** (100%)

All local benchmark questions pass:
- Wiki lookup questions (branch protection, SSH)
- Source code questions (web framework, router modules)
- Data queries (item count)
- Authentication testing (401 status code)
- Bug diagnosis (division by zero in `/analytics/completion-rate`, None-unsafe sorting in `/analytics/top-learners`)
- Reasoning questions (request lifecycle, ETL idempotency)

**Note:** The autochecker bot tests 10 additional hidden questions and may use LLM-based judging for open-ended answers.

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
