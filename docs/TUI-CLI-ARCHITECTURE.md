# TUI + CLI Architecture Implementation

## Summary

This document describes the architecture where:
- **TUI** = Primary user interface (Textual-based)
- **CLI** = Backend logger (system events, memory, tools)
- **Qwen3 Coder** = Will handle coding tasks (future integration)

## Architecture Flow

```
┌─────────────────────────────────────────────┐
│  User runs: python main.py                  │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  TUI Layer (User Interface)          │   │
│  │  - Textual-based UI                  │   │
│  │  - Message input/output               │   │
│  │  - Stats display                      │   │
│  │  - Log panel (filtered, configurable) │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  Backend Logger (CLI)                │   │
│  │  - Memory updates                    │   │
│  │  • Tool executions                   │   │
│  │  - LLM API calls                     │   │
│  │  - Session events                    │   │
│  └──────────────────────────────────────┘   │
│                                              │
└─────────────────────────────────────────────┘
        ↓
    AgentRuntime (core/agent.py)
        ↓
    Logging hooks → BackendLoggerBridge
```

## Files Created/Modified

### New Files

1. **`/Users/aditya/Coding/April/Open_INT/main.py`**
   - New project root entry point
   - Launches TUI with backend logger
   - Command-line arguments for model, log level, etc.

2. **`/Users/aditya/Coding/April/Open_INT/core/backend_logger.py`**
   - `BackendLoggerBridge` class
   - Logs to backend with structured tags: `[MEMORY]`, `[TOOL]`, `[LLM]`, `[SESSION]`, `[USER]`, `[AGENT]`, `[ERROR]`

3. **`/Users/aditya/Coding/April/Open_INT/logs/` directory**
   - Log directory for backend logs
   - Contains `.gitkeep`

### Modified Files

1. **`/Users/aditya/Coding/April/Open_INT/core/agent.py`**
   - Added `backend_logger` initialization
   - Added logging hooks in `run()` method:
     - User message logging
     - LLM request/response logging
     - Tool execution logging
     - Agent response logging

2. **`/Users/aditya/Coding/April/Open_INT/core/textual_tui.py`**
   - Updated `get_agent()` to show backend logger info
   - `APRILApp.__init__()` sets backend logger level from environment

3. **`/Users/aditya/Coding/April/Open_INT/core/__init__.py`**
   - Added exports for `BackendLoggerBridge`, `APRILLogger`, `get_logger`

4. **`/Users/aditya/Coding/April/Open_INT/cli/main.py`**
   - Added deprecation notice
   - Kept for backward compatibility

5. **`/Users/aditya/Coding/April/Open_INT/.gitignore`**
   - Already had `*.log` line

## Usage

### Launch TUI (Default)

```bash
python main.py
```

- Launches Textual TUI
- Backend logs to `logs/april_backend.log`
- Log panel hidden by default

### Launch with Debug Logging

```bash
python main.py --log-level DEBUG
```

- Backend logs all events
- Verbose logging in `logs/april_backend.log`

### Launch with Custom Model

```bash
python main.py --model qwen2.5-coder:7b
```

### Launch with Log Panel Visible

```bash
python main.py --show-logs
```

### Launch Without Agent (Testing)

```bash
python main.py --no-agent
```

### View Backend Logs

```bash
tail -f logs/april_backend.log
```

## Event Flow

### User Interaction

```
1. User types message in TUI input
         ↓
2. TUI calls agent.run(message)
         ↓
3. Backend logs: [USER] message...
         ↓
4. Agent logs: [LLM] Request to model...
         ↓
5. LLM returns response with tool calls
         ↓
6. Agent logs: [TOOL] Calling: shell
         ↓
7. Tool executes → Agent logs: [TOOL] Result: ...
         ↓
8. Agent logs: [LLM] Response from model...
         ↓
9. Agent extracts memories
         ↓
10. Agent logs: [MEMORY] extraction_complete
         ↓
11. Agent logs: [AGENT] response...
         ↓
12. TUI displays response to user
```

## Backend Log Format

```
============================================================
APRIL Backend Started
============================================================
Model: mistral
Log Level: INFO
Session: sess_abc123
Tools available: ['shell']
Memory database: data/april_memory.db
Launching Textual TUI...

[USER] What files are in this directory?
[LLM] Request to mistral (3 messages)
[TOOL] Calling: shell
[TOOL] Args: {'command': 'ls -la'}
[TOOL] Result: total 48 drwxr-xr-x...
[LLM] Response from mistral
[MEMORY] extraction_started: {}
[MEMORY] extraction_complete: {'count': 2}
[AGENT] The directory contains...
```

## Command-Line Arguments

| Argument | Description |
|----------|-------------|
| `-m, --model` | Override model from config |
| `--log-level` | Backend logger level (DEBUG, INFO, WARNING, ERROR) |
| `--log-file` | Path to backend log file |
| `--max-iterations` | Maximum tool call iterations |
| `--show-logs` | Show log panel in TUI |
| `--no-agent` | Run TUI without agent (testing) |

## Event Tags

- `[MEMORY]` - Memory extraction/updates
- `[TOOL]` - Tool executions
- `[LLM]` - LLM API calls (requests/responses)
- `[SESSION]` - Session lifecycle events
- `[USER]` - User input
- `[AGENT]` - Agent responses
- `[ERROR]` - Error events

## Log Files

- **Default:** `logs/april_backend.log`
- **Rotation:** 10MB files, keeps 5 backups
- **Format:** `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

## Testing

### Backend Logger Test

```bash
python3 -c "
from core.backend_logger import BackendLoggerBridge
from core.logging import APRILLogger
import os
logger = APRILLogger(name='test', level='INFO', log_file='logs/test.log')
bridge = BackendLoggerBridge(logger)
bridge.log_user_message('Hello')
bridge.log_llm_request('mistral', 3)
print('Backend logger test passed!')
"
```

### Check Log Output

```bash
cat logs/april_backend.log
```

## Future Integration

**Qwen3 Coder** will use this architecture to:
1. Read from the AgentRuntime's session and memory
2. Write generated code to the `data/` directory
3. Log code generation events to the backend logger
4. Extract memories from successful code generation

## Notes

- TUI is now the primary entry point via `python main.py`
- Backend CLI logger runs in the background, capturing all system events
- Log panel in TUI is configurable via `--show-logs` or `APRIL_TUI_SHOW_LOGS` env var
- Backend logs are written to file only (no console output for logs)
- The `cli/main.py` is kept for backward compatibility but marked as deprecated
