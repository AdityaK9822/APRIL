"""
APRIL IPC Logger

Separate process that connects to IPC server and logs events.
This runs as a separate terminal window/tab.
"""

import asyncio
import json
import os
import sys
import re
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, List

# Try to import colorama, but don't fail if not available
try:
    import colorama
    colorama.init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False
    colorama = type('colorama', (), {
        'init': lambda *a, **k: None,
        'Style': type('Style', (), {'BRIGHT': ''}),
        'Fore': type('Fore', (), {
            'RED': '', 'GREEN': '', 'YELLOW': '', 'BLUE': '',
            'MAGENTA': '', 'CYAN': '', 'WHITE': '', 'RESET': ''
        }),
        'Back': type('Back', (), {}),
        'Cursor': type('Cursor', (), {})
    })()


class Color:
    """ANSI color codes."""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


LOG_LEVEL_COLORS = {
    'DEBUG': Color.DIM + Color.WHITE,
    'INFO': Color.CYAN,
    'WARNING': Color.YELLOW,
    'ERROR': Color.RED,
    'CRITICAL': Color.MAGENTA,
}

SOURCE_COLORS = {
    'llm': Color.BLUE,
    'tool': Color.GREEN,
    'agent': Color.MAGENTA,
    'session': Color.CYAN,
    'memory': Color.YELLOW,
    'error': Color.RED,
    'default': Color.WHITE,
}


class LogFormatter:
    """Format events for display."""
    
    MAX_OUTPUT_LEN = 5000
    
    SENSITIVE_PATTERNS: List = [
        re.compile(r'api[_-]?key[_-]?\s*[=:]\s*["\']?[\w\-\+]{10,}', re.IGNORECASE),
        re.compile(r'secret[_-]?key[_-]?\s*[=:]\s*["\']?[\w\-\+]{10,}', re.IGNORECASE),
        re.compile(r'token[_-]?\s*[=:]\s*["\']?[\w\-\+]{10,}', re.IGNORECASE),
        re.compile(r'password[_-]?\s*[=:]\s*["\']?[^\s"\']+', re.IGNORECASE),
    ]
    
    @classmethod
    def truncate(cls, text: str, max_len: int = None) -> str:
        """Truncate long text with marker."""
        if max_len is None:
            max_len = cls.MAX_OUTPUT_LEN
        if len(text) > max_len:
            return text[:max_len] + f'\n{Color.DIM}[... output truncated at {max_len} chars ...]{Color.RESET}'
        return text
    
    @classmethod
    def redact(cls, text: str) -> str:
        """Redact sensitive information."""
        result = text
        for pattern in cls.SENSITIVE_PATTERNS:
            result = pattern.sub(lambda m: m.group(0)[:m.group(0).find('=')+1] + '***REDACTED***', result)
        return result
    
    @classmethod
    def format_event(cls, event: dict) -> Optional[str]:
        """Format an event for display."""
        event_type = event.get('type', 'unknown')
        payload = event.get('payload', {})
        timestamp = event.get('timestamp', '')
        
        if not timestamp:
            timestamp = datetime.now().strftime('%H:%M:%S')
        else:
            try:
                timestamp = datetime.fromisoformat(timestamp).strftime('%H:%M:%S')
            except ValueError:
                pass
        
        if event_type == 'log':
            level = payload.get('level', 'INFO')
            source = payload.get('source', 'unknown')
            message = cls.redact(payload.get('message', ''))
            
            color = LOG_LEVEL_COLORS.get(level, Color.WHITE)
            source_color = SOURCE_COLORS.get(source, Color.WHITE)
            
            return f'{timestamp} {color}[{level}]{Color.RESET} {source_color}[{source}]{Color.RESET} {message}'
        
        elif event_type == 'tool_call.start':
            tool_name = payload.get('tool_name', 'unknown')
            args = payload.get('tool_args', {})
            return f'{timestamp} {Color.GREEN}[TOOL]{Color.RESET} Calling: {tool_name}'
        
        elif event_type == 'tool_call.output':
            text = cls.truncate(cls.redact(payload.get('text', '')))
            is_error = payload.get('is_error', False)
            color = Color.RED if is_error else Color.DIM
            return f'{timestamp} {Color.DIM}[TOOL OUTPUT]{Color.RESET}\n{text}'
        
        elif event_type == 'tool_call.done':
            tool_name = payload.get('tool_name', 'unknown')
            result = cls.truncate(cls.redact(payload.get('result', '')))
            success = payload.get('success', True)
            color = Color.GREEN if success else Color.RED
            return f'{timestamp} {color}[TOOL DONE]{Color.RESET} {tool_name}: {result}'
        
        elif event_type == 'message.delta':
            return None  # Skip for logger
        
        elif event_type == 'message.start':
            return f'{timestamp} {Color.CYAN}[MESSAGE]{Color.RESET} Starting response'
        
        elif event_type == 'message.done':
            return f'{timestamp} {Color.GREEN}[MESSAGE]{Color.RESET} Response complete'
        
        elif event_type == 'error':
            error_type = payload.get('error_type', 'unknown')
            message = cls.redact(payload.get('message', ''))
            return f'{timestamp} {Color.RED}[ERROR]{Color.RESET} {error_type}: {message}'
        
        elif event_type == 'status':
            status = payload.get('status', 'unknown')
            return f'{timestamp} {Color.YELLOW}[STATUS]{Color.RESET} {status}'
        
        else:
            return f'{timestamp} {Color.WHITE}[EVENT]{Color.RESET} {event_type}: {payload}'


