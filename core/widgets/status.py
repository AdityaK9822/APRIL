"""
StatusWidget - Displays agent state (Ready/Thinking/Busy)
"""

from textual.widgets import Static
from textual.reactive import reactive


class StatusWidget(Static):
    """
    Status indicator showing agent state
    
    Features:
    - Three states: Ready, Thinking, Busy
    - Color-coded display
    - Reactive updates
    """
    
    # Reactive status - auto-triggers watch_status on change
    status = reactive("ready")
    
    def __init__(self):
        """Initialize status widget with default 'ready' state"""
        super().__init__()
        self.update_status("ready")
    
    def on_mount(self) -> None:
        """-widget is added to the DOM"""
        self.update_status("ready")
    
    def watch_status(self, old_status: str, new_status: str) -> None:
        """
        Automatically called when status changes
        
        Args:
            old_status: Previous status value
            new_status: New status value
        """
        self.update_status(new_status)
    
    def update_status(self, status: str) -> None:
        """
        Update status display with appropriate styling
        
        Args:
            status: Status string ("ready", "thinking", "busy")
        """
        self.status = status.lower()
        
        if self.status == "ready":
            self.update("[bold green]✓ Ready[/bold green]")
        elif self.status == "thinking":
            self.update("[bold yellow]⏳ Thinking...[/bold yellow]")
        elif self.status == "busy":
            self.update("[bold red]✗ Busy[/bold red]")
        else:
            self.update(f"[dim]{self.status}[/dim]")
    
    def to_ready(self) -> None:
        """Set status to ready"""
        self.update_status("ready")
    
    def to_thinking(self) -> None:
        """Set status to thinking"""
        self.update_status("thinking")
    
    def to_busy(self) -> None:
        """Set status to busy"""
        self.update_status("busy")
    
    def update_session_info(self, session_id: str = None, message_count: int = None) -> None:
        """
        Update status with session information
        
        Args:
            session_id: Current session ID
            message_count: Number of messages in session
        """
        info = []
        if session_id:
            info.append(f"Session: {session_id[:8]}...")
        if message_count is not None:
            info.append(f"Msgs: {message_count}")
        
        if info:
            self.update(f"[bold blue]{' | '.join(info)}[/bold blue]")
