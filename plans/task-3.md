# Task 3: The System Agent - Implementation Plan

## Overview
Add `query_api` tool to enable the agent to query the deployed backend API.

## Tool: query_api
- **Parameters:** method (GET/POST/PUT/DELETE), path (API endpoint), body (optional JSON)
- **Authentication:** Bearer token using LMS_API_KEY from .env.docker.secret
- **Base URL:** AGENT_API_BASE_URL env var (default: http://localhost:42002)

## Environment Variables
- LLM_API_KEY, LLM_API_BASE, LLM_MODEL from .env.agent.secret
- LMS_API_KEY from .env.docker.secret
- AGENT_API_BASE_URL (optional, defaults to localhost:42002)

## System Prompt
Guide LLM to use:
- list_files/read_file for wiki questions
- query_api for data queries and system facts
- read_file for source code questions

## Testing
- Test query_api with GET /items/
- Test system facts questions
- Run run_eval.py and iterate

## Benchmark Results
(To be filled after first run)
