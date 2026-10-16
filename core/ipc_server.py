"""
APRIL IPC Server

Socket server for IPC between TUI and external logger process.
Supports Unix sockets (macOS/Linux) and TCP fallback (Windows).
"""

import asyncio
import json
import os
import socket
import sys
import tempfile
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
import uuid

from .events import Event, EventBus, get_event_bus


class IPCServer:
    """
    IPC server that bridges the event bus to external processes.
    """
    
    def __init__(self, host: str = '127.0.0.1', port: int = 0, socket_path: Optional[str] = None):
        self.host = host
        self.port = port
        self.socket_path = socket_path or os.path.join(tempfile.gettempdir(), f'april_ipc_{uuid.uuid4().hex[:8]}.sock')
        self._server: Optional[asyncio.AbstractServer] = None
        self._clients: Set[asyncio.StreamWriter] = set()
        self._clients_lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Subscribe to event bus
        self._event_bus = get_event_bus()
        self._event_sub = self._event_bus.subscribe_async('message.delta', self._on_event)
        self._event_sub = self._event_bus.subscribe_async('message.start', self._on_event)
        self._event_sub = self._event_bus.subscribe_async('message.done', self._on_event)
        self._event_sub = self._event_bus.subscribe_async('tool_call.start', self._on_event)
        self._event_sub = self._event_bus.subscribe_async('tool_call.output', self._on_event)
        self._event_sub = self._event_bus.subscribe_async('tool_call.done', self._on_event)
        self._event_sub = self._event_bus.subscribe_async('log', self._on_event)
        self._event_sub = self._event_bus.subscribe_async('error', self._on_event)
        self._event_sub = self._event_bus.subscribe_async('status', self._on_event)
        self._event_sub = self._event_bus.subscribe_async('session', self._on_event)
    
    async def _on_event(self, event: Event) -> None:
        """Handle event from event bus, send to all clients."""
        await self._send_to_clients(event)
    
    async def _send_to_clients(self, event: Event) -> None:
        """Send event to all connected clients."""
        event_dict = {
            'type': event.event_type,
            'payload': asdict(event.payload) if event.payload else None,
            'timestamp': event.timestamp.isoformat(),
            'id': event.id
        }
        message = json.dumps(event_dict) + '\n'
        
        with self._clients_lock:
            disconnected = []
            for writer in self._clients:
                try:
                    writer.write(message.encode('utf-8'))
                    await writer.drain()
                except (ConnectionError, BrokenPipeError, asyncio.CancelledError):
                    disconnected.append(writer)
            
            for writer in disconnected:
                self._clients.discard(writer)
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle a single client connection."""
        with self._clients_lock:
            self._clients.add(writer)
        
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                # Echo heartbeat or process commands
                message = data.decode('utf-8').strip()
                if message == 'PING':
                    writer.write(b'PONG\n')
                    await writer.drain()
        except (ConnectionError, BrokenPipeError, asyncio.CancelledError):
            pass
        finally:
            with self._clients_lock:
                self._clients.discard(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
    
    async def start(self) -> None:
        """Start the IPC server."""
        if sys.platform == 'win32':
            # Windows: use TCP
            self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
            self.port = self._server.sockets[0].getsockname()[1]
        else:
            # Unix: use socket file
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
            self._server = await asyncio.start_unix_server(self._handle_client, self.socket_path)
            os.chmod(self.socket_path, 0o600)
            self.port = 0  # Socket path is the address
        
        self._running = True
    
    async def stop(self) -> None:
        """Stop the IPC server."""
        self._running = False
        
        # Close all clients
        with self._clients_lock:
            for writer in list(self._clients):
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
            self._clients.clear()
        
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        # Clean up socket file
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Unsubscribe from event bus
        try:
            self._event_bus.unsubscribe(self._event_sub)
        except Exception:
            pass
    
    def get_address(self) -> str:
        """Get the server address for clients to connect."""
        if sys.platform == 'win32':
            return f'tcp://{self.host}:{self.port}'
        else:
            return f'unix://{self.socket_path}'
    
    def get_socket_path(self) -> Optional[str]:
        """Get the socket path (Unix only)."""
        if sys.platform == 'win32':
            return None
        return self.socket_path
    
    def get_tcp_info(self) -> Optional[Dict[str, int]]:
        """Get TCP host/port (Windows or fallback)."""
        if sys.platform == 'win32' and self._server:
            return {'host': self.host, 'port': self.port}
        return None


async def run_ipc_server() -> IPCServer:
    """Create and start IPC server."""
    server = IPCServer()
    await server.start()
    return server


# For backwards compatibility
def create_ipc_server() -> IPCServer:
    """Create IPC server (sync wrapper)."""
    return IPCServer()
