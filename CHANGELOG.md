# APRIL TUI Improvements - Changelog

## Version 1.0 - Event Bus & IPC Architecture

### Overview
Major architectural overhaul to fix usability issues with the TUI, including blocking calls, no streaming, tangled code, and single-process limitations.

### New Features

#### Event Bus System
- **core/events.py**: Created `EventBus` class for decoupled agent-UI-logger communication
- Typed events for all agent lifecycle events:
  - `message.delta`: Streaming tokens from model
  - `message.start`, `message.done`: Message boundaries
  - `tool_call.start`, `tool_call.output`, `tool_call.done`: Tool lifecycle
  - `log`: Structured logging events
  - `error`: Error events
  - `status`: Agent state changes
- Thread-safe event distribution with sync and async callback support
- Event history tracking for debugging

#### IPC for Logger Tab
- **core/ipc_server.py**: Created socket server for IPC
  - Unix socket (macOS/Linux) for fast, secure local communication
  - TCP fallback (Windows) for cross-platform support
  - JSON-serialized events over socket
- **core/ipc_logger.py**: Separate logger subprocess
  - Connects to IPC server
  - Color-coded output by log level
  - Automatic redaction of sensitive data (API keys, tokens, secrets)
  - Long output truncation with markers
  - Reconnect support

#### Streaming Support
- `AgentRuntime.run_streaming()`: Async generator that yields tokens
- Token-by-token streaming to TUI via event bus
- Status updates during streaming

#### Enhanced TUI
- **core/textual_tui.py**: Updated with event bus integration
  - Subscribes to event bus for real-time updates
  - Markdown rendering (bold, italic, code, links)
  - Ctrl+C cancels generation
  - Slash commands: `/clear`, `/quit`, `/help`
  - Alt+Enter for multiline input
  - Command history with Up/Down navigation

#### Launcher System
- **launcher.py**: Spawns TUI and logger tabs
  - Platform-specific terminal spawning:
    - macOS: Terminal/iTerm via AppleScript
    - Linux: gnome-terminal/kitty
    - Windows: Windows Terminal
  - Fallback to single-pane mode
  - Signal handling for clean shutdown

### Changes to Existing Files

#### core/agent.py
- Added `EventBus` integration via `get_event_bus()`
- Added `run_streaming()` async generator method
- Events instead of direct logging:
  - `_emit_error()`: Emit error events
  - `_emit_status()`: Emit status events
  - `emit_log()` via event bus
- Thread-safe cancellation support
- Methods unchanged for backward compatibility

#### core/widgets/messages.py
- Added `_render_markdown()`: Basic markdown rendering
- Added `add_message_delta()`: Streaming token updates
- Markdown support for bold, italic, code, links, headers

#### core/__init__.py
- Added exports: `EventBus`, `get_event_bus`, `reset_event_bus`

#### main.py
- Updated to use event bus architecture
- Added launcher argument parsing
- Integration with IPC server
- Graceful shutdown handling

#### requirements.txt
- No new dependencies - all built on stdlib and existing textual

### Configuration

Environment Variables:
- `APRIL_LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR (default: INFO)
- `APRIL_TUI_SHOW_LOGS`: true/false (default: false)
- `APRIL_IPC_SOCKET`: Socket path for logger (auto-generated)

### Command Line Flags

#### Launcher Flags
- `-h, --help`: Show help
- `-s, --single-pane`: Run in single pane (no separate logger)
- `-n, --no-spawn`: Don't spawn terminals, just run
- `--theme`: Color theme (dark/light)

#### TUI Flags
- `-m, --model`: Override model from config
- `--log-level`: Backend logger level
- `--log-file`: Path to backend log file
- `--max-iterations`: Maximum tool call iterations
- `--show-logs`: Show log panel in TUI
- `--no-agent`: Run TUI without agent

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Alt+Enter` | Add newline (multiline) |
| `Ctrl+C` | Cancel current generation |
| `Ctrl+L` | Toggle log panel |
| `Ctrl+S` | Show stats |
| `Ctrl+Q`, `Esc` | Quit |

### Slash Commands

Type `/command` in input:
- `/clear`: Clear conversation
- `/quit`: Exit application
- `/help`: Show help

### Logging Levels

| Level | Color | Description |
|-------|-------|-------------|
| DEBUG | Dim white | Detailed debugging |
| INFO | Cyan | Normal operations |
| WARNING | Yellow | Warnings |
| ERROR | Red | Errors |

### Security

- API keys, tokens, secrets automatically redacted
- Unix socket with 0o600 permissions (user-only)
- TCP binds to 127.0.0.1 only
- No telemetry

### Testing

```bash
# Event system tests
python3 tests/test_events.py -v

# TUI widget tests
python3 test_textual_tui.py

# Integration
python3 main.py --log-level DEBUG
python3 main.py --single-pane --no-agent
```

### Files Created

1. `core/events.py` - Event types and EventBus
2. `core/ipc_server.py` - IPC socket server
3. `core/ipc_logger.py` - Logger subprocess
4. `launcher.py` - Terminal spawning
5. `tests/test_events.py` - Event system tests

### Files Modified

1. `core/agent.py` - Event bus integration, streaming
2. `core/textual_tui.py` - Event bus, markdown, slash commands
3. `core/widgets/messages.py` - Markdown rendering
4. `core/__init__.py` - Export new modules
5. `main.py` - Launcher integration
6. `README.md` - Complete documentation
7. `requirements.txt` - No changes needed

### Breaking Changes

None. Backward compatibility maintained:
- `AgentRuntime.run()` still works
- `APRILApp` still works
- All existing tests pass

### Known Limitations

1. Markdown rendering - Basic support only
2. Long output - Truncated with marker
3. Session persistence - Memory DB only
4. tmux detach detection - Known issue
5. Multi-user - Not supported

### Performance

- Async callbacks run in background tasks
- Sync callbacks are fast (< 1ms)
- Event history limited to 1000 events
- IPC: < 1ms latency on Unix socket

---

**Date**: October 14, 2026  
**Author**: APRIL Development  
**Python Version**: 3.10+

