"""
Tests for APRIL Event System
"""

import unittest
import time
import asyncio
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.events import (
    EventBus, get_event_bus, reset_event_bus,
    Event, MessageDelta, LogEvent, ErrorEvent,
    ToolCallStart, ToolCallOutput, ToolCallDone,
    StatusEvent, SessionEvent
)


class TestEventTypes(unittest.TestCase):
    """Test event dataclasses"""
    
    def test_message_delta(self):
        """Test MessageDelta event - note: timestamp is in Event wrapper"""
        delta = MessageDelta(content="hello", is_assistant=True, is_complete=False)
        self.assertEqual(delta.content, "hello")
        self.assertTrue(delta.is_assistant)
        self.assertFalse(delta.is_complete)
    
    def test_message_delta_wrapper(self):
        """Test MessageDelta wrapped in Event"""
        delta = MessageDelta(content="hello", is_assistant=True)
        event = Event(event_type="message.delta", payload=delta)
        self.assertIsInstance(event.timestamp, datetime)
        self.assertEqual(event.payload.content, "hello")
    
    def test_log_event(self):
        """Test LogEvent"""
        event = LogEvent(level="INFO", source="agent", message="test message")
        self.assertEqual(event.level, "INFO")
        self.assertEqual(event.source, "agent")
        self.assertEqual(event.message, "test message")
        self.assertIsInstance(event.timestamp, datetime)
    
    def test_error_event(self):
        """Test ErrorEvent"""
        event = ErrorEvent(
            error_type="ConnectionError",
            message="Failed to connect",
            details={"host": "localhost", "port": 8080}
        )
        self.assertEqual(event.error_type, "ConnectionError")
        self.assertEqual(event.message, "Failed to connect")
        self.assertEqual(event.details["host"], "localhost")
    
    def test_tool_call_start(self):
        """Test ToolCallStart"""
        event = ToolCallStart(
            tool_name="shell_execute",
            tool_args={"command": "ls", "timeout": 30},
            tool_call_id="call_123"
        )
        self.assertEqual(event.tool_name, "shell_execute")
        self.assertEqual(event.tool_args["command"], "ls")
        self.assertEqual(event.tool_call_id, "call_123")
    
    def test_tool_call_output(self):
        """Test ToolCallOutput"""
        event = ToolCallOutput(
            tool_call_id="call_123",
            text="stdout output",
            is_error=False
        )
        self.assertEqual(event.tool_call_id, "call_123")
        self.assertEqual(event.text, "stdout output")
        self.assertFalse(event.is_error)
    
    def test_tool_call_done(self):
        """Test ToolCallDone"""
        event = ToolCallDone(
            tool_name="shell_execute",
            result="Output: success",
            tool_call_id="call_123",
            success=True
        )
        self.assertEqual(event.tool_name, "shell_execute")
        self.assertEqual(event.result, "Output: success")
        self.assertTrue(event.success)
    
    def test_full_event(self):
        """Test full Event wrapper"""
        delta = MessageDelta(content="test", is_assistant=True)
        event = Event(event_type="message.delta", payload=delta)
        
        self.assertEqual(event.event_type, "message.delta")
        self.assertIsInstance(event.payload, MessageDelta)
        self.assertEqual(event.payload.content, "test")
        self.assertIsInstance(event.timestamp, datetime)


class TestEventBus(unittest.TestCase):
    """Test EventBus"""
    
    def setUp(self):
        """Reset global event bus before each test"""
        reset_event_bus()
        self.bus = get_event_bus()
    
    def tearDown(self):
        """Clean up after each test"""
        reset_event_bus()
    
    def test_subscribe_and_emit(self):
        """Test basic subscribe and emit"""
        received = []
        
        def callback(event):
            received.append(event)
        
        sub_id = self.bus.subscribe("test.event", callback)
        self.assertIsNotNone(sub_id)
        
        event = Event(event_type="test.event", payload={"data": "test"})
        self.bus.emit(event)
        
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].event_type, "test.event")
        self.assertEqual(received[0].payload["data"], "test")
    
    def test_convenience_methods(self):
        """Test convenience methods like emit_message_delta"""
        received = []
        
        def callback(event):
            received.append(event)
        
        self.bus.subscribe("message.delta", callback)
        self.bus.emit_message_delta("hello", is_assistant=True)
        
        self.assertEqual(len(received), 1)
        delta = received[0].payload
        self.assertEqual(delta.content, "hello")
        self.assertTrue(delta.is_assistant)
    
    def test_event_history(self):
        """Test event history tracking"""
        self.bus.emit(Event(event_type="test.event", payload="one"))
        self.bus.emit(Event(event_type="test.event", payload="two"))
        self.bus.emit(Event(event_type="other.event", payload="three"))
        
        history = self.bus.get_history()
        self.assertEqual(len(history), 3)
        
        test_events = self.bus.get_history("test.event")
        self.assertEqual(len(test_events), 2)
    
    def test_clear_history(self):
        """Test clearing history"""
        self.bus.emit(Event(event_type="test.event", payload="one"))
        self.bus.emit(Event(event_type="test.event", payload="two"))
        
        self.bus.clear_history()
        
        self.assertEqual(len(self.bus.get_history()), 0)
    
    def test_unsubscribe(self):
        """Test unsubscribing"""
        received = []
        
        def callback(event):
            received.append(event)
        
        sub_id = self.bus.subscribe("test.event", callback)
        self.bus.emit(Event(event_type="test.event", payload="first"))
        
        self.assertTrue(self.bus.unsubscribe(sub_id))
        
        self.bus.emit(Event(event_type="test.event", payload="second"))
        
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].payload, "first")
    
    def test_multiple_subscribers(self):
        """Test multiple subscribers for same event type"""
        received1 = []
        received2 = []
        
        def callback1(event):
            received1.append(event)
        
        def callback2(event):
            received2.append(event)
        
        self.bus.subscribe("multi.event", callback1)
        self.bus.subscribe("multi.event", callback2)
        
        self.bus.emit(Event(event_type="multi.event", payload="test"))
        
        self.assertEqual(len(received1), 1)
        self.assertEqual(len(received2), 1)
    
    def test_error_handler_dont_crash_others(self):
        """Test that one failing handler doesn't crash others"""
        received = []
        
        def bad_callback(event):
            raise Exception("I fail!")
        
        def good_callback(event):
            received.append(event)
        
        self.bus.subscribe("error.event", bad_callback)
        self.bus.subscribe("error.event", good_callback)
        
        self.bus.emit(Event(event_type="error.event", payload="test"))
        
        self.assertEqual(len(received), 1)


class TestEventBusIntegration(unittest.TestCase):
    """Integration tests"""
    
    def setUp(self):
        reset_event_bus()
    
    def tearDown(self):
        reset_event_bus()
    
    def test_agent_integration(self):
        """Test that agent can use event bus"""
        from core.agent import AgentRuntime
        from core.config import AgentConfig
        
        config = AgentConfig(
            model="test-model",
            api_key="test-key",
            api_base_url="http://localhost:11434/v1"
        )
        
        agent = AgentRuntime(config)
        
        self.assertIsNotNone(agent)
        self.assertIsNotNone(agent._event_bus)
        
        events_received = []
        
        def event_handler(event):
            events_received.append(event)
        
        agent._event_bus.subscribe("log", event_handler)
        
        self.assertTrue(hasattr(agent, 'run'))
        self.assertTrue(hasattr(agent, 'run_streaming'))


if __name__ == '__main__':
    unittest.main()
