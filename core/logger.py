"""
APRIL Logging Module

Structured logging with levels, file rotation, and configurable output.
"""

import logging
import os
from typing import Optional
from pathlib import Path


class APRILLogger:
    """
    Structured logger for APRIL system
    
    Features:
    - Logging levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - File output with rotation
    - Console output
    - Custom formatting
    """
    
    # Log level names
    LEVELS = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    def __init__(
        self,
        name: str = 'april',
        level: str = 'WARNING',
        log_file: Optional[str] = None,
        max_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        date_format: str = "%Y-%m-%d %H:%M:%S"
    ):
        """
        Initialize APRILLogger
        
        Args:
            name: Logger name
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Path to log file (None for console only)
            max_size: Max log file size in bytes
            backup_count: Number of backup files to keep
            format: Log message format
            date_format: Date format
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # Create formatter
        self.formatter = logging.Formatter(format, date_format)
        
        # Console handler
        self.console_handler = logging.StreamHandler()
        self.console_handler.setLevel(self.LEVELS.get(level.upper(), logging.WARNING))
        self.console_handler.setFormatter(self.formatter)
        self.logger.addHandler(self.console_handler)
        
        # File handler (optional)
        if log_file:
            self.log_file = Path(log_file)
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            
            from logging.handlers import RotatingFileHandler
            self.file_handler = RotatingFileHandler(
                str(self.log_file),
                maxBytes=max_size,
                backupCount=backup_count
            )
            self.file_handler.setLevel(self.LEVELS.get(level.upper(), logging.WARNING))
            self.file_handler.setFormatter(self.formatter)
            self.logger.addHandler(self.file_handler)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(self._format_message(message, kwargs))
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(self._format_message(message, kwargs))
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(self._format_message(message, kwargs))
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(self._format_message(message, kwargs))
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self.logger.critical(self._format_message(message, kwargs))
    
    def _format_message(self, message: str, kwargs: dict) -> str:
        """Format message with optional kwargs"""
        if not kwargs:
            return message
        return f"{message} | " + " | ".join(f"{k}={v}" for k, v in kwargs.items())
    
    def set_level(self, level: str):
        """Change log level"""
        level_num = self.LEVELS.get(level.upper(), logging.WARNING)
        self.console_handler.setLevel(level_num)
        if hasattr(self, 'file_handler'):
            self.file_handler.setLevel(level_num)
        self.logger.setLevel(level_num)
    
    def get_level(self) -> str:
        """Get current log level"""
        return logging.getLevelName(self.console_handler.level)


# Global logger instance
_global_logger: Optional[APRILLogger] = None


def get_logger(
    name: str = 'april',
    level: Optional[str] = None,
    log_file: Optional[str] = None
) -> APRILLogger:
    """
    Get global logger instance
    
    Args:
        name: Logger name
        level: Log level (optional, uses env var if not provided)
        log_file: Log file path (optional)
        
    Returns:
        APRILLogger instance
    """
    global _global_logger
    
    if _global_logger is None:
        # Get level from environment
        if level is None:
            level = os.getenv('APRIL_LOG_LEVEL', 'WARNING')
        
        # Get log file from environment
        if log_file is None:
            log_file = os.getenv('APRIL_LOG_FILE')
        
        _global_logger = APRILLogger(
            name=name,
            level=level,
            log_file=log_file
        )
    
    return _global_logger


def setup_from_config(config: dict) -> APRILLogger:
    """
    Setup logger from configuration dict
    
    Args:
        config: Configuration dict with logging settings
        
    Returns:
        Configured APRILLogger instance
    """
    logging_config = config.get('logging', {})
    
    return APRILLogger(
        name=logging_config.get('name', 'april'),
        level=logging_config.get('level', 'WARNING'),
        log_file=logging_config.get('file'),
        max_size=logging_config.get('max_size', 10 * 1024 * 1024),
        backup_count=logging_config.get('backup_count', 5),
        format=logging_config.get('format', "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        date_format=logging_config.get('date_format', "%Y-%m-%d %H:%M:%S")
    )


# Convenience functions
def debug(message: str, **kwargs):
    """Debug log convenience function"""
    get_logger().debug(message, **kwargs)


def info(message: str, **kwargs):
    """Info log convenience function"""
    get_logger().info(message, **kwargs)


def warning(message: str, **kwargs):
    """Warning log convenience function"""
    get_logger().warning(message, **kwargs)


def error(message: str, **kwargs):
    """Error log convenience function"""
    get_logger().error(message, **kwargs)


def critical(message: str, **kwargs):
    """Critical log convenience function"""
    get_logger().critical(message, **kwargs)