# Task 3: The System Agent - Implementation Plan

## Overview
Add `query_api` tool to enable the agent to query the deployed backend API.

## Tool: query_api
- **Parameters:** method (GET/POST/PUT/DELETE), path (API endpoint), body (optional JSON), auth (boolean, default true)
- **Authentication:** Bearer token using LMS_API_KEY from .env.docker.secret
- **Base URL:** AGENT_API_BASE_URL env var (default: http://localhost:42002)
- **Special feature:** The `auth` parameter allows testing unauthenticated access (e.g., checking 401 responses)

## Environment Variables
- LLM_API_KEY, LLM_API_BASE, LLM_MODEL from .env.agent.secret
- LMS_API_KEY from .env.docker.secret
- AGENT_API_BASE_URL (optional, defaults to localhost:42002)

## System Prompt
Guide LLM to use:
- list_files/read_file for wiki questions
- query_api for data queries and system facts
- read_file for source code questions
- query_api with auth=false for testing unauthenticated access

## Testing
- Test query_api with GET /items/
- Test system facts questions
- Run run_eval.py and iterate

## Benchmark Results

### Initial Score
**5/10 passed** - Failed on question 6 about HTTP status code without authentication

### First Failures
1. **Question 6:** "What HTTP status code does the API return when you request /items/ without sending an authentication header?"
   - **Problem:** The agent always sent authentication, so it got 200 instead of 401
   - **Fix:** Added `auth` parameter to `query_api` tool to allow testing unauthenticated access

### Iteration Strategy
1. Added `auth` boolean parameter to `query_api` tool (defaults to true)
2. Updated tool schema to document when to use `auth: false`
3. Updated system prompt to guide LLM on authentication testing
4. Re-ran evaluation - all 10 questions passed

### Final Score
**10/10 passed** (100%)

All questions pass including:
- Wiki lookup (branch protection, SSH)
- Source code analysis (web framework, router modules)
- Data queries (item count)
- Authentication testing (401 status code)
- Bug diagnosis (division by zero, top-learners crash)
- Reasoning (request lifecycle, ETL idempotency)
