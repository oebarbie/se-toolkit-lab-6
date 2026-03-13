# Task 2: The Documentation Agent - Implementation Plan

## Overview

Transform the Task 1 CLI chatbot into a true **agent** by adding tools and an agentic loop. The agent will be able to navigate the project wiki using `read_file` and `list_files` tools to find answers.

## LLM Provider and Model

**Provider:** Qwen Code API (via qwen-code-oai-proxy)
**Model:** `qwen3-coder-plus`

**Rationale:** Strong tool-calling capabilities, already configured from Task 1.

## Tool Definitions

### 1. `read_file`

**Purpose:** Read contents of a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root

**Returns:** File contents as string, or error message if file doesn't exist.

**Security:**
- Reject paths containing `../` (path traversal)
- Reject absolute paths
- Only allow files within project root

**Schema:**
```json
{
  "name": "read_file",
  "description": "Read a file from the project repository",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
      }
    },
    "required": ["path"]
  }
}
```

### 2. `list_files`

**Purpose:** List files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root

**Returns:** Newline-separated listing of entries.

**Security:**
- Reject paths containing `../` (path traversal)
- Reject absolute paths
- Only allow directories within project root

**Schema:**
```json
{
  "name": "list_files",
  "description": "List files and directories at a given path",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative directory path from project root (e.g., 'wiki')"
      }
    },
    "required": ["path"]
  }
}
```

## Agentic Loop Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agentic Loop                                  │
│                                                                  │
│  1. Send question + tool definitions to LLM                      │
│         │                                                        │
│         ▼                                                        │
│  2. Parse LLM response                                           │
│         │                                                        │
│         ├─ Has tool_calls? ──yes──▶ 3. Execute tools            │
│         │                        4. Append results as messages   │
│         │                        5. Loop back to step 1          │
│         │                                                        │
│         no                                                       │
│         │                                                        │
│         ▼                                                        │
│  6. Extract answer + source                                      │
│  7. Output JSON and exit                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Loop Steps

1. **Initial Request:** Send user question with system prompt and tool definitions
2. **Parse Response:** Check if LLM returned `tool_calls` or a final answer
3. **Execute Tools:** For each tool call, execute the corresponding function
4. **Append Results:** Add tool results as `tool` role messages
5. **Continue Loop:** Send updated conversation back to LLM
6. **Final Answer:** When no tool calls, extract answer and source
7. **Output:** Return JSON with `answer`, `source`, and `tool_calls`

### Loop Limits

- Maximum 10 tool calls per question
- Timeout: 60 seconds total

## System Prompt Strategy

The system prompt will instruct the LLM to:

1. Use `list_files` to discover wiki directory structure
2. Use `read_file` to read relevant wiki files
3. Find the specific section that answers the question
4. Include the source reference (file path + section anchor)
5. Only make tool calls when necessary

**Example System Prompt:**
```
You are a documentation agent that answers questions using the project wiki.

You have access to two tools:
- list_files: List files in a directory
- read_file: Read contents of a file

To answer questions:
1. First use list_files to explore the wiki directory
2. Use read_file to read relevant files
3. Find the specific section that answers the question
4. Include the source as "filepath.md#section-anchor"

Always provide the source reference for your answer.
```

## Output Format

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

## Path Security Implementation

```python
def is_safe_path(path: str) -> bool:
    """Check if path is safe (no traversal outside project root)."""
    # Reject absolute paths
    if path.startswith('/'):
        return False
    # Reject path traversal
    if '..' in path.split('/'):
        return False
    # Reject paths starting with ../
    if path.startswith('../'):
        return False
    return True
```

## Files to Modify/Create

1. `plans/task-2.md` - This implementation plan
2. `agent.py` - Add tools and agentic loop
3. `AGENT.md` - Update with tools documentation
4. `tests/test_agent.py` - Add 2 regression tests

## Testing Strategy

**Test 1:** Question about merge conflicts
- Input: `"How do you resolve a merge conflict?"`
- Expected: `read_file` in tool_calls, `wiki/git-workflow.md` in source

**Test 2:** Question about wiki files
- Input: `"What files are in the wiki?"`
- Expected: `list_files` in tool_calls

## Success Criteria

- [ ] Tools `read_file` and `list_files` implemented
- [ ] Agentic loop executes and feeds results back
- [ ] Output includes `answer`, `source`, and `tool_calls`
- [ ] Path security prevents directory traversal
- [ ] Maximum 10 tool calls enforced
- [ ] 2 regression tests pass
