# Agent Documentation

## Overview

This agent is a CLI program that takes a question as input, sends it to an LLM, and returns a structured JSON answer.

## Architecture

### LLM Provider

**Provider:** Qwen Code API (via qwen-code-oai-proxy)

**Model:** `qwen3-coder-plus`

**Why Qwen Code:**
- 1000 free requests per day
- Works from Russia without restrictions
- No credit card required
- OpenAI-compatible API
- Strong reasoning capabilities

### Components

| Component | Description |
|-----------|-------------|
| `agent.py` | Main CLI script that handles input/output and LLM communication |
| `.env.agent.secret` | Environment configuration (API key, base URL, model) |
| `qwen-code-oai-proxy` | Local proxy that exposes Qwen Code via OpenAI-compatible API |

## How It Works

```
┌─────────────────┐     ┌──────────┐     ┌─────────────────────┐     ┌──────────┐
│ User Question   │ ──→ │ agent.py │ ──→ │ Qwen Code API       │ ──→ │ JSON     │
│ (CLI argument)  │     │          │     │ (via local proxy)   │     │ Response │
└─────────────────┘     └──────────┘     └─────────────────────┘     └──────────┘
```

1. User provides a question as a command-line argument
2. `agent.py` loads configuration from `.env.agent.secret`
3. Agent sends HTTP POST request to the LLM API
4. LLM returns the answer
5. Agent outputs JSON with `answer` and `tool_calls` fields

## Usage

### Basic Usage

```bash
uv run agent.py "Your question here"
```

### Example

```bash
uv run agent.py "What does REST stand for?"
```

**Output:**
```json
{"answer": "REST stands for **Representational State Transfer**.", "tool_calls": []}
```

### Output Format

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "The LLM's response text",
  "tool_calls": []
}
```

- `answer`: String containing the LLM's response
- `tool_calls`: Array of tool calls (empty for Task 1)

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
- **Network error:** Prints error to stderr, exits with code 1
- **Invalid LLM response:** Prints error to stderr, exits with code 1

## Testing

Run the regression test:

```bash
uv run pytest backend/tests/test_agent.py -v
```

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main agent CLI |
| `.env.agent.secret` | LLM configuration (not committed to git) |
| `AGENT.md` | This documentation |
| `plans/task-1.md` | Implementation plan |
| `backend/tests/test_agent.py` | Regression tests |
