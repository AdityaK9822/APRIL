"""
StatsWidget - Memory statistics display
"""

from textual.widgets import Static
from typing import Optional


class StatsWidget(Static):
    """
    Memory statistics display
    
    Features:
    - Total memories count
    - Total messages count
    - Total sessions count
    - Unprocessed messages count
    - Memories by type breakdown
    """
    
    UPDATE_INTERVAL = 5.0  # seconds
    
    def __init__(self, db=None, id: str = None):
        """
        Initialize stats widget
        
        Args:
            db: MemoryDatabase instance for statistics
            id: Widget ID for CSS selection
        """
        super().__init__(id=id)
        self.db = db
        self.stats = {}
    
    def on_mount(self) -> None:
        """Widget is added to the DOM - start periodic updates"""
        self.update_stats()
        self.set_interval(self.UPDATE_INTERVAL, self.update_stats)
    
    def update_stats(self, stats: Optional[dict] = None) -> None:
        """
        Update statistics display
        
        Args:
            stats: Optional pre-fetched stats dict
        """
        if stats is None and self.db:
            try:
                stats = self.db.get_stats()
            except Exception:
                stats = {}
        
        if not stats:
            stats = self.stats or {
                'total_memories': 0,
                'total_messages': 0,
                'total_sessions': 0,
                'unprocessed_messages': 0,
                'memory_by_type': {}
            }
        
        # Update stored stats
        self.stats = stats
        
        # Build display text
        text = "[bold]Memory Statistics[/bold]\n\n"
        text += f"  Total Memories: [cyan]{stats.get('total_memories', 0)}[/cyan]\n"
        text += f"  Total Messages: [cyan]{stats.get('total_messages', 0)}[/cyan]\n"
        text += f"  Sessions: [cyan]{stats.get('total_sessions', 0)}[/cyan]\n"
        text += f"  Unprocessed: [yellow]{stats.get('unprocessed_messages', 0)}[/yellow]\n"
        
        # Add memory by type if available
        memory_by_type = stats.get('memory_by_type', {})
        if memory_by_type:
            text += "\n[bold]By Type:[/bold]\n"
            for mem_type, count in sorted(memory_by_type.items()):
                text += f"    {mem_type}: {count}\n"
        
        self.update(text)
    
    def get_stats(self) -> dict:
        """Return current stats"""
        return self.stats.copy()
