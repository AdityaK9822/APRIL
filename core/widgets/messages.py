"""
MessageList - Displays chat history with auto-scroll and markdown
"""

from textual.widgets import Static
from textual.containers import ScrollableContainer
from datetime import datetime
import re


class MessageList(ScrollableContainer):
    """
    Scrollable container for chat messages
    
    Features:
    - Color-coded by role (user/assistant)
    - Auto-scroll to latest
    - Maximum message limit
    - Timestamp display
    - Basic markdown rendering
    """
    
    MAX_MESSAGES = 1000
    
    def __init__(self, id: str = None):
        super().__init__(id=id)
        self.messages = []
        self._pending_delta: str = ""
    
    def add_message(self, role: str, content: str) -> None:
        """Add message to history."""
        if len(self.messages) >= self.MAX_MESSAGES:
            oldest = self.messages.pop(0)
            oldest.remove()
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Create styled widget based on role
        if role == "user":
            prefix = "[cyan bold]You:[/cyan bold]"
            msg_class = "message-user"
        else:
            prefix = "[green bold]APRIL:[/green bold]"
            msg_class = "message-assistant"
        
        # Render markdown
        rendered = self._render_markdown(content)
        
        # Create message widget
        message_widget = Static(
            f"{prefix} {rendered}",
            classes=f"message {msg_class}",
            id=f"msg-{len(self.messages)}"
        )
        
        # Mount widget to scrollable container
        self.mount(message_widget)
        self.messages.append(message_widget)
        
        # Auto-scroll to bottom
        self.scroll_end(animate=False)
    
    def add_message_delta(self, content: str) -> None:
        """Add delta to current message (streaming)."""
        self._pending_delta += content
        
        # Find the last assistant message
        for msg_widget in reversed(self.messages):
            if 'message-assistant' in msg_widget.classes:
                # Update the content
                timestamp = datetime.now().strftime("%H:%M:%S")
                rendered = self._render_markdown(self._pending_delta)
                msg_widget.update(f"[green bold]APRIL:[/green bold] {rendered}")
                self.scroll_end(animate=False)
                break
    
    def add_system_message(self, content: str) -> None:
        """Add system message with different styling."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        message_widget = Static(
            f"[dim][{timestamp}] {content}[/dim]",
            classes="message system",
            id=f"msg-{len(self.messages)}"
        )
        
        self.mount(message_widget)
        self.messages.append(message_widget)
    
    def clear(self) -> None:
        """Clear all messages."""
        for msg in self.messages:
            msg.remove()
        self.messages.clear()
        self._pending_delta = ""
    
    def count(self) -> int:
        """Return message count."""
        return len(self.messages)
    
    def _render_markdown(self, text: str) -> str:
        """Basic markdown rendering for Textual."""
        # Bold: **text** or __text__
        text = re.sub(r'\*\*(.*?)\*\*', r'[bold]\1[/bold]', text)
        text = re.sub(r'__(.*?)__', r'[bold]\1[/bold]', text)
        
        # Italic: *text* or _text_
        text = re.sub(r'\*(.*?)\*', r'[italic]\1[/italic]', text)
        text = re.sub(r'_(.*?)_', r'[italic]\1[/italic]', text)
        
        # Code: `code` (inline)
        text = re.sub(r'`([^`]+)`', r'[cyan]\1[/cyan]', text)
        
        # Code blocks: ```code```
        text = re.sub(r'```([^\n]*)\n(.*?)```', r'[dim]Code block:[/dim]\n[cyan]\2[/cyan]', text, flags=re.DOTALL)
        
        # Links: [text](url) -> text (url)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'[link]\1[/link] (\2)', text)
        
        # Headers: # Header -> bold header
        text = re.sub(r'^#(.*?)$', r'[bold]\1[/bold]', text, flags=re.MULTILINE)
        
        return text
