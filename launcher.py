#!/usr/bin/env python3
"""
APRIL Launcher

Spawns TUI and logger tab using platform-specific methods.
"""

import asyncio
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


class TerminalLauncher:
    """Launches terminal windows/tabs for TUI and logger."""
    
    def __init__(self, single_pane: bool = False):
        self.single_pane = single_pane
        self._logger_process: Optional[subprocess.Popen] = None
        self._tui_process: Optional[subprocess.Popen] = None
        self._socket_path: Optional[str] = None
    
    def find_best_terminal(self) -> Optional[str]:
        """Find the best available terminal."""
        terminals = []
        
        if sys.platform == 'darwin':  # macOS
            terminals.extend(['Terminal', 'iTerm', 'Alacritty', 'kitty'])
        elif sys.platform == 'linux':  # Linux
            terminals.extend([
                'gnome-terminal', 'konsole', 'xfce4-terminal', 'mate-terminal',
                'xterm', 'urxvt', 'alacritty', 'kitty'
            ])
        elif sys.platform == 'win32':  # Windows
            terminals.extend(['wt.exe', 'cmd.exe', 'powershell.exe'])
        else:
            terminals.extend(['xterm', 'urxvt', 'alacritty', 'kitty'])
        
        for term in terminals:
            if self._which(term):
                return term
        
        return None
    
    def _which(self, cmd: str) -> Optional[str]:
        """Check if command exists in PATH."""
        try:
            result = subprocess.run(
                ['which', cmd],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return None
    
    def spawn_logger_via_socket(self) -> Optional[str]:
        """Spawn logger in separate terminal via socket."""
        # Create socket file
        self._socket_path = os.path.join(
            tempfile.gettempdir(),
            f'april_logger_{os.getpid()}.sock'
        )
        
        # Prepare command
        code_dir = os.getcwd()
        
        if sys.platform == 'darwin':
            # macOS: Use AppleScript to open new Terminal tab
            apple_script = f'''
tell application "Terminal"
    do script "cd {code_dir}; python3 -m core.ipc_logger"
end tell
'''
            cmd = ['osascript', '-e', apple_script]
            
        elif sys.platform == 'linux':
            terminal = self.find_best_terminal()
            if not terminal:
                return None
            
            cmd = [
                terminal, '--tab', '--title', 'APRIL Logger',
                '-e', 'bash', '-c',
                f'cd {code_dir}; python3 -m core.ipc_logger'
            ]
            
        elif sys.platform == 'win32':
            cmd = [
                'wt.exe', '--window', '0', 'tab',
                'python', '-m', 'core.ipc_logger'
            ]
            
        else:
            return None
        
        try:
            self._logger_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            time.sleep(1)
            return self._socket_path
        
        except Exception as e:
            print(f"Failed to spawn logger: {e}", file=sys.stderr)
            return None
    
    def cleanup(self):
        """Clean up spawned processes."""
        if self._logger_process:
            try:
                self._logger_process.terminate()
                self._logger_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._logger_process.kill()
            except Exception:
                pass
        
        if self._tui_process:
            try:
                self._tui_process.terminate()
                self._tui_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._tui_process.kill()
            except Exception:
                pass
        
        if self._socket_path and os.path.exists(self._socket_path):
            try:
                os.unlink(self._socket_path)
            except Exception:
                pass


async def run_launcher(
    single_pane: bool = False,
    no_spawn: bool = False,
    no_agent: bool = False,
    log_level: str = 'INFO'
) -> int:
    """
    Run the launcher.
    
    Args:
        single_pane: Run in single pane (no separate logger tab)
        no_spawn: Don't spawn new terminals, just run
        no_agent: Run without agent
        log_level: Log level for backend
    
    Returns:
        Exit code
    """
    launcher = TerminalLauncher(single_pane=single_pane)
    
    try:
        if no_spawn:
            os.environ['APRIL_LOG_LEVEL'] = log_level
            from core.textual_tui import main as tui_main
            tui_main()
            return 0
        
        if single_pane:
            # Run logger in current terminal
            print("Starting APRIL in single pane mode...")
            os.environ['APRIL_TUI_SHOW_LOGS'] = 'true'
            from core.textual_tui import main as tui_main
            tui_main()
            return 0
        
        # Spawn separate logger tab
        print("Starting APRIL with separate logger tab...")
        
        socket_path = launcher.spawn_logger_via_socket()
        if socket_path:
            os.environ['APRIL_IPC_SOCKET'] = socket_path
        
        os.environ['APRIL_LOG_LEVEL'] = log_level
        
        from core.textual_tui import main as tui_main
        launcher._tui_process = subprocess.Popen(
            [sys.executable, 'main.py', '--log-level', log_level],
            start_new_session=True
        )
        
        if launcher._tui_process:
            launcher._tui_process.wait()
        
        return 0
    
    except KeyboardInterrupt:
        return 0
    
    finally:
        launcher.cleanup()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="APRIL Launcher")
    parser.add_argument(
        '--single-pane', '-s',
        action='store_true',
        help='Run in single pane (no separate logger tab)'
    )
    parser.add_argument(
        '--no-spawn', '-n',
        action='store_true',
        help="Don't spawn new terminals, just run"
    )
    parser.add_argument(
        '--no-agent', '-a',
        action='store_true',
        help='Run without agent'
    )
    parser.add_argument(
        '--log-level', '-l',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Log level (default: INFO)'
    )
    parser.add_argument(
        '--theme',
        default='dark',
        choices=['dark', 'light'],
        help='Color theme'
    )
    
    args = parser.parse_args()
    
    exit_code = asyncio.run(
        run_launcher(
            single_pane=args.single_pane,
            no_spawn=args.no_spawn,
            no_agent=args.no_agent,
            log_level=args.log_level
        )
    )
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
