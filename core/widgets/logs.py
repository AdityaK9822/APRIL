"""
LogPanel - Filtered log display with real-time support

Features:
- Log level filtering (DEBUG, INFO, WARNING, ERROR)
- Color-coded by level
- Timestamp display
- Maximum log limit
- Real-time integration with backend logger
"""

from textual.widgets import Static
from datetime import datetime
from typing import Optional, Callable
import threading


class LogPanel(Static):
    """
    Filtered log display with log level filtering
    
    Features:
    - Log level filtering (DEBUG, INFO, WARNING, ERROR)
    - Color-coded by level
    - Timestamp display
    - Maximum log limit
    - Real-time updates from backend logger
    """
    
    LEVELS = {
        'DEBUG': 10,
        'INFO': 20,
        'WARNING': 30,
        'ERROR': 40,
        'CRITICAL': 50
    }
    
    MAX_LOGS = 100
    
    def __init__(self, log_level: str = "WARNING", id: str = None):
        """
        Initialize log panel
        
        Args:
            log_level: Minimum log level to display
            id: Widget ID for CSS selection
        """
        super().__init__(id=id)
        self.log_level = self.LEVELS.get(log_level.upper(), 30)
        self.logs: list[str] = []
        self._buffer: list[tuple[str, str]] = []  # (message, level) buffer
        self._buffer_lock = threading.Lock()
        self._max_buffer_size = 50
        self._callback: Optional[Callable] = None
        self._flush_pending = False
    
    def add_log(self, message: str, level: str = "INFO", real_time: bool = False) -> None:
        """
        Add log entry (filtered by level)
        
        Args:
            message: Log message
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            real_time: If True, adds to buffer for real-time refresh
        """
        level_num = self.LEVELS.get(level.upper(), 20)
        
        # Filter by log level
        if level_num < self.log_level:
            return
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color by level
        if level_num >= self.LEVELS['ERROR']:
            formatted = f"[red][{timestamp}] {level}: {message}[/red]"
        elif level_num >= self.LEVELS['WARNING']:
            formatted = f"[yellow][{timestamp}] {level}: {message}[/yellow]"
        elif level_num >= self.LEVELS['DEBUG']:
            formatted = f"[dim][{timestamp}] {level}: {message}[/dim]"
        else:
            formatted = f"[{timestamp}] {message}"
        
        if real_time:
            # Add to buffer for real-time flush
            with self._buffer_lock:
                self._buffer.append((formatted, level))
                
                # Flush if buffer is full or on critical messages
                if len(self._buffer) >= 10 or level.upper() in ('ERROR', 'CRITICAL'):
                    self._flush_buffer()
        else:
            # Direct addition (legacy mode)
            self.logs.append(formatted)
            
            # Trim old logs
            if len(self.logs) > self.MAX_LOGS:
                self.logs = self.logs[-self.MAX_LOGS:]
            
            # Update display
            self.update("\n".join(self.logs))
    
    def _flush_buffer(self) -> None:
        """Flush buffered logs to display"""
        with self._buffer_lock:
            if not self._buffer:
                return
            
            # Add buffered logs
            for formatted, _ in self._buffer:
                self.logs.append(formatted)
            
            self._buffer.clear()
            
            # Trim old logs
            if len(self.logs) > self.MAX_LOGS:
                self.logs = self.logs[-self.MAX_LOGS:]
            
            # Update display
            self.update("\n".join(self.logs))
    
    def flush(self) -> None:
        """Force flush any pending buffered logs"""
        self._flush_buffer()
    
    def set_callback(self, callback: Callable) -> None:
        """
        Set callback for real-time log updates
        
        Args:
            callback: Function to call when logs are added
        """
        self._callback = callback
    
    def set_level(self, level: str) -> None:
        """
        Change log level filter
        
        Args:
            level: New minimum log level
        """
        self.log_level = self.LEVELS.get(level.upper(), 30)
        # Re-display existing logs
        self.update("\n".join(self.logs))
    
    def clear(self) -> None:
        """Clear all logs"""
        with self._buffer_lock:
            self._buffer.clear()
        self.logs.clear()
        self.update("")
    
    def get_logs(self) -> list[str]:
        """Return all logged messages"""
        return self.logs.copy()
    
    def get_buffer_size(self) -> int:
        """Return current buffer size"""
        with self._buffer_lock:
            return len(self._buffer)
