# Documentation Agent

## Overview

This agent is a CLI program that answers questions using the project wiki. It has **tools** (`read_file`, `list_files`) that allow it to navigate and read files from the project repository, and an **agentic loop** that enables it to make multiple tool calls before providing a final answer.

## Architecture

### LLM Provider

**Provider:** Qwen Code API (via qwen-code-oai-proxy)

**Model:** `qwen3-coder-plus`

**Why Qwen Code:**
- 1000 free requests per day
- Works from Russia without restrictions
- No credit card required
- OpenAI-compatible API with tool calling support
- Strong reasoning capabilities

### Components

| Component | Description |
|-----------|-------------|
| `agent.py` | Main CLI script with tools and agentic loop |
| `.env.agent.secret` | Environment configuration (API key, base URL, model) |
| `qwen-code-oai-proxy` | Local proxy that exposes Qwen Code via OpenAI-compatible API |

### Tools

The agent has two tools:

#### `read_file`

Read the contents of a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as a string, or an error message if the file doesn't exist.

**Security:**
- Rejects absolute paths
- Rejects path traversal (`../`)
- Only allows files within project root

#### `list_files`

List files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated listing of entries.

**Security:**
- Rejects absolute paths
- Rejects path traversal (`../`)
- Only allows directories within project root

## Agentic Loop

The agentic loop enables the agent to:
1. Send the user's question + tool definitions to the LLM
2. If the LLM responds with `tool_calls` → execute each tool, append results as `tool` role messages, go to step 1
3. If the LLM responds with a text message (no tool calls) → that's the final answer
4. If 10 tool calls are reached → stop looping and provide whatever answer is available

```
Question ──▶ LLM ──▶ tool call? ──yes──▶ execute tool ──▶ back to LLM
                     │
                     no
                     │
                     ▼
                JSON output
```

### Loop Limits

- Maximum 10 tool calls per question
- Timeout: 60 seconds per LLM request

## System Prompt Strategy

The system prompt instructs the LLM to:
1. Use `list_files` to discover wiki directory structure
2. Use `read_file` to read relevant wiki files
3. Find the specific section that answers the question
4. Include the source reference (file path + section anchor)
5. Only make tool calls when necessary

## Usage

### Basic Usage

```bash
uv run agent.py "Your question here"
```

### Examples

**List wiki files:**
```bash
uv run agent.py "What files are in the wiki?"
```

**Find information about merge conflicts:**
```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Output Format

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "The answer text from the LLM",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

- `answer` (string, required): The LLM's response text
- `source` (string, required): The wiki section reference (e.g., `wiki/git-workflow.md#section-anchor`)
- `tool_calls` (array, required): All tool calls made during the agentic loop

**Note:** All debug/logging output goes to stderr, only the JSON result goes to stdout.

## Configuration

### Environment Variables

Create `.env.agent.secret` in the project root:

```bash
# LLM API key
LLM_API_KEY=qwen-lab-api-key-2026

# API base URL (OpenAI-compatible endpoint)
LLM_API_BASE=http://127.0.0.1:42005/v1

# Model name
LLM_MODEL=qwen3-coder-plus
```

### Setting Up Qwen Code API

1. Install Qwen Code CLI on your VM:
   ```bash
   export PNPM_HOME="/home/me/.local/share/pnpm"
   export PATH="$PNPM_HOME:$PATH"
   pnpm add -g @qwen-code/qwen-code
   ```

2. Clone and configure qwen-code-oai-proxy:
   ```bash
   git clone https://github.com/inno-se-toolkit/qwen-code-oai-proxy ~/qwen-code-oai-proxy
   cd ~/qwen-code-oai-proxy
   cp .env.example .env
   # Edit .env to set QWEN_API_KEY
   docker compose up --build -d
   ```

3. The API will be available at `http://localhost:42005/v1`

## Error Handling

- **Missing question:** Prints usage to stderr, exits with code 1
- **Missing config:** Prints error to stderr, exits with code 1
- **Network error:** Returns error in JSON, exits with code 0
- **Invalid LLM response:** Returns error in JSON, exits with code 0
- **Max tool calls reached:** Returns partial answer with tool calls made

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main agent CLI with tools and agentic loop |
| `.env.agent.secret` | LLM configuration (not committed to git) |
| `AGENT.md` | This documentation |
| `plans/task-1.md` | Task 1 implementation plan |
| `plans/task-2.md` | Task 2 implementation plan |
| `tests/test_agent.py` | Regression tests |
