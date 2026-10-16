#!/usr/bin/env python3
"""
APRIL Textual TUI - Main Application

Modern Textual-based terminal user interface for APRIL.
"""

import sys
import asyncio
import argparse
import os
import signal
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button
from textual.containers import Horizontal, Vertical
from textual.screen import Screen

from .widgets.status import StatusWidget
from .widgets.messages import MessageList
from .widgets.input import InputWidget
from .widgets.logs import LogPanel
from .widgets.stats import StatsWidget
from .config import AgentConfig
from .agent import AgentRuntime
from .logger import APRILLogger
from .events import get_event_bus, Event, MessageDelta, LogEvent, ErrorEvent, StatusEvent
from .ipc_server import IPCServer


class APRILApp(App):
    """
    Main Textual application for APRIL
    """
    
    CSS_PATH = Path(__file__).parent / "april.tcss"
    
    BINDINGS = [
        ("ctrl+l", "toggle_logs", "Toggle Logs"),
        ("ctrl+s", "show_stats", "Stats"),
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+c", "cancel_generation", "Cancel"),
        ("escape", "clear_input", "Clear"),
        ("alt+enter", "insert_newline", "Newline"),
    ]
    
    def __init__(self, agent: Optional['AgentRuntime'] = None, db=None):
        super().__init__()
        self.agent = agent
        self.db = db
        self.show_logs = True
        self._log_flush_timer = None
        self._event_bus = get_event_bus()
        self._ipcs_server = None
        self._subscription_ids = []
        
        # For streaming
        self._current_msg_id: Optional[str] = None
        self._streaming_buffer = ""
    
    def compose(self) -> ComposeResult:
        """Compose the UI layout"""
        yield Header()
        
        yield StatusWidget()
        
        with Horizontal():
            yield MessageList()
            yield StatsWidget(db=self.db)
        
        yield LogPanel()
        
        yield Footer()
        
        yield InputWidget(
            placeholder="Type your message... (Enter to send, Alt+Enter for newline, /help for commands)"
        )
    
    async def on_mount(self) -> None:
        """Configure widgets after they're mounted"""
        self.query_one(InputWidget).focus()
        
        # Set up log level
        log_level = os.getenv('APRIL_LOG_LEVEL', 'WARNING')
        log_panel = self.query_one(LogPanel)
        log_panel.set_level(log_level)
        
        # Show/hide logs
        show_logs_env = os.getenv('APRIL_TUI_SHOW_LOGS', 'false').lower()
        if show_logs_env != 'true':
            log_panel.display = False
            self.show_logs = False
        
        # Subscribe to events
        # Create a list and append to avoid the previous bug
        subs = [
            self._event_bus.subscribe_async('message.delta', self._on_message_delta),
            self._event_bus.subscribe_async('message.start', self._on_message_start),
        ]
        subs.append(self._event_bus.subscribe_async('message.done', self._on_message_done))
        subs.append(self._event_bus.subscribe_async('log', self._on_log_event))
        subs.append(self._event_bus.subscribe_async('error', self._on_error_event))
        subs.append(self._event_bus.subscribe_async('status', self._on_status_event))
        self._subscription_ids = subs
        
        # Start IPC server for external logger
        self._start_ipc_server()
        
        # Start log flush timer
        self.set_interval(0.5, self._flush_logs)
    
    def _start_ipc_server(self):
        """Start IPC server for external logger."""
        try:
            import asyncio
            self._ipc_task = asyncio.create_task(self._start_ipc_server_async())
        except Exception as e:
            self.log(f"IPC server failed: {e}")
    
    async def _start_ipc_server_async(self):
        """Start IPC server (async)."""
        self._ipcs_server = None
        try:
            from .ipc_server import IPCServer
            self._ipcs_server = IPCServer()
            await self._ipcs_server.start()
        except Exception as e:
            self.log(f"Failed to start IPC server: {e}")
    
    def _flush_logs(self):
        """Flush log panel."""
        try:
            log_panel = self.query_one(LogPanel)
            log_panel.flush()
        except Exception:
            pass
    
    async def _on_message_delta(self, event: Event) -> None:
        """Handle message delta events (streaming)."""
        delta: MessageDelta = event.payload
        if delta.is_assistant:
            if self._current_msg_id:
                message_list = self.query_one(MessageList)
                await message_list.add_message_delta(delta.content)
    
    async def _on_message_start(self, event: Event) -> None:
        """Handle message start."""
        if event.payload.is_assistant:
            self._current_msg_id = event.payload.message_id
    
    async def _on_message_done(self, event: Event) -> None:
        """Handle message done."""
        self._current_msg_id = None
    
    async def _on_log_event(self, event: Event) -> None:
        """Handle log events."""
        log_event: LogEvent = event.payload
        try:
            log_panel = self.query_one(LogPanel)
            log_panel.add_log(log_event.message, log_event.level, real_time=True)
        except Exception:
            pass
    
    async def _on_error_event(self, event: Event) -> None:
        """Handle error events."""
        error_event: ErrorEvent = event.payload
        try:
            log_panel = self.query_one(LogPanel)
            log_panel.add_log(f"[{error_event.error_type}] {error_event.message}", "ERROR", real_time=True)
            
            message_list = self.query_one(MessageList)
            message_list.add_system_message(f"⚠️ Error: {error_event.message}")
        except Exception:
            pass
    
    async def _on_status_event(self, event: Event) -> None:
        """Handle status events."""
        status_event: StatusEvent = event.payload
        try:
            status_widget = self.query_one(StatusWidget)
            status_widget.update_status(status_event.status)
        except Exception:
            pass
    
    async def action_send_message(self) -> None:
        """Handle Enter key - send user message"""
        input_widget = self.query_one(InputWidget)
        message = input_widget.value
        
        if not message.strip():
            return
        
        input_widget.value = ""
        input_widget.add_to_history(message)
        
        message_list = self.query_one(MessageList)
        message_list.add_message("user", message)
        
        asyncio.create_task(self._process_message(message))
    
    async def _process_message(self, message: str) -> None:
        """Process message through agent (non-blocking)"""
        status_widget = self.query_one(StatusWidget)
        status_widget.to_thinking()
        
        if self.agent:
            try:
                # Run in thread pool to avoid blocking
                response_task = asyncio.create_task(
                    asyncio.to_thread(self.agent.run, message)
                )
                
                response = await response_task
                
                message_list = self.query_one(MessageList)
                message_list.add_message("assistant", response)
                
            except asyncio.CancelledError:
                message_list = self.query_one(MessageList)
                message_list.add_system_message("Operation cancelled")
            
            except Exception as e:
                error_panel = self.query_one(LogPanel)
                error_panel.add_log(f"Agent error: {e}", "ERROR")
                message_list = self.query_one(MessageList)
                message_list.add_system_message(f"Error: {e}")
        else:
            message_list = self.query_one(MessageList)
            message_list.add_system_message("No agent connected")
        
        status_widget.to_ready()
        
        if self.db:
            try:
                stats = self.db.get_stats()
                self.query_one(StatsWidget).update_stats(stats)
            except Exception:
                pass
    
    def action_toggle_logs(self) -> None:
        """Toggle log panel visibility"""
        log_panel = self.query_one(LogPanel)
        self.show_logs = not self.show_logs
        log_panel.display = self.show_logs
    
    def action_show_stats(self) -> None:
        """Force stats update"""
        if self.db:
            try:
                stats = self.db.get_stats()
                self.query_one(StatsWidget).update_stats(stats)
            except Exception:
                pass
    
    def action_clear_input(self) -> None:
        """Clear input field"""
        input_widget = self.query_one(InputWidget)
        input_widget.value = ""
    
    def action_insert_newline(self) -> None:
        """Insert newline in input widget"""
        input_widget = self.query_one(InputWidget)
        input_widget.value += "\n"
    
    def action_cancel_generation(self) -> None:
        """Cancel current generation"""
        if self.agent and hasattr(self.agent, 'request_cancel'):
            self.agent.request_cancel()
            message_list = self.query_one(MessageList)
            message_list.add_system_message("⚠️ Cancelling generation...")
        else:
            self.action_clear_input()
    
    def action_quit(self) -> None:
        """Quit the application"""
        for sub_id in self._subscription_ids:
            self._event_bus.unsubscribe(sub_id)
        
        if hasattr(self, '_ipcs_server') and self._ipcs_server:
            try:
                if hasattr(self._ipcs_server, 'stop'):
                    asyncio.create_task(self._ipcs_server.stop())
            except Exception:
                pass
        
        self.exit()
    
    async def on_key(self, event) -> None:
        """Handle key events for slash commands"""
        if event.key == "enter":
            input_widget = self.query_one(InputWidget)
            message = input_widget.value
            
            if message.strip().startswith('/'):
                await self._handle_slash_command(message.strip()[1:])
                input_widget.value = ""
                return
    
    async def _handle_slash_command(self, command: str) -> None:
        """Handle slash commands"""
        cmd = command.lower().strip()
        
        if cmd in ['help', '?']:
            message_list = self.query_one(MessageList)
            message_list.add_system_message(
                "Slash commands:\n"
                "  /clear - Clear conversation\n"
                "  /quit  - Exit application\n"
                "  /help  - Show this help\n"
                "  /save  - Save current session\n"
                "  /load  - Load session from file"
            )
        
        elif cmd in ['clear']:
            self.action_clear()
        
        elif cmd in ['quit', 'exit']:
            self.action_quit()
        
        elif cmd in ['save']:
            message_list = self.query_one(MessageList)
            message_list.add_system_message("Save command not yet implemented")
        
        elif cmd in ['load']:
            message_list = self.query_one(MessageList)
            message_list.add_system_message("Load command not yet implemented")
    
    def action_clear(self) -> None:
        """Clear conversation"""
        message_list = self.query_one(MessageList)
        message_list.clear()
        
        if self.agent:
            try:
                self.agent.clear_context()
            except Exception:
                pass


def get_agent() -> Optional[AgentRuntime]:
    """Create and configure agent if enabled"""
    try:
        config = AgentConfig.from_env()
        agent = AgentRuntime(config)
        
        import os
        log_level = os.getenv('APRIL_LOG_LEVEL', 'INFO')
        
        print(f"Agent created with model: {config.model}")
        print(f"Backend logger level: {log_level}")
        print(f"Tools available: {', '.join(agent.tool_map.keys())}")
        
        return agent
    except Exception as e:
        print(f"Warning: Could not create agent: {e}")
        return None


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="APRIL Textual TUI")
    parser.add_argument(
        '--agent',
        action='store_true',
        help='Enable agent integration'
    )
    args = parser.parse_args()
    
    agent = get_agent() if args.agent else None
    db = agent.db if agent else None
    
    app = APRILApp(agent=agent, db=db)
    
    try:
        app.run()
    except KeyboardInterrupt:
        app.exit()


if __name__ == "__main__":
    main()
