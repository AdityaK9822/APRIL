#!/usr/bin/env python3
"""
APRIL - An assistant with a body
Main entry point

Launches TUI as primary interface with backend CLI logger
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    """Main entry point"""
    # Parse launcher args
    parser = argparse.ArgumentParser(
        description="APRIL - An assistant with a body",
        add_help=False
    )
    
    parser.add_argument(
        '-h', '--help',
        action='store_true',
        help='Show this help message'
    )
    
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
        '--theme',
        default='dark',
        choices=['dark', 'light'],
        help='Color theme'
    )
    
    parser.add_argument(
        "--help-all",
        action='store_true',
        help='Show both launcher and TUI help'
    )
    
    args, remaining = parser.parse_known_args()
    
    # Show launcher help
    if args.help:
        print("""
APRIL - An assistant with a body

Usage: python main.py [launcher options] [tui options]

Launcher options:
  -h, --help              Show this launcher help
  -s, --single-pane       Run in single pane (no separate logger tab)
  -n, --no-spawn          Don't spawn new terminals, just run
  --theme LIGHT|DARK      Color theme (dark by default)

TUI options:
  -m, --model MODEL       Override model from config
  --log-level LEVEL       Backend logger level (default: INFO)
  --log-file FILE         Path to backend log file
  --max-iterations N      Maximum tool call iterations (default: 100)
  --show-logs             Show log panel in TUI (default: hidden)
  --no-agent              Run TUI without agent (testing mode)

Examples:
  python main.py                      # Run with separate logger tab
  python main.py --single-pane        # Run in single pane mode
  python main.py --no-agent           # Run TUI without agent
  python main.py -m mistral           # Use mistral model
  python main.py --log-level DEBUG    # Debug logging
        """)
        return 0
    
    # Parse TUI args
    tui_parser = argparse.ArgumentParser(
        description="APRIL - An assistant with a body",
        add_help=False
    )
    
    tui_parser.add_argument(
        "-m", "--model",
        help="Override model from config"
    )
    
    tui_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Backend logger level (default: INFO)"
    )
    
    tui_parser.add_argument(
        "--log-file",
        help="Path to backend log file"
    )
    
    tui_parser.add_argument(
        "--max-iterations",
        type=int,
        default=100,
        help="Maximum tool call iterations"
    )
    
    tui_parser.add_argument(
        "--show-logs",
        action="store_true",
        help="Show log panel in TUI (default: hidden)"
    )
    
    tui_parser.add_argument(
        "--no-agent",
        action="store_true",
        help="Run TUI without agent (testing mode)"
    )
    
    try:
        tui_args = tui_parser.parse_args(remaining)
    except SystemExit:
        tui_args = argparse.Namespace(
            model=None,
            log_level="INFO",
            log_file=None,
            max_iterations=100,
            show_logs=False,
            no_agent=False
        )
    
    # Setup backend logger
    from core.config import AgentConfig
    from core.logger import APRILLogger
    
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = tui_args.log_file or str(log_dir / "april_backend.log")
    os.environ['APRIL_LOG_LEVEL'] = tui_args.log_level
    os.environ['APRIL_TUI_SHOW_LOGS'] = 'true' if tui_args.show_logs else 'false'
    
    # Load configuration
    try:
        config = AgentConfig.from_env()
        
        if tui_args.model:
            config.model = tui_args.model
        
        config.max_iterations = tui_args.max_iterations
        
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        print(f"\nMake sure to create a .env file with:")
        print("  OPENAI_API_KEY=your_key")
        print("  OPENAI_API_BASE_URL=http://localhost:11434/v1")
        print("  OPENAI_MODEL=mistral")
        sys.exit(1)
    
    # Create agent
    if not tui_args.no_agent:
        from core.agent import AgentRuntime
        from core.backend_logger import BackendLoggerBridge
        
        agent = AgentRuntime(config)
        
        backend_logger = APRILLogger(
            name='april.backend',
            level=tui_args.log_level,
            log_file=log_file
        )
        
        if not hasattr(agent, 'backend_logger') or agent.backend_logger is None:
            agent.backend_logger = BackendLoggerBridge(backend_logger)
        
        # Log startup
        backend_logger.info("=" * 60)
        backend_logger.info("APRIL Backend Started")
        backend_logger.info("=" * 60)
        backend_logger.info(f"Model: {config.model}")
        backend_logger.info(f"Log Level: {tui_args.log_level}")
        backend_logger.info(f"Session: {agent.session.id}")
        backend_logger.info(f"Tools available: {list(agent.tool_map.keys())}")
        
        if agent.db:
            backend_logger.info(f"Memory database: {config.memory_db_path}")
        
    else:
        agent = None
        
        backend_logger = APRILLogger(
            name='april.backend',
            level=tui_args.log_level,
            log_file=log_file
        )
        
        backend_logger.info("=" * 60)
        backend_logger.info("APRIL Backend Started (No Agent)")
        backend_logger.info("=" * 60)
        backend_logger.info("Running in no-agent mode (TUI only)")
    
    # Run TUI
    import asyncio
    from core.textual_tui import APRILApp
    
    db = agent.db if agent else None
    app = APRILApp(agent=agent, db=db)
    
    try:
        app.run()
        
    except KeyboardInterrupt:
        if backend_logger:
            backend_logger.info("Shutdown requested by user")
        
    except Exception as e:
        if backend_logger:
            backend_logger.error(f"Error running TUI: {e}")
        raise
        
    finally:
        if backend_logger:
            backend_logger.info("APRIL Backend Stopped")
            backend_logger.info("=" * 60)


if __name__ == "__main__":
    main()
