# TUI + CLI Architecture - Complete Implementation

## Overview

This document describes the complete implementation of APRIL's TUI + CLI architecture where:
- **TUI** = Primary user interface (Textual-based)
- **CLI** = Backend logger (system events, memory, tools)
- **Qwen3 Coder** = Will handle coding tasks (future integration)

---

## Files Structure

### New Files Created

```
Open_INT/
├── main.py                              # NEW: Project root entry point
├── core/backend_logger.py               # NEW: Backend logger bridge
├── core/logger.py                       # RENAMED: From logging.py
├── core/widgets/logs.py                 # ENHANCED: Real-time log panel
├── core/widgets/status.py               # ENHANCED: Session info display
├── logs/                                # NEW: Log directory
│   └── .gitkeep
└── docs/
    ├── TUI-CLI-ARCHITECTURE.md          # NEW: Architecture documentation
    └── TUI-ENHANCEMENTS.md              # NEW: TUI enhancements guide
```

### Files Modified

1. **`core/agent.py`** - Added backend logger hooks
2. **`core/textual_tui.py`** - Enhanced with real-time logging
3. **`core/__init__.py`** - Added exports for new modules
4. **`cli/main.py`** - Added deprecation notice

---

## Architecture Flow

```
┌─────────────────────────────────────────────┐
│  User runs: python main.py                  │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Backend Logger Setup                       │
│  - Creates log file: logs/april_backend.log │
│  - Sets log level from CLI args             │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Load AgentConfig (from .env)               │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Create AgentRuntime                        │
│  - Initialize backend_logger                │
│  - Setup logging hooks                      │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Launch Textual TUI                         │
│  - Message list (user ↔ agent)              │
│  - Status bar                               │
│  - Stats panel                              │
│  - Log panel (filtered)                     │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Agent Runtime Events → Backend Logger      │
│  - [USER] User input                        │
│  - [LLM] API requests                       │
│  - [TOOL] Tool executions                   │
│  - [MEMORY] Memory updates                  │
│  - [AGENT] Agent responses                  │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  TUI Log Panel (Real-time)                  │
│  - Buffered logs (50 items)                 │
│  - Auto-flush every 500ms                   │
│  - Color-coded by level                     │
└─────────────────────────────────────────────┘
```

---

## Event Flow Example

```
User: "What files are in this directory?"

TUI Input → agent.run("What files are in this directory?")
         ↓
BackendLogger.log_user_message()
         ↓
[USER] What files are in this directory?
         ↓
[LLM] Request to mistral (3 messages)
         ↓
Tool: shell_execute(command="ls -la")
         ↓
[TOOL] Calling: shell
[TOOL] Args: {'command': 'ls -la'}
[TOOL] Result: total 48 drwxr-xr-x...
         ↓
[LLM] Response from mistral
         ↓
[AGENT] The directory contains:
- main.py
- cli/
- core/
- docs/
- logs/
- tests/

Display in TUI
```

---

## Log Panel Display

```
┌────────────────────────────────────────────┐
│ APRIL - An assistant with a body           │
├────────────────────────────────────────────┤
│                                            │
│ [✓ Ready]                                  │
│                                            │
│ ┌──────────────────────────────────────┐   │
│ │ [👤] What files are in this          │   │
│ │      directory?                      │   │
│ │                                      │   │
│ │ [🤖] The directory contains:         │   │
│ │      - main.py                       │   │
│ │      - cli/                          │   │
│ │      - core/                         │   │
│ └──────────────────────────────────────┘   │
│                                            │
│ ┌──────────────────────────────────────────┐
│ │ [12:34:56] [USER] What files...          │
│ │ [12:34:56] [LLM] Request to mistral...   │
│ │ [12:34:57] [TOOL] Calling: shell         │
│ │ [12:34:57] [TOOL] Result: total 48...    │
│ │ [12:34:57] [LLM] Response from mistral   │
│ │ [12:34:57] [AGENT] The directory...      │
│ └──────────────────────────────────────────┘
│                                            │
│    Type your message...                    │
└────────────────────────────────────────────┘
```

---

## Backend Logger Reference

### BackendLoggerBridge

**File:** `core/backend_logger.py`

**Features:**
- Structured log tags: `[MEMORY]`, `[TOOL]`, `[LLM]`, `[SESSION]`, `[USER]`, `[AGENT]`, `[ERROR]`
- Real-time callback support
- Thread-safe logging
- File output with rotation

**Methods:**

| Method | Description |
|--------|-------------|
| `log_user_message(message)` | Log user input |
| `log_agent_response(response)` | Log agent output |
| `log_memory_event(event_type, details)` | Log memory events |
| `log_tool_execution(tool_name, args, result)` | Log tool calls |
| `log_llm_request(model, message_count)` | Log LLM requests |
| `log_llm_response(model)` | Log LLM responses |
| `log_session_event(event_type, session_id)` | Log session events |
| `log_error(error_type, message)` | Log errors |
| `set_real_time_callback(callback)` | Register TUI callback |

### APRILLogger

**File:** `core/logger.py` (renamed from logging.py)

**Features:**
- Structured logging with levels
- File output with rotation (10MB, 5 backups)
- Console output
- Custom formatting

**Methods:**

