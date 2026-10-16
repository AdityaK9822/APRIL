# APRIL Textual TUI

A modern, feature-rich terminal user interface for APRIL built with [Textual](https://textual.textualize.io/).

## Features

- **Modern Interface**: Built with Textual for a responsive, event-driven UI
- **Real-time Status**: Agent state indicator (Ready/Thinking/Busy)
- **Chat History**: Auto-scrolling message list with role-based coloring
- **Command History**: Input field with Up/Down arrow navigation
- **Log Panel**: Configurable log level filtering with color coding
- **Memory Statistics**: Live stats from the database
- **Keyboard Shortcuts**: Fast keyboard navigation
- **Thread-Safe Agent**: Non-blocking agent calls via asyncio

## Installation

Textual is included in the requirements:

```bash
pip install textual>=1.0.0,<2.0.0
```

## Usage

### Running without Agent

```bash
python3 -m core.textual_tui
```

### Running with Agent

```bash
python3 -m core.textual_tui --agent
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APRIL_LOG_LEVEL` | `WARNING` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `APRIL_TUI_SHOW_LOGS` | `false` | Show log panel on startup |

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Up` | Previous command in history |
| `Down` | Next command in history |
| `Ctrl+L` | Toggle log panel visibility |
| `Ctrl+S` | Refresh statistics panel |
| `Ctrl+C` | Clear input field |
| `Ctrl+Q` | Quit application |

## Architecture

### Widget Structure

```
APRILApp (Textual App)
├── Header (App title)
├── StatusWidget (Agent state)
├── MessageList (Chat history)
├── StatsWidget (Memory stats)
├── LogPanel (Log display)
├── Footer (Key bindings)
└── InputWidget (User input)
```

### Integration

The Textual TUI integrates with the existing `AgentRuntime` using `asyncio.to_thread()` to run synchronous operations without blocking the UI:

```python
# In _process_message()
response = await asyncio.to_thread(
    self.agent.run,
    message
)
```

## Development

### Running Tests

```bash
python3 test_textual_tui.py
```

### Widget Implementation

Each widget is in `core/widgets/`:
- `status.py` - StatusWidget
- `messages.py` - MessageList
- `input.py` - InputWidget
- `logs.py` - LogPanel
- `stats.py` - StatsWidget

### Styling

Edit `core/april.tcss` to customize:
- Colors (Hex: `#RRGGBB` or named colors)
- Border styles
- Layout dimensions
- Widget visibility

## Differences from Curses TUI

| Feature | Curses | Textual |
|---------|--------|---------|
| Framework | `curses` module | Textual |
| Async | Manual | Native |
| Web Deploy | No | Yes (`textual-serve`) |
| Widget System | Manual drawing | Component-based |
| Styling | Hardcoded | CSS-like (TCSS) |
| Event Loop | Polling | Event-driven |

## Future Enhancements

- [ ] Web dashboard via `textual-serve`
- [ ] Markdown rendering
- [ ] Syntax highlighting
- [ ] Image support (Sixel)
- [ ] tmux session awareness
- [ ] Split panes
- [ ] Multi-agent support

## License

Same as APRIL core.
