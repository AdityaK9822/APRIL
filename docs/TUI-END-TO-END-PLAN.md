# APRIL Textual TUI - End-to-End Implementation Plan

## Branch: `feature/textual-tui`
## Date: October 14, 2026
## Status: Ready for Implementation

---

## Executive Summary

This plan details the complete replacement of APRIL's current curses-based TUI with **Textual** - a modern Python TUI framework. The implementation will be done in phases, ensuring backward compatibility with the existing curses TUI.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Technology Stack](#technology-stack)
3. [Implementation Phases](#implementation-phases)
4. [File Structure](#file-structure)
5. [Component Design](#component-design)
6. [Integration Points](#integration-points)
7. [Testing Strategy](#testing-strategy)
8. [Migration Path](#migration-path)
9. [Success Metrics](#success-metrics)
10. [Timeline](#timeline)
11. [Risk Mitigation](#risk-mitigation)

---

## 1. Architecture Overview

### Current State (curses)
```
User Input → APRIL_TUI (curses)
                   ↓
              AgentRuntime
                   ↓
         ConsoleRenderer (fallback)
```

### Future State (Textual)
```
User Input → APRILApp (Textual)
                   ↓
              AgentRuntime
                   ↓
         ┌──────────────────────┐
         │  Widget System       │
         │  - StatusWidget      │
         │  - MessageList       │
         │  - LogPanel          │
         │  - InputWidget       │
         │  - StatsWidget       │
         └──────────────────────┘
                   ↓
         textual-serve (web deploy)
```

### Why Textual?

| Feature | curses | Textual | Benefit |
|---------|--------|---------|---------|
| Async Support | Manual | Native | Agent loop integration |
| Web Deployment | No | Yes | Remote monitoring |
| Modern Widgets | Manual | Built-in | Faster development |
| Styling | Manual code | CSS-like | Maintainable |
| Event Handling | Polling | Event-driven | Responsive |
| Community | Declining | Active | Long-term support |
| Performance | Good | 60 FPS | Modern hardware |

---

## 2. Technology Stack

### Dependencies
```
textual>=1.0           # Core TUI framework
rich>=13.0             # Textual's rendering backend (already installed)
```

### File Structure
```
Open_INT/
├── core/
│   ├── textual_tui.py         # NEW: Textual implementation
│   ├── april.tcss             # NEW: Textual CSS
│   ├── tui.py                 # EXISTING: curses (keep for compatibility)
│   ├── agent.py               # EXISTING: No changes needed
│   ├── logging.py             # EXISTING: Already integrated
│   └── ...
├── tests/
│   ├── test_tui_textual.py    # NEW: Textual tests
│   └── test_memory.py         # EXISTING: Should still pass
├── docs/
│   └── TUI-END-TO-END-PLAN.md # NEW: This document
└── requirements.txt           # MODIFY: Add textual>=1.0
```

---

## 3. Implementation Phases

### Phase 1: Foundation (Days 1-2)
**Goal**: Basic Textual app running

#### Tasks
- [ ] Install Textual: `pip install textual`
- [ ] Create `core/textual_tui.py` with minimal `APRILApp`
- [ ] Create `core/april.tcss` with basic styling
- [ ] Test: App launches and displays header/footer

#### Deliverables
```python
# core/textual_tui.py (minimal)
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer

class APRILApp(App):
    CSS_PATH = "./core/april.tcss"
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
```

#### Success Criteria
- App runs without errors
- Header displays "APRIL"
- Footer shows default keybindings

---

### Phase 2: Core Widgets (Days 3-4)
**Goal**: Implement all required widgets

#### Widget Catalog

| Widget | Purpose | Key Features |
|--------|---------|--------------|
| **Header** | App title | Dynamic status indicator |
| **StatusWidget** | Agent status | Ready/Thinking/Busy states |
| **MessageList** | Chat history | Auto-scroll, color-coded roles |
| **LogPanel** | Logs | Filter by log level |
| **StatsWidget** | Memory stats | Live updates |
| **InputWidget** | User input | Command history, autocomplete |
| **Footer** | Keybindings | Dynamic shortcuts |

#### Implementation

```python
# StatusWidget
class StatusWidget(Static):
    def update_status(self, status: str):
        if status == "ready":
            self.update("[green]Ready[/green]")
        elif status == "thinking":
            self.update("[yellow]Thinking...[/yellow]")
        elif status == "busy":
            self.update("[red]Busy[/red]")

# MessageList
class MessageList(Static):
    def add_message(self, role: str, content: str):
        if role == "user":
            prefix = "[cyan]You:[/cyan]"
        else:
            prefix = "[green]APRIL:[/green]"
        self.update(f"{prefix} {content}")

# LogPanel
class LogPanel(Static):
    def __init__(self, log_level: str = "WARNING"):
        self.log_level = log_level
        self.logs = []
    
    def add_log(self, message: str, level: str = "INFO"):
        if self._should_show(level):
            self.logs.append(f"[{level}] {message}")
            self.update("\n".join(self.logs[-50:]))
```

#### Success Criteria
- All widgets render correctly
- Dynamic updates work
- Layout is responsive

---

### Phase 3: Agent Integration (Days 5-6)
**Goal**: Connect TUI to AgentRuntime

#### Integration Points

```python
class APRILApp(App):
    def __init__(self, agent=None, db=None):
        self.agent = agent
        self.db = db
        super().__init__()
    
    async def on_agent_thinking(self):
        """Called when agent starts processing"""
        self.query_one(StatusWidget).update_status("thinking")
    
    async def on_agent_response(self, response: str):
        """Called when agent responds"""
        self.query_one(MessageList).add_message("assistant", response)
        self.query_one(StatusWidget).update_status("ready")
    
    async def on_memory_update(self, stats: dict):
        """Called when memory stats change"""
        self.query_one(StatsWidget).update(stats)
    
    async def on_tool_execution(self, tool_name: str):
        """Called when tool is executed"""
        self.query_one(LogPanel).add_log(f"Executing: {tool_name}")
```

#### Message Handling

```python
class APRILApp(App):
    BINDINGS = [
        ("enter", "send_message", "Send"),
        ("ctrl+l", "toggle_logs", "Logs"),
        ("ctrl+s", "show_stats", "Stats"),
        ("ctrl+q", "quit", "Quit"),
    ]
    
    def action_send_message(self):
        """Handle user input"""
        input_widget = self.query_one("#user-input")
        message = input_widget.value
        
        if message.strip():
            # Clear input
            input_widget.value = ""
            
            # Add to message list
            self.query_one(MessageList).add_message("user", message)
            
            # Send to agent
            asyncio.create_task(self._process_message(message))
    
    async def _process_message(self, message: str):
        """Process message through agent"""
        if self.agent:
            self.query_one(StatusWidget).update_status("thinking")
            response = await asyncio.to_thread(self.agent.run, message)
            self.query_one(MessageList).add_message("assistant", response)
            self.query_one(StatusWidget).update_status("ready")
```

#### Success Criteria
- Agent messages flow through TUI
- Status updates correctly
- No blocking on agent calls

---

### Phase 4: Styling & Polish (Days 7-8)
**Goal**: Beautiful, consistent UI

#### TCSS Implementation

```css
/* core/april.tcss */

/* Global */
Screen {
    background: $surface;
    color: $text;
}

/* Layout */
Container {
    layout: grid;
    grid-size: 100%;
}

/* Header */
Header {
    dock: top;
    height: 3;
    background: $primary;
    color: $text;
    padding: 1;
}

/* Status */
StatusWidget {
    min-height: 3;
    background: $panel;
    border: solid $success;
    padding: 1;
}

/* Messages */
#message-list {
    height: 100%;
    background: $panel;
    border: solid $primary;
    overflow-y: auto;
    padding: 1;
}

.message-user {
    color: $cyan;
    text-style: bold;
}

.message-assistant {
    color: $green;
    text-style: bold;
}

/* Logs */
#log-panel {
    height: 8;
    background: $panel;
    border: solid $warning;
    padding: 1;
    display: none;
}

.log-info {
    color: $text-muted;
}

.log-warning {
    color: $warning;
}

.log-error {
    color: $error;
    text-style: bold;
}

/* Input */
#user-input {
    dock: bottom;
    height: 3;
    background: $surface;
    border: solid $primary;
    padding: 1;
}

#user-input:focus {
    border: solid $success;
}

/* Stats */
#stats-panel {
    width: 25%;
    background: $panel;
    border: solid $secondary;
    padding: 1;
}

.stat-label {
    text-style: bold;
    color: $primary;
}

.stat-value {
    color: $text;
}
```

#### Color Scheme
```python
# Match existing curses colors
COLORS = {
    'primary': 'blue',
    'secondary': 'cyan',
    'success': 'green',
    'warning': 'yellow',
    'error': 'red',
    'text': 'white',
    'text-muted': 'gray',
    'surface': 'black',
    'panel': '#1a1a1a',
}
```

#### Success Criteria
- Colors match existing TUI
- Layout is responsive (test with resize)
- Text is readable

---

### Phase 5: Testing (Days 9-10)
**Goal**: Comprehensive test coverage

#### Test Categories

##### Unit Tests (Widget Behavior)
```python
# tests/test_tui_textual.py

class TestStatusWidget(unittest.TestCase):
    def test_update_ready(self):
        widget = StatusWidget()
        widget.update_status("ready")
        self.assertIn("Ready", str(widget))
    
    def test_update_thinking(self):
        widget = StatusWidget()
        widget.update_status("thinking")
        self.assertIn("Thinking", str(widget))
    
    def test_update_busy(self):
        widget = StatusWidget()
        widget.update_status("busy")
        self.assertIn("Busy", str(widget))

class TestMessageList(unittest.TestCase):
    def test_add_user_message(self):
        widget = MessageList()
        widget.add_message("user", "Hello")
        self.assertIn("You", str(widget))
    
    def test_add_assistant_message(self):
        widget = MessageList()
        widget.add_message("assistant", "Hi there")
        self.assertIn("APRIL", str(widget))
    
    def test_auto_scroll(self):
        widget = MessageList()
        for i in range(100):
            widget.add_message("user", f"Message {i}")
        # Should keep last 50

class TestLogPanel(unittest.TestCase):
    def test_filter_by_level(self):
        panel = LogPanel(log_level="WARNING")
        panel.add_log("Debug msg", "DEBUG")  # Should not show
        panel.add_log("Warning msg", "WARNING")  # Should show
        self.assertIn("Warning", str(panel))
        self.assertNotIn("Debug", str(panel))
```

##### Integration Tests (Agent + TUI)
```python
class TestAPRILAppIntegration(unittest.TestCase):
    def test_app_initialization(self):
        config = AgentConfig.from_env()
        agent = AgentRuntime(config)
        app = APRILApp(agent=agent, db=agent.db)
        self.assertIsNotNone(app.agent)
    
    def test_message_flow(self):
        app = APRILApp()
        app.action_send_message = Mock()
        
        # Simulate user input
        input_widget = app.query_one("#user-input")
        input_widget.value = "Hello"
        
        # Trigger send
        app.action_send_message()
        
        # Verify message added
        messages = app.query_one(MessageList)
        self.assertIn("Hello", str(messages))
```

##### E2E Tests (Full Flow)
```python
class TestEndToEnd(unittest.TestCase):
    def test_full_conversation(self):
        """Test complete conversation flow"""
        config = AgentConfig.from_env()
        agent = AgentRuntime(config)
        app = APRILApp(agent=agent, db=agent.db)
        
        # Start app in thread
        import threading
        thread = threading.Thread(target=app.run)
        thread.start()
        
        # Simulate user input
        time.sleep(1)
        app.query_one("#user-input").value = "What's the date?"
        
        # Check response appears
        time.sleep(5)
        messages = app.query_one(MessageList)
        self.assertTrue(len(messages.renderables) > 0)
        
        # Cleanup
        app.exit()
        thread.join()
```

#### Test Commands
```bash
# Run Textual tests only
python3 -m unittest tests.test_tui_textual -v

# Run all tests
python3 -m unittest discover tests -v

# Run with coverage
coverage run -m unittest discover tests
coverage report
```

#### Success Criteria
- All 10+ Textual tests pass
- All 12 existing memory tests still pass
- Coverage > 80%

---

### Phase 6: Documentation (Day 11)
**Goal**: Complete documentation

#### Documentation Files

##### 1. User Guide
```markdown
# docs/TUI-USER-GUIDE.md

## Installation
pip install textual

## Usage

### Basic Usage
python3 -m core.textual_tui

### With Agent
python3 -m core.textual_tui --agent

### Debug Mode
APRIL_LOG_LEVEL=DEBUG python3 -m core.textual_tui

## Keyboard Shortcuts
- `Enter`: Send message
- `Ctrl+L`: Toggle logs
- `Ctrl+S`: Show stats
- `Ctrl+Q`: Quit
- `Up/Down`: Command history

## Features
- Real-time status updates
- Color-coded messages
- Log filtering
- Memory statistics
```

##### 2. Developer Guide
```markdown
# docs/TUI-DEVELOPER-GUIDE.md

## Architecture

### Widget Overview
- StatusWidget: Displays agent status
- MessageList: Chat history
- LogPanel: Filtered log display
- StatsWidget: Memory statistics
- InputWidget: User input

### Event Flow
User Input → InputWidget → APRILApp → AgentRuntime → Response → MessageList

### Styling
Edit `core/april.tcss` to customize colors and layout.

## Extending

### Adding a New Widget
1. Create widget class (extend Static or Widget)
2. Add to APRILApp.compose()
3. Update TCSS
4. Add tests

### Example:
class MyWidget(Static):
    def on_mount(self):
        self.update("Hello")
```

##### 3. Migration Guide
```markdown
# docs/TUI-MIGRATION-GUIDE.md

## For Users

### What Changed
- Old: `core.tui.APRIL_TUI` (curses)
- New: `core.textual_tui.APRILApp` (Textual)

### Environment Variables
No changes required. Both use same env vars:
- APRIL_LOG_LEVEL
- APRIL_TUI_ENABLED

### Compatibility
Both TUIs can coexist:
- Default: curses
- Textual: Set APRIL_TUI_TYPE=textual

## For Developers

### Code Differences
| curses | Textual |
|--------|---------|
| `_draw_*` methods | Widget composition |
| Manual key handling | Event handlers |
| `curses.wrapper()` | `app.run()` |

### Import Changes
```python
# Old
from core import APRIL_TUI

# New
from core import APRILApp
```
```

---

### Phase 7: Deployment (Day 12)
**Goal**: Production-ready

#### Pre-deployment Checklist
- [ ] All tests pass
- [ ] Documentation complete
- [ ] Performance benchmarks met
- [ ] Memory leaks checked
- [ ] Error handling tested
- [ ] Keyboard shortcuts documented
- [ ] Web deployment tested (textual-serve)

#### Deployment Steps
```bash
# 1. Update dependencies
pip install textual>=1.0

# 2. Run tests
python3 -m unittest discover tests -v

# 3. Local test
python3 -m core.textual_tui --agent

# 4. Web test (optional)
pip install textual-serve
textual serve core.textual_tui:APRILApp

# 5. Production deploy
# No changes needed - it's just Python
```

#### Web Deployment
```bash
# Install textual-serve
pip install textual-serve

# Serve APRIL over web
textual serve core.textual_tui:APRILApp --port 8000

# Access at http://localhost:8000
```

---

## 4. Component Design

### Detailed Widget Specifications

#### StatusWidget
```python
class StatusWidget(Static):
    """Status indicator showing agent state"""
    
    def __init__(self):
        super().__init__("")
        self.status = "ready"
    
    def update_status(self, status: str):
        """Update status display"""
        self.status = status
        if status == "ready":
            self.update("[bold green]Ready[/bold green]")
        elif status == "thinking":
            self.update("[bold yellow]Thinking...[/bold yellow]")
        elif status == "busy":
            self.update("[bold red]Busy[/bold red]")
    
    def on_click(self):
        """Toggle detailed status on click"""
        # Show/hide panel with detailed stats
        pass
```

#### MessageList
```python
class MessageList(ScrollableContainer):
    """Scrollable message history"""
    
    def __init__(self):
        super().__init__()
        self.messages = []
        self.max_messages = 1000
    
    def add_message(self, role: str, content: str):
        """Add message to history"""
        if len(self.messages) >= self.max_messages:
            self.messages.pop(0)
        
        self.messages.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now()
        })
        
        # Render
        if role == 'user':
            prefix = "[cyan bold]You:[/cyan bold]"
        else:
            prefix = "[green bold]APRIL:[/green bold]"
        
        message_widget = Static(f"{prefix} {content}")
        self.mount(message_widget)
        
        # Auto-scroll to bottom
        self.scroll_end(animate=False)
```

#### LogPanel
```python
class LogPanel(Static):
    """Filtered log display"""
    
    LEVELS = {
        'DEBUG': 10,
        'INFO': 20,
        'WARNING': 30,
        'ERROR': 40,
        'CRITICAL': 50
    }
    
    def __init__(self, log_level: str = "WARNING"):
        super().__init__("")
        self.log_level = self.LEVELS.get(log_level, 30)
        self.logs = []
        self.max_logs = 100
    
    def add_log(self, message: str, level: str = "INFO"):
        """Add log entry"""
        level_num = self.LEVELS.get(level, 20)
        
        if level_num >= self.log_level:
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Color by level
            if level == "ERROR":
                formatted = f"[red][{timestamp}] {level}: {message}[/red]"
            elif level == "WARNING":
                formatted = f"[yellow][{timestamp}] {level}: {message}[/yellow]"
            else:
                formatted = f"[dim][{timestamp}] {level}: {message}[/dim]"
            
            self.logs.append(formatted)
            
            # Trim old logs
            if len(self.logs) > self.max_logs:
                self.logs = self.logs[-self.max_logs:]
            
            # Update display
            self.update("\n".join(self.logs))
    
    def set_level(self, level: str):
        """Change log level filter"""
        self.log_level = self.LEVELS.get(level, 30)
        self.update("\n".join(self.logs))
```

#### StatsWidget
```python
class StatsWidget(Static):
    """Memory statistics display"""
    
    def __init__(self, db=None):
        super().__init__("")
        self.db = db
    
    def on_mount(self):
        """Start periodic updates"""
        self.update_stats()
        self.set_interval(5.0, self.update_stats)
    
    def update_stats(self):
        """Refresh statistics"""
        if self.db:
            stats = self.db.get_stats()
            
            text = (
                f"[bold]Memory Statistics[/bold]\n\n"
                f"Total Memories: [cyan]{stats.get('total_memories', 0)}[/cyan]\n"
                f"Total Messages: [cyan]{stats.get('total_messages', 0)}[/cyan]\n"
                f"Sessions: [cyan]{stats.get('total_sessions', 0)}[/cyan]\n"
                f"Unprocessed: [yellow]{stats.get('unprocessed_messages', 0)}[/yellow]\n"
            )
            
            if stats.get('memory_by_type'):
                text += "\n[bold]By Type:[/bold]\n"
                for mem_type, count in stats['memory_by_type'].items():
                    text += f"  {mem_type}: {count}\n"
            
            self.update(text)
```

#### InputWidget
```python
class InputWidget(Input):
    """User input with history"""
    
    def __init__(self):
        super().__init__(placeholder="Type your message...", id="user-input")
        self.history = []
        self.history_index = -1
    
    def on_key(self, event: Key):
        """Handle special keys"""
        if event.key == "up":
            # Navigate history backward
            if self.history and self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.value = self.history[-(self.history_index + 1)]
        elif event.key == "down":
            # Navigate history forward
            if self.history_index > 0:
                self.history_index -= 1
                self.value = self.history[-(self.history_index + 1)]
            else:
                self.history_index = -1
                self.value = ""
    
    def add_to_history(self, message: str):
        """Add to command history"""
        self.history.append(message)
        self.history_index = -1
        
        # Keep last 100
        if len(self.history) > 100:
            self.history = self.history[-100:]
```

---

## 5. Integration Points

### Agent Runtime Integration

```python
class APRILApp(App):
    """Main Textual application for APRIL"""
    
    def __init__(self, agent=None, db=None):
        super().__init__()
        self.agent = agent
        self.db = db
    
    async def process_user_message(self, message: str):
        """Process message through agent"""
        if self.agent:
            # Update status
            self.query_one(StatusWidget).update_status("thinking")
            
            # Run agent in thread pool (non-blocking)
            response = await asyncio.to_thread(
                self.agent.run,
                message
            )
            
            # Add response
            self.query_one(MessageList).add_message("assistant", response)
            
            # Update status
            self.query_one(StatusWidget).update_status("ready")
            
            # Update stats
            if self.db:
                stats = self.db.get_stats()
                self.query_one(StatsWidget).update(stats)
```

### Logging Integration

```python
from core.logging import get_logger

class LogBridge:
    """Bridge from core.logging to LogPanel"""
    
    def __init__(self, app):
        self.app = app
    
    def emit(self, record):
        """Emit log to LogPanel"""
        level = record.levelname
        message = record.getMessage()
        
        # Update LogPanel
        log_panel = self.app.query_one(LogPanel)
        log_panel.add_log(message, level)

# In APRILApp
def on_mount(self):
    logger = get_logger()
    logger.addHandler(LogBridge(self))
```

### Configuration Integration

```python
class APRILApp(App):
    def on_mount(self):
        """Load configuration"""
        import os
        
        # Log level
        log_level = os.getenv('APRIL_LOG_LEVEL', 'WARNING')
        self.query_one(LogPanel).set_level(log_level)
        
        # Show logs
        show_logs = os.getenv('APRIL_TUI_SHOW_LOGS', 'false').lower() == 'true'
        if not show_logs:
            self.query_one(LogPanel).display = False
```

---

## 6. Testing Strategy

### Test Pyramid

```
        E2E Tests (10%)
       ↑
      Integration Tests (30%)
     ↑
    Unit Tests (60%)
```

### Test Coverage Goals

| Component | Target | Current |
|-----------|--------|---------|
| Widgets | 90% | 0% |
| Integration | 80% | 0% |
| E2E | 70% | 0% |
| **Overall** | **80%** | **0%** |

### Test Commands

```bash
# Unit tests only
python3 -m unittest tests.test_tui_textual -v

# Integration tests
python3 -m unittest tests.test_tui_integration -v

# All tests
python3 -m unittest discover tests -v

# With coverage
coverage run -m unittest discover tests
coverage report --include="core/*"
coverage html

# Performance test
python3 -m pytest tests/test_tui_performance.py --benchmark
```

---

## 7. Success Metrics

### Quantitative Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Test Coverage | > 80% | `coverage report` |
| Startup Time | < 500ms | `time python3 -m core.textual_tui` |
| Response Latency | < 100ms | Internal timing |
| Memory Usage | < 50MB | `ps aux | grep april` |
| FPS | 60 FPS | Textual diagnostics |
| Package Size | < 5MB | `du -sh` |

### Qualitative Metrics

- [ ] UI is responsive and smooth
- [ ] Colors are readable and consistent
- [ ] Keyboard shortcuts work as expected
- [ ] Error states are handled gracefully
- [ ] Documentation is clear and complete
- [ ] Code is maintainable and well-documented

---

## 8. Timeline

### Detailed Schedule

| Day | Phase | Tasks | Hours |
|-----|-------|-------|-------|
| 1 | Foundation | Install, create basic app | 4 |
| 2 | Foundation | Basic widgets, layout | 6 |
| 3 | Widgets | StatusWidget, MessageList | 6 |
| 4 | Widgets | LogPanel, StatsWidget | 6 |
| 5 | Integration | Agent integration | 6 |
| 6 | Integration | Event handling, async | 6 |
| 7 | Styling | TCSS, color scheme | 4 |
| 8 | Styling | Responsive layout | 4 |
| 9 | Testing | Unit tests | 6 |
| 10 | Testing | Integration tests | 6 |
| 11 | Documentation | User/developer guides | 4 |
| 12 | Deployment | Final checks, release | 2 |
| **Total** | | | **60 hours** |

### Milestones

1. **Day 2**: App runs with basic widgets
2. **Day 4**: All widgets implemented
3. **Day 6**: Agent integration complete
4. **Day 8**: Styling polished
5. **Day 10**: Tests passing
6. **Day 12**: Production ready

---

## 9. Risk Mitigation

### Identified Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Textual breaking changes | Low | High | Pin version, monitor releases |
| Performance regression | Medium | Medium | Benchmark early, optimize |
| Async complexity | Medium | High | Use thread pools, test thoroughly |
| Color consistency | Low | Low | Test across terminals |
| Memory leaks | Low | High | Profile with tracemalloc |

### Rollback Plan

```bash
# If issues arise, rollback to curses
git checkout main
python3 -m core.tui  # Use old curses TUI
```

### Fallback Strategy

- Keep `core/tui.py` (curses) unchanged
- Both TUIs can coexist
- User can choose: `--tui=curses` or `--tui=textual`

---

## 10. Post-Implementation

### Future Enhancements

1. **Web Dashboard**
   - Deploy via `textual-serve`
   - Share APRIL session over HTTP
   - Remote monitoring

2. **Advanced Features**
   - Splittable panes
   - Markdown rendering
   - Syntax highlighting
   - Image support (Sixel)

3. **Integrations**
   - tmux session awareness
   - MCP connection status
   - Multi-agent support

### Maintenance Plan

- Monitor Textual releases (monthly)
- Update dependencies (quarterly)
- Performance audit (quarterly)
- Security scan (automated)

---

## Appendix A: Error Handling

```python
class APRILApp(App):
    def on_exception(self, error: Exception):
        """Handle uncaught exceptions"""
        log_panel = self.query_one(LogPanel)
        log_panel.add_log(f"Error: {error}", "ERROR")
        
        # Show toast notification
        self.notify(
            f"An error occurred: {error}",
            title="Error",
            severity="error"
        )
```

---

## Appendix B: Configuration Options

```bash
# Environment Variables
APRIL_TUI_TYPE=textual          # or curses
APRIL_TUI_SHOW_LOGS=true        # Show log panel
APRIL_LOG_LEVEL=DEBUG           # Log level
APRIL_LOG_FILE=april.log        # Log file path
APRIL_TUI_COLOR_SCHEME=dark     # dark or light
APRIL_TUI_THEME=default         # TCSS theme
```

---

## Appendix C: Troubleshooting

### Common Issues

#### Issue: App won't start
```bash
# Check dependencies
pip list | grep textual

# Reinstall
pip install --upgrade textual
```

#### Issue: Colors not showing
```bash
# Check terminal support
echo $TERM

# Force color
export COLORTERM=truecolor
```

#### Issue: Layout broken
```bash
# Check terminal size
tput lines cols

# Reset TCSS
rm -rf ~/.cache/textual
```

---

## Appendix D: Performance Optimization

### Tips

1. **Lazy Loading**: Don't load all messages at once
2. **Virtual Scrolling**: Render only visible items
3. **Debouncing**: Batch rapid updates
4. **Thread Pools**: Use for agent calls

```python
# Virtual scrolling
class MessageList(ScrollableContainer):
    def on_scroll_region_changed(self):
        # Only render visible messages
        visible_start = self.scroll_y
        visible_end = visible_start + self.size.height
        # ...
```

---

## Sign-Off

- **Author**: APRIL Development Team
- **Date**: October 14, 2026
- **Status**: Ready for Implementation
- **Branch**: feature/textual-tui
- **Next Action**: Begin Phase 1 (Foundation)

---

**End of Plan**