| Method | Description |
|--------|-------------|
| `set_level(level)` | Change log level |
| `debug(message)` | Log debug message |
| `info(message)` | Log info message |
| `warning(message)` | Log warning message |
| `error(message)` | Log error message |
| `critical(message)` | Log critical message |

---

## Command-Line Arguments

### main.py

| Argument | Description | Example |
|----------|-------------|---------|
| `-m, --model` | Override model | `--model qwen2.5-coder:7b` |
| `--log-level` | Backend log level | `--log-level DEBUG` |
| `--log-file` | Log file path | `--log-file logs/my.log` |
| `--max-iterations` | Max tool calls | `--max-iterations 200` |
| `--show-logs` | Show log panel | `--show-logs` |
| `--no-agent` | TUI without agent | `--no-agent` |

### Examples

```bash
# Launch TUI with default config
python main.py

# Launch with debug logging
python main.py --log-level DEBUG

# Launch with custom model
python main.py --model qwen2.5-coder:7b

# Launch with visible log panel
python main.py --show-logs

# Launch without agent (testing)
python main.py --no-agent
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APRIL_LOG_LEVEL` | `WARNING` | Backend log level |
| `APRIL_TUI_SHOW_LOGS` | `false` | Show log panel in TUI |

---

## Log Tags Reference

| Tag | Description |
|-----|-------------|
| `[USER]` | User input messages |
| `[AGENT]` | Agent responses |
| `[LLM]` | LLM API requests/responses |
| `[TOOL]` | Tool executions |
| `[MEMORY]` | Memory extraction/updates |
| `[SESSION]` | Session lifecycle events |
| `[ERROR]` | Error events |

---

## Performance

- Buffer size: 50 logs (auto-flush)
- Flush interval: 500ms
- Max display logs: 100
- Log file rotation: 10MB, 5 backups
- Thread-safe: Yes (uses locks)

---

## Event Tags

### User Events

```python
[USER] Hello, how are you?
```

### LLM Events

```python
[LLM] Request to mistral (3 messages)
[LLM] Response from mistral
```

### Tool Events

```python
[TOOL] Calling: shell
[TOOL] Args: {'command': 'ls -la'}
[TOOL] Result: total 48 drwxr-xr-x...
```

### Memory Events

```python
[MEMORY] extraction_started: {}
[MEMORY] extraction_complete: {'count': 2}
```

### Session Events

```python
[SESSION] created - ID: sess_abc123
[SESSION] reset
```

### Agent Events

```python
[AGENT] The directory contains:
- main.py
- cli/
- core/
```

---

## Testing

### Backend Logger Test

```python
from core.backend_logger import BackendLoggerBridge
from core.logger import APRILLogger
import os

os.makedirs('logs', exist_ok=True)
logger = APRILLogger(name='test', level='INFO', log_file='logs/test.log')
bridge = BackendLoggerBridge(logger)
bridge.log_user_message('Hello')
bridge.log_llm_request('mistral', 3)
print('Backend logger test passed!')
```

### TUI Test

```python
from core.textual_tui import APRILApp

# Create app without agent
app = APRILApp(agent=None)
print('TUI created successfully!')
```

---

## Future Integration

### Qwen3 Coder Integration

Qwen3 Coder will use this architecture to:

1. **Read from AgentRuntime**
   - Access session context
   - Read memory database
   - Monitor tool executions

2. **Write Code to Database**
   - Generate code snippets
   - Store in `data/codes/` directory
   - Version control for code changes

3. **Extract Memories from Code**
   - Learn from successful code examples
   - Store best practices
   - Build code library

4. **Log Code Generation Events**
   ```python
   [CODING] Request: Write Python function
   [CODING] Language: Python
   [CODING] Generated: 42 lines
   [CODING] Stored: data/codes/fn_001.py
   ```

---

## Files Quick Reference

| File | Purpose |
|------|---------|
| `main.py` | Project entry point |
| `core/backend_logger.py` | Backend logger bridge |
| `core/logger.py` | Structured logging system |
| `core/textual_tui.py` | Main TUI application |
| `core/agent.py` | Agent runtime with logging hooks |
| `core/widgets/logs.py` | Real-time log panel |
| `core/widgets/status.py` | Status indicator with session info |
| `core/config.py` | Agent configuration |
| `core/database.py` | Memory database |

---

## Architecture Principles

1. **Separation of Concerns**
   - TUI handles UI only
   - Backend logger handles system events
   - Agent handles LLM and tools

2. **Real-time Updates**
   - Logs appear immediately in TUI
   - Periodic flush ensures no delays
   - Buffered logging for performance

3. **Extensibility**
   - Easy to add new log tags
   - Callback system for custom handlers
   - Plugin-friendly architecture

4. **Backward Compatibility**
   - CLI main.py kept for reference
   - Legacy TUI still available
   - Gradual migration path

---

## Notes

- TUI is now the primary entry point via `python main.py`
- Backend CLI logger runs in the background, capturing all system events
- Log panel in TUI is configurable via `--show-logs` or `APRIL_TUI_SHOW_LOGS` env var
- Backend logs are written to file only (no console output for logs)
- The `cli/main.py` is kept for backward compatibility but marked as deprecated
- `logging.py` renamed to `logger.py` to avoid conflict with Python's stdlib module
