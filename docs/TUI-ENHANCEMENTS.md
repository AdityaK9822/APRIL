# TUI Enhancements v1

## Overview

Real-time backend logging integration with the TUI log panel.

## What Was Added

### 1. Enhanced LogPanel (`core/widgets/logs.py`)

**Features:**
- Real-time log buffering system
- Auto-flush every 500ms
- Callback support for real-time updates
- Configurable by log level

**Key Methods:**
```python
add_log(message, level="INFO", real_time=False)
flush()  # Force flush buffered logs
set_callback(callback)  # Register real-time callback
get_buffer_size()  # Check current buffer size
set_level(level)  # Change log level filter
```

### 2. Enhanced BackendLoggerBridge (`core/backend_logger.py`)

**Features:**
- Real-time callback support
- Thread-safe log broadcasting
- Structured event tags: `[MEMORY]`, `[TOOL]`, `[LLM]`, `[SESSION]`, `[USER]`, `[AGENT]`, `[ERROR]`

**Key Methods:**
```python
log_user_message(message)
log_agent_response(response)
log_memory_event(event_type, details, real_time=False)
log_tool_execution(tool_name, args, result, real_time=False)
log_llm_request(model, message_count, real_time=False)
log_llm_response(model, real_time=False)
set_real_time_callback(callback)  # Register TUI callback
```

### 3. Updated APRILApp (`core/textual_tui.py`)

**Features:**
- Automatic backend logger integration on mount
- Periodic log flush timer (500ms)
- Real-time callback setup

**New Methods:**
```python
_on_backend_log(message, level)  # Callback for backend logs
_start_log_flush_timer()  # Start periodic flush
```

## Architecture Flow

```
Agent Runtime
    ↓ (calls backend_logger.log_*)
BackendLoggerBridge
    ↓ (real-time callback)
LogPanel.add_log() → Buffer (50 items)
    ↓ (500ms timer)
LogPanel.flush() → Display
```

## Event Flow Example

```
User types: "List files"
    ↓
TUI: agent.run()
    ↓
BackendLogger.log_user_message("List files")
    ↓
LogPanel.add_log("[USER] List files", "INFO", real_time=True)
    ↓
Buffer: 1 item
    ↓ (0.5 sec)
LogPanel.flush()
    ↓
Display: [12:34:56] [USER] List files
    ↓
[LLM] Request to mistral (3 messages)
    ↓
[TOOL] Calling: shell
    ↓
[TOOL] Result: total 48 drwx...
    ↓
[LLM] Response from mistral
    ↓
[AGENT] The directory contains...
```

## Log Panel Display

```
┌─────────────────────────────────────┐
│ [12:34:56] [USER] List files        │
│ [12:34:56] [LLM] Request...         │
│ [12:34:56] [TOOL] Calling: shell    │
│ [12:34:56] [TOOL] Result: ...       │
│ [12:34:57] [LLM] Response...        │
│ [12:34:57] [AGENT] The directory... │
└─────────────────────────────────────┘
```

## Usage

### Starting the TUI

```bash
python main.py
```

### View Backend Logs

```bash
python main.py --log-level DEBUG --show-logs
```

### Check Buffer Status

```bash
# Add this to your code for debugging:
print(f"Buffer size: {log_panel.get_buffer_size()}")
```

## Event Tags Reference

| Tag | Description |
|-----|-------------|
| `[USER]` | User input messages |
| `[AGENT]` | Agent responses |
| `[LLM]` | LLM API requests/responses |
| `[TOOL]` | Tool executions |
| `[MEMORY]` | Memory extraction/updates |
| `[SESSION]` | Session lifecycle events |
| `[ERROR]` | Error events |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APRIL_LOG_LEVEL` | `WARNING` | Backend log level |
| `APRIL_TUI_SHOW_LOGS` | `false` | Show log panel in TUI |

### Command Line

```bash
python main.py --log-level DEBUG
python main.py --show-logs
python main.py --max-iterations 200
```

## Performance

- Buffer size: 50 logs (auto-flush)
- Flush interval: 500ms
- Max display logs: 100
- Thread-safe: Yes (uses locks)

## Future Enhancements

- [ ] Log search/filter in TUI
- [ ] Export logs to file
- [ ] Log panel toggle keybinding
- [ ] Log level selector widget
- [ ] Real-time stats overlay
