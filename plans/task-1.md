# Task 1: Call an LLM from Code - Implementation Plan

## LLM Provider and Model

**Provider:** Qwen Code API (via qwen-code-oai-proxy)

**Model:** `qwen3-coder-plus`

**Rationale:**
- Qwen Code provides 1000 free requests per day
- Works from Russia without restrictions
- No credit card required
- Strong tool-calling capabilities for future tasks
- OpenAI-compatible API endpoint

## Architecture

### Components

1. **Environment Configuration** (`.env.agent.secret`)
   - `LLM_API_KEY`: API key for authentication
   - `LLM_API_BASE`: OpenAI-compatible endpoint URL
   - `LLM_MODEL`: Model name to use

2. **Agent CLI** (`agent.py`)
   - Parses command-line arguments (question as first arg)
   - Loads environment configuration from `.env.agent.secret`
   - Constructs OpenAI-compatible API request
   - Sends request to LLM via HTTP
   - Parses LLM response
   - Outputs structured JSON to stdout

### Data Flow

```
User question (CLI arg)
    ↓
agent.py (parse input)
    ↓
HTTP POST to LLM_API_BASE/chat/completions
    ↓
LLM response (JSON)
    ↓
agent.py (format output)
    ↓
{"answer": "...", "tool_calls": []} (stdout)
```

## Implementation Details

### Input Parsing
- Use `sys.argv[1]` to get the question
- Validate that a question was provided
- Exit with error code if missing

### LLM API Call
- Use `httpx` (already in dependencies) for async HTTP requests
- Set headers: `Content-Type: application/json`, `Authorization: Bearer <key>`
- Request body: OpenAI chat completions format
- Timeout: 60 seconds

### Output Formatting
- JSON with two required fields:
  - `answer`: String containing the LLM's response
  - `tool_calls`: Empty array (for Task 1)
- All output to stdout must be valid JSON
- Debug/logging output goes to stderr

### Error Handling
- Network errors: return error message in JSON, exit code 1
- Invalid response: return error message in JSON, exit code 1
- Missing question: print usage to stderr, exit code 1

## Files to Create

1. `plans/task-1.md` - This implementation plan
2. `agent.py` - Main agent CLI script
3. `AGENT.md` - Documentation
4. `backend/tests/test_agent.py` - Regression test

## Testing Strategy

1. **Manual testing:** Run `uv run agent.py "question"` and verify JSON output
2. **Regression test:** 
   - Run agent.py as subprocess
   - Parse stdout as JSON
   - Assert `answer` field exists and is non-empty
   - Assert `tool_calls` field exists and is array

## Success Criteria

- [ ] `uv run agent.py "What does REST stand for?"` outputs valid JSON
- [ ] JSON contains `answer` and `tool_calls` fields
- [ ] Response completes within 60 seconds
- [ ] Exit code 0 on success
- [ ] API key loaded from `.env.agent.secret` (not hardcoded)
