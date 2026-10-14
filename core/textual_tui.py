"""
APRIL Textual TUI

Modern TUI implementation using the Textual framework.
Provides a responsive, interactive terminal interface.
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label, Static, TextArea
from textual.containers import Container, Vertical, Horizontal
from typing import Optional, List, Dict


class APRILApp(App):
    """
    Textual-based TUI for APRIL agent
    
    Features:
    - Status bar showing agent status
    - Message history with color coding
    - Log panel with filtering
    - Input prompt for commands
    - Memory statistics display
    """
    
    CSS_PATH = "./core/april.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "clear", "Clear"),
        ("s", "toggle_status", "Status"),
        ("l", "toggle_logs", "Toggle Logs"),
    ]
    
    def __init__(self, agent=None, db=None):
        super().__init__()
        self.agent = agent
        self.db = db
        self.show_logs = True
        self.messages: List[Dict] = []
    
    def compose(self) -> ComposeResult:
        """Compose the UI layout"""
        yield Header()
        
        yield Container(
            Vertical(
                Label("Status", id="status-label"),
                Static("Ready", id="status-display"),
                Label("Memory Stats", id="stats-label"),
                Static("", id="stats-display"),
                classes="sidebar",
            ),
            Vertical(
                Label("Messages", id="msg-label"),
                TextArea.read_only(id="messages", theme="monokai"),
                classes="main-content",
            ),
        )
        
        if self.show_logs:
            yield TextArea.read_only(id="logs", theme="monokai")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Setup when app starts"""
        self.update_stats()
        self.log("APRIL TUI started")
    
    def update_stats(self):
        """Update memory statistics"""
        if self.db:
            stats = self.db.get_stats()
            stats_text = (
                f"Memories: {stats.get('total_memories', 0)}\n"
                f"Messages: {stats.get('total_messages', 0)}\n"
                f"Sessions: {stats.get('total_sessions', 0)}"
            )
            self.query_one("#stats-display").update(stats_text)
    
    def update_status(self, status: str):
        """Update agent status"""
        self.query_one("#status-display").update(status)
    
    def add_message(self, role: str, content: str):
        """Add message to history"""
        self.messages.append({'role': role, 'content': content})
        
        text_area = self.query_one("#messages", TextArea)
        prefix = "👤 You: " if role == 'user' else "🤖 APRIL: "
        text_area.insert_text(f"{prefix}{content}\n\n")
        text_area.scroll_end()
    
    def toggle_logs(self):
        """Toggle logs visibility"""
        self.show_logs = not self.show_logs
        self.query_one("#logs").toggle_visible()
    
    def action_toggle_status(self):
        """Toggle status panel"""
        self.query_one(".sidebar").toggle_visible()
    
    def action_clear(self):
        """Clear message history"""
        self.messages.clear()
        text_area = self.query_one("#messages", TextArea)
        text_area.clear()
    
    def action_quit(self):
        """Quit the app"""
        self.exit()
    
    def on_resize(self) -> None:
        """Handle window resize"""
        self.update_layout()


class ConsoleRenderer:
    """
    Simple console renderer fallback
    Uses Rich for formatted output
    """
    
    def __init__(self):
        from rich.console import Console
        self.console = Console()
        self.messages: List[Dict] = []
        self.running = False
    
    def print_header(self):
        """Print header"""
        self.console.print("=" * 60)
        self.console.print("[boldcyan]APRIL[/boldcyan] - An assistant with a body".center(60))
        self.console.print("=" * 60)
        self.console.print()
    
    def print_message(self, role: str, content: str):
        """Print a message"""
        if role == 'user':
            self.console.print(f"\n[bold]You:[/bold]\n  {content}")
        elif role == 'assistant':
            self.console.print(f"\n[bold green]APRIL:[/bold green]\n  {content}")
        else:
            self.console.print(f"\n[{role.upper()}]:\n  {content}")
    
    def start(self):
        """Start the renderer"""
        self.running = True
        self.print_header()
    
    def stop(self):
        """Stop the renderer"""
        self.running = False
        self.console.print("\n[bold]APRIL TUI stopped. Goodbye![/bold]")
