"""
APRIL Event System

Typed events and event bus for decoupled agent-UI-logger communication.
"""

import asyncio
import threading
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Any, TypeVar, Generic


T = TypeVar('T')


@dataclass
class Event(Generic[T]):
    """Base event type"""
    event_type: str
    payload: T = None
    timestamp: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


@dataclass
class MessageDelta:
    """Streaming token from model"""
    content: str
    is_assistant: bool
    is_complete: bool = False


@dataclass
class MessageStart:
    """Start of a new message"""
    is_assistant: bool
    message_id: str


@dataclass
class MessageDone:
    """Message sending/completion done"""
    message_id: str
    full_content: str
    is_assistant: bool


@dataclass
class ToolCallStart:
    """Tool execution starting"""
    tool_name: str
    tool_args: Dict[str, Any]
    tool_call_id: str


@dataclass
class ToolCallOutput:
    """Tool stdout/stderr output"""
    tool_call_id: str
    text: str
    is_error: bool = False


@dataclass
class ToolCallDone:
    """Tool execution completed"""
    tool_name: str
    result: str
    tool_call_id: str
    success: bool


@dataclass
class LogEvent:
    """Logger output"""
    level: str
    source: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ErrorEvent:
    """Error occurred"""
    error_type: str
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class StatusEvent:
    """Agent status change"""
    status: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionEvent:
    """Session management"""
    event_type: str
    session_id: str


EventCallback = Callable[[Event[Any]], None]


class EventBus:
    """
    Thread-safe event bus for decoupled communication.
    """
    
    def __init__(self):
        self._callbacks: Dict[str, List[EventCallback]] = {}
        self._async_callbacks: Dict[str, List[EventCallback]] = {}
        self._lock = threading.Lock()
        self._event_history: List[Event[Any]] = []
        self._max_history = 1000
        self._sub_ids: Dict[str, List[str]] = {}
        self._all_sub_ids: Dict[str, EventCallback] = {}
    
    def subscribe(self, event_type: str, callback: EventCallback) -> str:
        with self._lock:
            if event_type not in self._callbacks:
                self._callbacks[event_type] = []
                self._sub_ids[event_type] = []
            sub_id = str(uuid.uuid4())[:8]
            self._callbacks[event_type].append(callback)
            self._sub_ids[event_type].append(sub_id)
            self._all_sub_ids[sub_id] = callback
            return sub_id
    
    def subscribe_async(self, event_type: str, callback: EventCallback) -> str:
        with self._lock:
            if event_type not in self._async_callbacks:
                self._async_callbacks[event_type] = []
            if event_type not in self._sub_ids:
                self._sub_ids[event_type] = []
            sub_id = str(uuid.uuid4())[:8]
            self._async_callbacks[event_type].append(callback)
            self._sub_ids[event_type].append(sub_id)
            self._all_sub_ids[sub_id] = callback
            return sub_id
    
    def unsubscribe(self, sub_id: str) -> bool:
        with self._lock:
            callback = self._all_sub_ids.pop(sub_id, None)
            if callback is None:
                return False
            
            for event_type, callbacks in list(self._callbacks.items()):
                if callback in callbacks:
                    callbacks.remove(callback)
                    if event_type in self._sub_ids:
                        self._sub_ids[event_type] = [s for s in self._sub_ids[event_type] if s != sub_id]
                    if not callbacks:
                        self._callbacks.pop(event_type, None)
                        self._sub_ids.pop(event_type, None)
                    return True
            
            for event_type, callbacks in list(self._async_callbacks.items()):
                if callback in callbacks:
                    callbacks.remove(callback)
                    if event_type in self._sub_ids:
                        self._sub_ids[event_type] = [s for s in self._sub_ids[event_type] if s != sub_id]
                    if not callbacks:
                        self._async_callbacks.pop(event_type, None)
                    return True
            
            return True
    
    def emit(self, event: Event[Any]) -> None:
        with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history:]
        
        with self._lock:
            sync_callbacks = list(self._callbacks.get(event.event_type, []))
        
        for callback in sync_callbacks:
            try:
                callback(event)
            except Exception:
                pass
        
        with self._lock:
            async_callbacks = list(self._async_callbacks.get(event.event_type, []))
        
        for callback in async_callbacks:
            try:
                asyncio.create_task(callback(event))
            except Exception:
                pass
    
    def emit_message_delta(self, content: str, is_assistant: bool, is_complete: bool = False) -> None:
        delta = MessageDelta(content=content, is_assistant=is_assistant, is_complete=is_complete)
        self.emit(Event(event_type="message.delta", payload=delta))
    
    def emit_message_start(self, is_assistant: bool) -> str:
        msg_id = str(uuid.uuid4())[:8]
        self.emit(Event(event_type="message.start", payload=MessageStart(is_assistant=is_assistant, message_id=msg_id)))
        return msg_id
    
    def emit_message_done(self, message_id: str, full_content: str, is_assistant: bool) -> None:
        self.emit(Event(event_type="message.done", payload=MessageDone(
            message_id=message_id,
            full_content=full_content,
            is_assistant=is_assistant
        )))
    
    def emit_tool_call_start(self, tool_name: str, tool_args: Dict[str, Any], tool_call_id: str) -> None:
        self.emit(Event(event_type="tool_call.start", payload=ToolCallStart(
            tool_name=tool_name,
            tool_args=tool_args,
            tool_call_id=tool_call_id
        )))
    
    def emit_tool_call_output(self, tool_call_id: str, text: str, is_error: bool = False) -> None:
        self.emit(Event(event_type="tool_call.output", payload=ToolCallOutput(
            tool_call_id=tool_call_id,
            text=text,
            is_error=is_error
        )))
    
    def emit_tool_call_done(self, tool_name: str, result: str, tool_call_id: str, success: bool) -> None:
        self.emit(Event(event_type="tool_call.done", payload=ToolCallDone(
            tool_name=tool_name,
            result=result,
            tool_call_id=tool_call_id,
            success=success
        )))
    
    def emit_log(self, level: str, source: str, message: str) -> None:
        self.emit(Event(event_type="log", payload=LogEvent(
            level=level,
            source=source,
            message=message
        )))
    
    def emit_error(self, error_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.emit(Event(event_type="error", payload=ErrorEvent(
            error_type=error_type,
            message=message,
            details=details
        )))
    
    def emit_status(self, status: str, metadata: Dict[str, Any] = None) -> None:
        self.emit(Event(event_type="status", payload=StatusEvent(
            status=status,
            metadata=metadata or {}
        )))
    
    def get_history(self, event_type: Optional[str] = None, limit: int = 100) -> List[Event[Any]]:
        with self._lock:
            if event_type:
                history = [e for e in self._event_history if e.event_type == event_type]
            else:
                history = list(self._event_history)
            return history[-limit:]
    
    def clear_history(self) -> None:
        with self._lock:
            self._event_history.clear()


_global_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus


def reset_event_bus() -> None:
    global _global_bus
    _global_bus = None
