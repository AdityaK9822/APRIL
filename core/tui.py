"""
APRIL Console TUI

A simple, responsive console-based user interface for APRIL.
Uses Python's built-in curses module for terminal rendering.

Features:
- Status panel showing session info
- Message history with visual separation
- Input field for user commands
- Memory statistics display
- Auto-scrolling log view (optional)

Usage:
    from core.tui import APRIL_TUI
    
    tui = APRIL_TUI()
    tui.start()
"""

import curses
import sys
import threading
import time
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path


class APRIL_TUI:
    """
    Console-based TUI for APRIL agent
    
    Provides a clean, responsive interface with:
    - Status bar (memory stats, session info)
    - Message history area
    - Input prompt
    - Auto-scrolling logs
    """
    
    def __init__(self, agent: Optional['AgentRuntime'] = None, db=None):
        """
        Initialize the TUI
        
        Args:
            agent: Optional AgentRuntime instance for stats
            db: Optional MemoryDatabase instance for stats
        """
        self.agent = agent
        self.db = db
        self.running = False
        
        # UI state
        self.input_buffer = ""
        self.messages: List[Dict] = []
        self.logs: List[str] = []
        self.status = "Ready"
        
        # Colors - initialized lazily in curses wrapper
        self._colors_initialized = False
    
    def _init_colors(self):
        """Initialize color pairs"""
        try:
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)   # Header
            curses.init_pair(2, curses.COLOR_CYAN, -1)    # User messages
            curses.init_pair(3, curses.COLOR_YELLOW, -1)  # Assistant messages
            curses.init_pair(4, curses.COLOR_WHITE, -1)   # Status
            curses.init_pair(5, curses.COLOR_BLUE, -1)    # Memory stats
            curses.init_pair(6, curses.COLOR_GRAY, -1)    # Dim text
            curses.init_pair(7, curses.COLOR_RED, -1)     # Errors
            self._colors_initialized = True
        except:
            # Colors not available outside curses (fallback mode)
            self._colors_initialized = False
    
    def _log(self, message: str, level: str = "info"):
        """
        Add a log message with proper filtering
        
        Args:
            message: Log message
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        import os
        from core.logging import APRILLogger
        
        # Get log level from environment
        log_level = os.getenv('APRIL_LOG_LEVEL', 'WARNING').upper()
        
        # Map level strings to logging levels
        level_map = {
            'DEBUG': 10, 'INFO': 20, 'WARNING': 30,
            'ERROR': 40, 'CRITICAL': 50
        }
        
        # Filter based on log level
        msg_level = level_map.get(level.upper(), 20)
        threshold = level_map.get(log_level, 30)
        
        # Only show if message level >= threshold
        if msg_level >= threshold:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.logs.append(f"[{timestamp}] {message}")
            
            # Keep only last 100 logs
            if len(self.logs) > 100:
                self.logs = self.logs[-100:]
    
    def _get_stats(self) -> Dict:
        """Get current statistics"""
        stats = {}
        
        if self.db:
            try:
                stats = self.db.get_stats()
            except:
                pass
        
        if not stats:
            stats = {
                'total_messages': len(self.messages),
                'total_memories': 0,
                'total_sessions': 0,
                'unprocessed_messages': 0
            }
        
        return stats
    
    def _draw_header(self, stdscr, y, width):
        """Draw header bar"""
        try:
            # APRIL logo
            logo = " APRIL - An assistant with a body "
            stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
            stdscr.addnstr(y, 0, logo, width - 1)
            stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
            
            # Status
            status = f" {self.status} "
            stdscr.attron(curses.color_pair(4) | curses.A_REVERSE)
            stdscr.addnstr(y, width - len(status) - 1, status, len(status) + 1)
            stdscr.attroff(curses.color_pair(4) | curses.A_REVERSE)
            
        except:
            pass
    
    def _draw_stats(self, stdscr, y, width):
        """Draw statistics bar"""
        stats = self._get_stats()
        
        stats_str = f" Memory: {stats.get('total_memories', 0)} | Messages: {stats.get('total_messages', 0)} | Sessions: {stats.get('total_sessions', 0)} "
        
        try:
            stdscr.attron(curses.color_pair(5))
            stdscr.addnstr(y, 0, stats_str, width - 1)
            stdscr.attroff(curses.color_pair(5))
        except:
            pass
    
    def _draw_messages(self, stdscr, start_y, height, width):
        """Draw message history"""
        messages = self.messages[-(height - 2):]  # Show last N messages
        
        for i, msg in enumerate(messages):
            y = start_y + i
            if y >= start_y + height - 2:
                break
            
            try:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')[:width - 3]
                
                if role == 'user':
                    stdscr.attron(curses.color_pair(2))
                    stdscr.addnstr(y, 0, f"  {content}", width - 1)
                    stdscr.attroff(curses.color_pair(2))
                elif role == 'assistant':
                    stdscr.attron(curses.color_pair(3))
                    stdscr.addnstr(y, 0, f"  {content}", width - 1)
                    stdscr.attroff(curses.color_pair(3))
                else:
                    stdscr.addnstr(y, 0, f"  {content}", width - 1)
                    
            except:
                pass
    
    def _draw_input(self, stdscr, y, width):
        """Draw input prompt"""
        prompt = "  > "
        
        try:
            # Input prefix
            stdscr.attron(curses.color_pair(6))
            stdscr.addnstr(y, 0, prompt, len(prompt))
            stdscr.attroff(curses.color_pair(6))
            
            # Input buffer
            stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
            stdscr.addnstr(y, len(prompt), self.input_buffer, width - len(prompt) - 1)
            stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
            
            # Cursor position
            cursor_x = len(prompt) + len(self.input_buffer)
            try:
                stdscr.move(y, cursor_x)
            except:
                pass
                
        except:
            pass
    
    def _draw_logs(self, stdscr, start_y, height, width):
        """Draw log panel (bottom)"""
        # Logs header
        try:
            stdscr.attron(curses.color_pair(6) | curses.A_UNDERLINE)
            stdscr.addnstr(start_y, 2, " Logs (suppressing errors by default) ", width - 4)
            stdscr.attroff(curses.color_pair(6) | curses.A_UNDERLINE)
        except:
            pass
        
        # Show last few logs
        logs = self.logs[-(height - 4):]
        for i, log in enumerate(logs):
            y = start_y + 1 + i
            if y >= start_y + height:
                break
            
            try:
                # Truncate and color based on content
                log_display = log[:width - 5]
                
                if "error" in log.lower() or "Error" in log:
                    stdscr.attron(curses.color_pair(7))
                    stdscr.addnstr(y, 2, log_display, width - 3)
                    stdscr.attroff(curses.color_pair(7))
                else:
                    stdscr.attron(curses.color_pair(6))
                    stdscr.addnstr(y, 2, log_display, width - 3)
                    stdscr.attroff(curses.color_pair(6))
                    
            except:
                pass
    
    def _draw(self, stdscr):
        """Main draw function"""
        # Clear screen
        stdscr.clear()
        
        height, width = stdscr.getmaxyx()
        
        # Define sections
        header_y = 0
        stats_y = 1
        messages_start = 2
        messages_height = height - 6  # Leave room for input and logs
        logs_start = height - 4
        logs_height = 4
        
        # Draw sections
        self._draw_header(stdscr, header_y, width)
        self._draw_stats(stdscr, stats_y, width)
        self._draw_messages(stdscr, messages_start, messages_height, width)
        self._draw_input(stdscr, height - 5, width)
        self._draw_logs(stdscr, logs_start, logs_height, width)
        
        stdscr.refresh()
    
    def _handle_input(self, stdscr):
        """Handle keyboard input"""
        stdscr.nodelay(True)  # Non-blocking input
        
        while self.running:
            try:
                key = stdscr.getch()
                
                if key == -1:
                    continue
                elif key == 10:  # Enter
                    # Process input
                    if self.input_buffer.strip():
                        self._process_command(self.input_buffer)
                        self.input_buffer = ""
                elif key == 127 or key == 8:  # Backspace
                    self.input_buffer = self.input_buffer[:-1]
                elif 32 <= key <= 126:  # Printable characters
                    self.input_buffer += chr(key)
                
                # Redraw
                self._draw(stdscr)
                
            except Exception:
                pass  # Ignore input errors
            
            time.sleep(0.05)  # Small delay to prevent CPU spinning
    
    def _process_command(self, command: str):
        """
        Process a command
        
        Args:
            command: User input command
        """
        cmd = command.strip().lower()
        
        if cmd in ['help', '?']:
            self._log("Commands: help, clear, stats, exit")
        elif cmd in ['clear', 'cls']:
            self.messages.clear()
            self._log("Cleared message history")
        elif cmd in ['stats']:
            stats = self._get_stats()
            self._log(f"Stats: {stats}")
        elif cmd in ['exit', 'quit', 'q']:
            self.running = False
        else:
            # Forward to agent if available
            if self.agent:
                try:
                    response = self.agent.run(command)
                    self.messages.append({'role': 'user', 'content': command})
                    self.messages.append({'role': 'assistant', 'content': response})
                    self._log(f"Processed: {command[:50]}...")
                except Exception as e:
                    self._log(f"Error: {str(e)}", "error")
            else:
                self._log(f"Unknown command: {cmd}")
    
    def start(self):
        """Start the TUI"""
        self.running = True
        
        # Initial log
        self._log("APRIL TUI started", "success")
        
        try:
            curses.wrapper(self._main_loop)
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
    
    def _main_loop(self, stdscr):
        """Main TUI loop"""
        # Setup curses
        curses.curs_set(0)  # Hide cursor (we draw it manually)
        stdscr.nodelay(True)
        
        # Start input handler thread
        input_thread = threading.Thread(target=self._handle_input, args=(stdscr,))
        input_thread.daemon = True
        input_thread.start()
        
        # Main draw loop
        while self.running:
            try:
                self._draw(stdscr)
            except KeyboardInterrupt:
                break
            except Exception:
                pass
            
            time.sleep(0.1)  # Redraw rate limit
    
    def stop(self):
        """Stop the TUI"""
        self.running = False
    
    def add_message(self, role: str, content: str):
        """Add a message to the display"""
        self.messages.append({'role': role, 'content': content})
    
    def update_status(self, status: str):
        """Update the status bar"""
        self.status = status


class ConsoleRenderer:
    """
    Simple console renderer (curses fallback)
    
    Prints APRIL output to console with clear formatting.
    """
    
    def __init__(self):
        self.messages: List[Dict] = []
        self.running = False
    
    def print_header(self):
        """Print header"""
        print()
        print("=" * 60)
        print(" APRIL - An assistant with a body ".center(60))
        print("=" * 60)
        print()
    
    def print_message(self, role: str, content: str):
        """Print a message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if role == 'user':
            print(f"\n[{timestamp}] 👤 You:")
            print(f"    {content}")
        elif role == 'assistant':
            print(f"\n[{timestamp}] 🤖 APRIL:")
            # Wrap long lines
            width = 56
            lines = [content[i:i+width] for i in range(0, len(content), width)]
            for line in lines:
                print(f"    {line}")
        else:
            print(f"\n[{timestamp}] {role.upper()}:")
            print(f"    {content}")
    
    def print_status(self, status: str):
        """Print status"""
        print(f"\n[{status}]".center(60))
    
    def start(self):
        """Start the renderer"""
        self.running = True
        self.print_header()
    
    def stop(self):
        """Stop the renderer"""
        self.running = False
        print("\n APRIL TUI stopped. Goodbye! ".center(60, "="))
        print()


