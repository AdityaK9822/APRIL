"""
Backend Logger Bridge

Connects agent runtime to CLI backend logger for event monitoring
"""

from typing import Dict, Any, Optional, Callable
from .logger import APRILLogger
import threading


class BackendLoggerBridge:
    """
    Bridge between agent runtime and backend logger
    
    Captures agent events and logs them to backend:
    - Memory updates
    - Tool executions
    - LLM API calls
    - Session events
    """
    
    def __init__(self, logger: APRILLogger, real_time_callback: Optional[Callable] = None):
        """
        Initialize backend logger bridge
        
        Args:
            logger: APRILLogger instance for backend output
            real_time_callback: Optional callback for real-time log updates
        """
        self.logger = logger
        self.real_time_callback = real_time_callback
        self._callback_lock = threading.Lock()
    
    def log_memory_event(self, event_type: str, details: Dict[str, Any], real_time: bool = False):
        """
        Log memory system events
        
        Args:
            event_type: Type of memory event
            details: Event details
            real_time: If True, send to real-time callback
        """
        self.logger.info(f"[MEMORY] {event_type}: {details}")
        
        if real_time:
            with self._callback_lock:
                if self.real_time_callback:
                    self.real_time_callback(f"[MEMORY] {event_type}", "INFO")
    
    def log_tool_execution(self, tool_name: str, args: Dict, result: str, real_time: bool = False):
        """
        Log tool execution events
        
        Args:
            tool_name: Name of executed tool
            args: Tool arguments
            result: Tool execution result
            real_time: If True, send to real-time callback
        """
        self.logger.info(f"[TOOL] Calling: {tool_name}")
        self.logger.debug(f"[TOOL] Args: {args}")
        self.logger.debug(f"[TOOL] Result: {result[:200]}")
        
        if real_time:
            with self._callback_lock:
                if self.real_time_callback:
                    self.real_time_callback(f"[TOOL] {tool_name}", "INFO")
    
    def log_llm_request(self, model: str, message_count: int, prompt_tokens: int = None, real_time: bool = False):
        """
        Log LLM API request events
        
        Args:
            model: Model name
            message_count: Number of messages in context
            prompt_tokens: Optional token count
            real_time: If True, send to real-time callback
        """
        msg = f"[LLM] Request to {model} ({message_count} messages)"
        if prompt_tokens:
            msg += f" - {prompt_tokens} tokens"
        self.logger.info(msg)
        
        if real_time:
            with self._callback_lock:
                if self.real_time_callback:
                    self.real_time_callback(f"[LLM] Request", "INFO")
    
    def log_llm_response(self, model: str, response_tokens: int = None, real_time: bool = False):
        """
        Log LLM API response events
        
        Args:
            model: Model name
            response_tokens: Optional response token count
            real_time: If True, send to real-time callback
        """
        msg = f"[LLM] Response from {model}"
        if response_tokens:
            msg += f" - {response_tokens} tokens"
        self.logger.info(msg)
        
        if real_time:
            with self._callback_lock:
                if self.real_time_callback:
                    self.real_time_callback(f"[LLM] Response", "INFO")
    
    def log_session_event(self, event_type: str, session_id: str = None, real_time: bool = False):
        """
        Log session events
        
        Args:
            event_type: Type of session event
            session_id: Session identifier
            real_time: If True, send to real-time callback
        """
        msg = f"[SESSION] {event_type}"
        if session_id:
            msg += f" - ID: {session_id}"
        self.logger.info(msg)
        
        if real_time:
            with self._callback_lock:
                if self.real_time_callback:
                    self.real_time_callback(f"[SESSION] {event_type}", "INFO")
    
    def set_real_time_callback(self, callback: Callable) -> None:
        """
        Set real-time callback for TUI updates
        
        Args:
            callback: Function to call with (message, level)
        """
        with self._callback_lock:
            self.real_time_callback = callback
    
    def log_user_message(self, message: str):
        """
        Log incoming user message
        
        Args:
            message: User message (truncated for privacy)
        """
        truncated = message[:100] + "..." if len(message) > 100 else message
        self.logger.info(f"[USER] {truncated}")
        
        # Call real-time callback if available
        with self._callback_lock:
            if self.real_time_callback:
                self.real_time_callback(f"[USER] {truncated}", "INFO")
    
    def log_agent_response(self, response: str):
        """
        Log agent response
        
        Args:
            response: Agent response (truncated)
        """
        truncated = response[:100] + "..." if len(response) > 100 else response
        self.logger.info(f"[AGENT] {truncated}")
        
        # Call real-time callback if available
        with self._callback_lock:
            if self.real_time_callback:
                self.real_time_callback(f"[AGENT] {truncated}", "INFO")
    
    def log_error(self, error_type: str, message: str):
        """
        Log error events
        
        Args:
            error_type: Type of error
            message: Error message
        """
        self.logger.error(f"[ERROR] {error_type}: {message}")
