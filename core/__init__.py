"""Core APRIL Agent Runtime"""

from .config import AgentConfig
from .agent import AgentRuntime
from .session import Session, SessionManager
from .database import MemoryDatabase
from .memory_extractor import MemoryExtractor
from .tui import APRIL_TUI, ConsoleRenderer as curses_ConsoleRenderer
from .textual_tui import APRILApp, ConsoleRenderer as textual_ConsoleRenderer

__all__ = [
    'AgentConfig', 
    'AgentRuntime', 
    'Session', 
    'SessionManager',
    'MemoryDatabase',
    'MemoryExtractor',
    # Legacy curses TUI
    'APRIL_TUI',
    'curses_ConsoleRenderer',
    # New Textual TUI
    'APRILApp',
    'textual_ConsoleRenderer',
]
