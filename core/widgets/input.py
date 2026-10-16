"""
InputWidget - User input with command history
"""

from textual.widgets import Input
from typing import Optional


class InputWidget(Input):
    """
    User input field with command history support
    
    Features:
    - Up/Down arrow navigation through history
    - Configurable history size
    - Placeholder text
    """
    
    def on_key(self, event) -> None:
        """Handle key events for history navigation"""
        if self.has_focus:
            self._handle_key_navigation(event)
    
    def _handle_key_navigation(self, event) -> None:
        """Handle Up/Down arrow keys for history navigation"""
        if event.key == "up":
            self._navigate_history(-1)
        elif event.key == "down":
            self._navigate_history(1)
    
    def _navigate_history(self, direction: int) -> None:
        """
        Navigate through command history
        
        Args:
            direction: -1 for previous, 1 for next
        """
        if not self.history:
            return
        
        if direction < 0:
            # Navigate backward in history
            if self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.value = self.history[-(self.history_index + 1)]
        else:
            # Navigate forward in history
            if self.history_index > 0:
                self.history_index -= 1
                self.value = self.history[-(self.history_index + 1)]
            else:
                self.history_index = -1
                self.value = ""
    
    def add_to_history(self, message: str) -> None:
        """
        Add message to command history
        
        Args:
            message: Message to add to history
        """
        # Don't add empty messages or duplicates of last item
        if not message.strip():
            return
        
        if self.history and self.history[-1] == message:
            return
        
        self.history.append(message)
        self.history_index = -1
        
        # Trim old history
        if len(self.history) > self.history_size:
            self.history = self.history[-self.history_size:]
    
    def clear_history(self) -> None:
        """Clear command history"""
        self.history.clear()
        self.history_index = -1