class IPCLogger:
    """Connect to IPC server and log events."""
    
    def __init__(self, socket_path: Optional[str] = None, host: str = '127.0.0.1', port: Optional[int] = None):
        self.socket_path = socket_path
        self.host = host
        self.port = port
        self._running = False
        self._reader = None
        self._writer = None
    
    def parse_address(self, address: str) -> None:
        """Parse address string."""
        if address.startswith('unix://'):
            self.socket_path = address[7:]
            self.port = None
        elif address.startswith('tcp://'):
            rest = address[6:]
            if ':' in rest:
                host, port = rest.rsplit(':', 1)
                self.host = host
                self.port = int(port)
            else:
                self.host = rest
                self.port = None
    
    async def connect(self) -> bool:
        """Connect to IPC server."""
        try:
            if self.socket_path:
                self._reader, self._writer = await asyncio.open_unix_connection(self.socket_path)
            elif self.host and self.port:
                self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
            else:
                return False
            return True
        except (ConnectionError, FileNotFoundError, OSError):
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from IPC server."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None
    
    async def _receive_loop(self) -> None:
        """Receive and log events from server."""
        formatter = LogFormatter()
        
        try:
            while self._running and self._reader:
                line = await self._reader.readline()
                if not line:
                    break
                
                try:
                    event = json.loads(line.decode('utf-8').strip())
                    formatted = formatter.format_event(event)
                    
                    if formatted:
                        print(formatted, flush=True)
                except json.JSONDecodeError:
                    pass
                
        except (asyncio.CancelledError, ConnectionError, BrokenPipeError):
            pass
    
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat."""
        try:
            while self._running and self._writer:
                try:
                    self._writer.write(b'PING\n')
                    await self._writer.drain()
                except Exception:
                    pass
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass
    
    async def run(self) -> int:
        """Main loop."""
        self._running = True
        
        if not await self.connect():
            print(f'{Color.RED}Failed to connect to IPC server{Color.RESET}', file=sys.stderr)
            return 1
        
        try:
            receive_task = asyncio.create_task(self._receive_loop())
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            done, pending = await asyncio.wait(
                [receive_task, heartbeat_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            await self.disconnect()
        
        print(f'{Color.YELLOW}[LOGGER] Session ended{Color.RESET}', flush=True)
        return 0


async def main_async() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description='APRIL IPC Logger')
    parser.add_argument('--socket', '-s', help='Unix socket path')
    parser.add_argument('--host', '-H', default='127.0.0.1', help='TCP host')
    parser.add_argument('--port', '-p', type=int, help='TCP port')
    parser.add_argument('--address', '-a', help='Full address (unix://path or tcp://host:port)')
    parser.add_argument('--reconnect', '-r', action='store_true', help='Reconnect on disconnect')
    
    args = parser.parse_args()
    
    logger = IPCLogger()
    
    if args.address:
        logger.parse_address(args.address)
    elif args.socket:
        logger.socket_path = args.socket
    elif args.port:
        logger.host = args.host
        logger.port = args.port
    
    while True:
        exit_code = await logger.run()
        
        if not args.reconnect:
            return exit_code
        
        print(f'{Color.YELLOW}[LOGGER] Reconnecting in 5s...{Color.RESET}', flush=True)
        await asyncio.sleep(5)


def main() -> int:
    """Sync wrapper for main_async."""
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    sys.exit(main())