# CLI interface
def main():
    """CLI entry point for testing TUI"""
    import argparse
    
    parser = argparse.ArgumentParser(description='APRIL Console TUI')
    parser.add_argument('--agent', action='store_true', help='Connect to live agent')
    parser.add_argument('--no-tui', action='store_true', help='Use simple renderer instead of TUI')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    if args.no_tui:
        # Simple console mode
        renderer = ConsoleRenderer()
        renderer.start()
        
        if args.agent:
            from core import AgentConfig, AgentRuntime
            
            config = AgentConfig.from_env()
            if args.debug:
                import os
                os.environ['APRIL_DEBUG'] = '1'
            
            agent = AgentRuntime(config)
            renderer.agent = agent
            
            print("\nType 'exit' to quit\n")
            
            while True:
                try:
                    user_input = input("You: ")
                    if user_input.lower() in ['exit', 'quit', 'q']:
                        break
                    
                    response = agent.run(user_input)
                    renderer.add_message('user', user_input)
                    renderer.add_message('assistant', response)
                    renderer.print_message('assistant', response)
                    
                except KeyboardInterrupt:
                    break
                except EOFError:
                    break
        
        renderer.stop()
    
    else:
        # Full TUI mode
        from core import AgentConfig, AgentRuntime
        
        config = AgentConfig.from_env()
        if args.debug:
            import os
            os.environ['APRIL_DEBUG'] = '1'
        
        agent = AgentRuntime(config)
        
        tui = APRIL_TUI(agent=agent, db=agent.db)
        tui.start()


if __name__ == "__main__":
    main()
