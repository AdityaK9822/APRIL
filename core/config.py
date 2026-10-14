"""
APRIL Agent Configuration

Handles loading configuration from environment variables and YAML files.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import os
import yaml
import logging


@dataclass
class TUIConfig:
    """
    TUI (Terminal User Interface) configuration
    
    Attributes:
        enabled: Enable TUI mode
        show_logs: Show log panel in TUI
        log_height: Height of log panel in lines
        message_history_size: Max messages to display
        color_scheme: Color scheme (dark/light/custom)
        refresh_rate: Screen refresh rate in seconds
    """
    enabled: bool = False
    show_logs: bool = False
    log_height: int = 4
    message_history_size: int = 1000
    color_scheme: str = "dark"
    refresh_rate: float = 0.1


@dataclass
class LoggingConfig:
    """
    Logging configuration
    
    Attributes:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        file: Path to log file (None for console only)
        max_size: Max log file size in bytes
        backup_count: Number of backup files to keep
        format: Log message format
        date_format: Date format for logs
    """
    level: str = "WARNING"  # Default: suppress INFO/DEBUG
    file: Optional[str] = None
    max_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"


@dataclass
class MemoryConfig:
    """
    Memory system configuration
    
    Attributes:
        enabled: Enable memory storage
        db_path: Path to memory database
        extraction_model: Model for memory extraction
        cleanup_delay: Minutes before cleanup of processed messages
        max_context: Max memories to include in context
    """
    enabled: bool = True
    db_path: str = "./data/april_memory.db"
    extraction_model: str = "gemma4:31b-cloud"
    cleanup_delay: int = 60
    max_context: int = 10


@dataclass
class AgentConfig:
    """
    Agent configuration

    Attributes:
        model: LLM model name
        api_key: OpenAI API key
        api_base_url: API endpoint URL
        max_context_length: Maximum context window size
        temperature: Sampling temperature
        max_iterations: Maximum agent loop iterations
        memory: Memory system configuration
        tui: TUI configuration
        logging: Logging configuration
    """

    model: str
    api_key: str
    api_base_url: str
    max_context_length: int = 128000
    temperature: float = 0.7
    max_iterations: int = 100
    
    # Memory configuration (backward compatible)
    memory_enabled: bool = True
    memory_db_path: str = "./data/april_memory.db"
    memory_extraction_model: str = "gemma4:31b-cloud"
    memory_cleanup_delay: int = 60
    memory_max_context: int = 10
    
    # New structured configs
    memory: Optional[MemoryConfig] = None
    tui: Optional[TUIConfig] = None
    logging: Optional[LoggingConfig] = None
    
    def __post_init__(self):
        """Initialize defaults from environment if not set"""
        # Initialize memory config from old fields if not provided
        if self.memory is None:
            self.memory = MemoryConfig(
                enabled=self.memory_enabled,
                db_path=self.memory_db_path,
                extraction_model=self.memory_extraction_model,
                cleanup_delay=self.memory_cleanup_delay,
                max_context=self.memory_max_context
            )
        
        # Initialize TUI config from environment
        if self.tui is None:
            tui_enabled = os.getenv('APRIL_TUI_ENABLED', 'false').lower() == 'true'
            tui_show_logs = os.getenv('APRIL_TUI_SHOW_LOGS', 'false').lower() == 'true'
            self.tui = TUIConfig(
                enabled=tui_enabled,
                show_logs=tui_show_logs
            )
        
        # Initialize logging config from environment
        if self.logging is None:
            log_level = os.getenv('APRIL_LOG_LEVEL', 'WARNING').upper()
            log_file = os.getenv('APRIL_LOG_FILE', None)
            
            self.logging = LoggingConfig(
                level=log_level,
                file=log_file
            )
        
        # Also update old fields for backward compatibility
        self.memory_enabled = self.memory.enabled
        self.memory_db_path = self.memory.db_path
        self.memory_extraction_model = self.memory.extraction_model
        self.memory_cleanup_delay = self.memory.cleanup_delay
        self.memory_max_context = self.memory.max_context

    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> 'AgentConfig':
        """
        Load configuration from environment variables
        
        Args:
            env_file: Optional path to .env file
            
        Returns:
            Configured AgentConfig instance
        """
        # Load .env file if specified
        if env_file and Path(env_file).exists():
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        # Get required values from environment
        api_key = os.getenv('OPENAI_API_KEY', '')
        api_base_url = os.getenv('OPENAI_API_BASE_URL', '')
        model = os.getenv('OPENAI_MODEL', 'gemma4:31b-cloud')
        
        # Create config
        config = cls(
            model=model,
            api_key=api_key,
            api_base_url=api_base_url
        )
        
        return config
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'AgentConfig':
        """
        Load configuration from YAML file
        
        Args:
            yaml_path: Path to YAML configuration file
            
        Returns:
            Configured AgentConfig instance
        """
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Extract sub-configs
        memory_data = data.get('memory', {})
        tui_data = data.get('tui', {})
        logging_data = data.get('logging', {})
        
        # Create sub-configs
        memory = MemoryConfig(**memory_data) if memory_data else None
        tui = TUIConfig(**tui_data) if tui_data else None
        logging = LoggingConfig(**logging_data) if logging_data else None
        
        # Extract top-level config
        config_data = {k: v for k, v in data.items() 
                      if k not in ['memory', 'tui', 'logging']}
        
        # Create main config
        config = cls(
            **config_data,
            memory=memory,
            tui=tui,
            logging=logging
        )
        
        return config


# Module-level logger
def setup_logging(config: LoggingConfig) -> logging.Logger:
    """
    Set up logging based on configuration
    
    Args:
        config: LoggingConfig instance
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger('april')
    
    # Set level
    level = getattr(logging, config.level.upper(), logging.WARNING)
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(config.format, config.date_format)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if config.file:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            config.file,
            maxBytes=config.max_size,
            backupCount=config.backup_count
        )
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(config.format, config.date_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


# Global logger instance
_global_logger = None


def get_logger(name: str = 'april') -> logging.Logger:
    """
    Get global logger instance
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    global _global_logger
    
    if _global_logger is None:
        # Try to get from config if available
        if 'AGENT_CONFIG' in globals():
            _global_logger = setup_logging(AGENT_CONFIG.logging)
        else:
            # Default config
            default_config = LoggingConfig()
            _global_logger = setup_logging(default_config)
    
    return logging.getLogger(name)


# Set up module-level logger on import
try:
    default_config = LoggingConfig()
    _global_logger = setup_logging(default_config)
except Exception:
    # Fallback if environment not set up
    _global_logger = logging.getLogger('april')
    _global_logger.setLevel(logging.WARNING)
