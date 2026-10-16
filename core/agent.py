"""
APRIL Agent Runtime

The core agent loop: manage context, call LLM, process tool calls.
"""

from typing import List, Dict, Optional, Callable, AsyncGenerator, Any
import json
import threading
import os
from openai import OpenAI

from .config import AgentConfig
from .session import Session
from .database import MemoryDatabase
from .memory_extractor import MemoryExtractor
from .logger import APRILLogger, get_logger
from .backend_logger import BackendLoggerBridge
from .events import get_event_bus, Event, LogEvent, ErrorEvent, StatusEvent
from tools.shell import ShellTool


class AgentRuntime:
    """
    The core agent runtime
    
    Manages conversation with an LLM, processes tool calls, and
    maintains session state.
    """
    
    def __init__(self, config: AgentConfig, tools: Optional[List] = None):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.api_base_url
        )
        
        # Initialize memory system
        self.db = None
        self.extractor = None
        if config.memory_enabled:
            try:
                self.db = MemoryDatabase(config.memory_db_path)
                self.extractor = MemoryExtractor(model=config.memory_extraction_model)
                self.extractor._client = self.client
            except Exception as e:
                self._emit_error("memory_init", str(e))
        
        # Create session with database
        self.session = Session(db=self.db)
        
        # Initialize tools
        if tools is None:
            self.tools = [ShellTool()]
        else:
            self.tools = tools
        
        # Build tool schema list for API
        self.tool_schemas = [t.schema() for t in self.tools]
        
        # Build tool name -> instance map
        self.tool_map = {t.name: t for t in self.tools}
        
        # Event bus
        self._event_bus = get_event_bus()
    
    def _emit_error(self, error_type: str, message: str, details: Dict = None):
        """Emit error event."""
        self._event_bus.emit(ErrorEvent(error_type=error_type, message=message, details=details))
    
    def _emit_status(self, status: str, metadata: Dict = None):
        """Emit status event."""
        self._event_bus.emit(StatusEvent(status=status, metadata=metadata or {}))
    
    def _process_tool_calls(self, tool_calls: List) -> List[Dict]:
        """Process tool calls from LLM response."""
        results = []
        
        for call in tool_calls:
            tool_name = call.function.name
            tool_args = json.loads(call.function.arguments)
            
            if tool_name not in self.tool_map:
                results.append({
                    'tool_call_id': call.id,
                    'role': 'tool',
                    'name': tool_name,
                    'content': f"Error: Unknown tool '{tool_name}'"
                })
                continue
            
            tool = self.tool_map[tool_name]
            
            try:
                if tool_name == 'shell_execute':
                    result = tool.execute(
                        command=tool_args.get('command'),
                        timeout=tool_args.get('timeout', 30)
                    )
                else:
                    result = tool.execute(**tool_args)
                
                results.append({
                    'tool_call_id': call.id,
                    'role': 'tool',
                    'name': tool_name,
                    'content': str(result)
                })
            
            except Exception as e:
                results.append({
                    'tool_call_id': call.id,
                    'role': 'tool',
                    'name': tool_name,
                    'content': f'Error executing tool: {str(e)}'
                })
        
        return results
    
    def run(self, user_input: str, max_iterations: Optional[int] = None) -> str:
        """Synchronous run method for backward compatibility."""
        if max_iterations is None:
            max_iterations = self.config.max_iterations
        
        # Log user message
        truncated = user_input[:100] + "..." if len(user_input) > 100 else user_input
        self._event_bus.emit(LogEvent(level="INFO", source="user", message=truncated))
        
        # Augment context with relevant memories
        self._augment_context_with_memories(user_input)
        
        # Save user message
        self._save_conversation_turn('user', user_input)
        
        # Add user message to context
        self.session.add_message('user', user_input)
        
        # Agent loop
        iterations = 0
        while iterations < max_iterations:
            # Log LLM request
            self._event_bus.emit(LogEvent(level="INFO", source="llm", message=f"Request to {self.config.model} ({len(self.session.context)} messages)"))
            
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=self.session.context,
                tools=self.tool_schemas,
                temperature=self.config.temperature
            )
            
            message = response.choices[0].message
            
            # Log LLM response
            self._event_bus.emit(LogEvent(level="INFO", source="llm", message=f"Response from {self.config.model}"))
            
            # Check if we need to process tool calls
            if message.tool_calls:
                # Add assistant message with tool calls
                self.session.context.append({
                    'role': 'assistant',
                    'content': message.content,
                    'tool_calls': [
                        {
                            'id': tc.id,
                            'type': 'function',
                            'function': {
                                'name': tc.function.name,
                                'arguments': tc.function.arguments
                            }
                        } for tc in message.tool_calls
                    ]
                })
                
                # Process tool calls
                tool_results = self._process_tool_calls(message.tool_calls)
                
                # Log tool executions
                for result in tool_results:
                    tool_name = result.get('name', 'unknown')
                    self._event_bus.emit(LogEvent(level="INFO", source="tool", message=f"Calling: {tool_name}"))
                
                # Add tool results to context
                for result in tool_results:
                    self.session.context.append(result)
                
                iterations += 1
                continue
            
            # No tool calls - we have a final response
            self.session.add_message('assistant', message.content or '')
            final_response = message.content or ''
            
            # Save assistant response
            if final_response:
                self._save_conversation_turn('assistant', final_response)
                self._extract_and_store_memories()
            
            # Log agent response
            self._event_bus.emit(LogEvent(level="INFO", source="agent", message=final_response[:100] + "..." if len(final_response) > 100 else final_response))
            
            return final_response
        
        # Max iterations reached
        return f'Reached maximum iterations ({max_iterations}) without completing. Last context length: {len(self.session.context)} messages.'
    
    def _save_conversation_turn(self, role: str, content: str):
        """Save conversation turn to database."""
        if self.db:
            self.db.save_message(self.session.id, role, content)
    
    def _augment_context_with_memories(self, user_input: str):
        """Add relevant memories to context."""
        if not self.db:
            return
        
        memories = self.session.get_relevant_memories(user_input, limit=self.config.memory_max_context)
        
        if memories:
            memory_text = "\n\nRelevant previous knowledge from past conversations:\n"
            for mem in memories:
                mem_type = mem['memory_type']
                text = mem['content'].get('text', '')
                memory_text += f"- [{mem_type.upper()}] {text}\n"
            
            if not any(m.get('role') == 'system' and 'Relevant previous knowledge' in m.get('content', '') for m in self.session.context[-5:]):
                self.session.add_message('system', memory_text)
    
    def _extract_and_store_memories(self):
        """Extract memories from conversation and store."""
        if not self.db or not self.extractor or not self.session.id:
            return
        
        try:
            messages = self.db.get_unprocessed_messages(self.session.id)
            
            if not messages:
                return
            
            self._event_bus.emit(LogEvent(level="DEBUG", source="memory", message=f"Extracting memories from {len(messages)} messages"))
            
            memories = self.extractor.extract(messages, client=self.client)
            
            self._event_bus.emit(LogEvent(level="DEBUG", source="memory", message=f"Extracted {len(memories)} memories"))
            
            for memory in memories:
                self.db.save_memory(
                    session_id=self.session.id,
                    memory_type=memory['type'],
                    content=memory['content'],
                    confidence=memory['confidence'],
                    tags=memory['tags'],
                    source_message_ids=[m['id'] for m in messages]
                )
            
            message_ids = [m['id'] for m in messages]
            self.db.mark_processed(message_ids)
            
            self._event_bus.emit(LogEvent(level="DEBUG", source="memory", message=f"Marked {len(message_ids)} messages as processed"))
            
        except Exception as e:
            self._emit_error("memory_extraction", str(e))
    
    def run_conversation(self, user_messages: List[str]) -> str:
        """Run multiple messages through the agent."""
        response = ''
        for msg in user_messages:
            response = self.run(msg)
        return response
    
    def clear_context(self) -> None:
        """Clear conversation context."""
        self.session.clear()
        self._event_bus.emit(LogEvent(level="INFO", source="session", message="Context cleared"))
    
    def get_context_summary(self) -> Dict:
        """Get summary of current context."""
        return {
            'session_id': self.session.id,
            'message_count': len(self.session.context),
            'created_at': self.session.created_at.isoformat(),
            'tools_available': list(self.tool_map.keys())
        }
    
    # Async streaming methods
    async def run_streaming(self, user_input: str, max_iterations: Optional[int] = None) -> AsyncGenerator[str, None]:
        """
        Async streaming version of run.
        
        Yields tokens as they arrive from the model.
        """
        if max_iterations is None:
            max_iterations = self.config.max_iterations
        
        # Emit start events
        msg_id = self._event_bus.emit_message_start(is_assistant=True)
        self._event_bus.emit_status("thinking", {"user_input": user_input[:50]})
        
        # Log user message
        truncated = user_input[:100] + "..." if len(user_input) > 100 else user_input
        self._event_bus.emit(LogEvent(level="INFO", source="user", message=truncated))
        
        # Augment context
        self._augment_context_with_memories(user_input)
        self._save_conversation_turn('user', user_input)
        self.session.add_message('user', user_input)
        
        # Agent loop
        iterations = 0
        while iterations < max_iterations:
            # Emit status
            self._event_bus.emit_status("streaming" if iterations == 0 else "running_tool")
            
            # Log LLM request
            self._event_bus.emit(LogEvent(level="INFO", source="llm", message=f"Request to {self.config.model} ({len(self.session.context)} messages)"))
            
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=self.session.context,
                tools=self.tool_schemas,
                temperature=self.config.temperature,
                stream=True  # Enable streaming
            )
            
            full_response = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    yield token
                    self._event_bus.emit_message_delta(token, is_assistant=True, is_complete=False)
            
            # Complete message
            self._event_bus.emit_message_delta("", is_assistant=True, is_complete=True)
            
            # Check for tool calls in final message
            message = response.choices[0].message if hasattr(response, 'choices') else None
            if not message:
                # Get from accumulated chunks
                message = type('obj', (object,), {
                    'content': full_response,
                    'tool_calls': None
                })()
            
            if message.tool_calls:
                # Tool calls - emit start
                self._event_bus.emit_status("running_tool", {"tool_calls": len(message.tool_calls)})
                
                for tc in message.tool_calls:
                    tool_name = tc.function.name
                    tool_args = json.loads(tc.function.arguments)
                    self._event_bus.emit_tool_call_start(tool_name, tool_args, tc.id)
                
                # Process tool calls
                tool_results = self._process_tool_calls(message.tool_calls)
                
                for result in tool_results:
                    tool_name = result.get('name', 'unknown')
                    self._event_bus.emit_tool_call_output(result.get('tool_call_id', ''), f"Result from {tool_name}")
                    self._event_bus.emit_tool_call_done(tool_name, result.get('content', ''), result.get('tool_call_id', ''), True)
                
                # Add to context
                self.session.context.append({
                    'role': 'assistant',
                    'content': message.content,
                    'tool_calls': [
                        {
                            'id': tc.id,
                            'type': 'function',
                            'function': {'name': tc.function.name, 'arguments': tc.function.arguments}
                        } for tc in message.tool_calls
                    ]
                })
                
                for result in tool_results:
                    self.session.context.append(result)
                
                iterations += 1
                continue
            
            # No tool calls
            self.session.add_message('assistant', full_response)
            
            if full_response:
                self._save_conversation_turn('assistant', full_response)
                self._extract_and_store_memories()
            
            self._event_bus.emit_message_done(msg_id, full_response, is_assistant=True)
            self._event_bus.emit_status("idle")
            
            return
        
        self._event_bus.emit_status("idle")
        yield f'Reached maximum iterations ({max_iterations}) without completing.'
    
    # Thread-safe cancellation support
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._cancellation_tokens = {}
    
    def request_cancel(self, session_id: str = None):
        """Request cancellation of current operation."""
        if session_id is None:
            session_id = self.session.id
        self._cancellation_tokens[session_id] = True
    
    def is_cancellation_requested(self, session_id: str = None) -> bool:
        """Check if cancellation was requested."""
        if session_id is None:
            session_id = self.session.id
        return self._cancellation_tokens.get(session_id, False)
    
    def clear_cancellation(self, session_id: str = None):
        """Clear cancellation flag."""
        if session_id is None:
            session_id = self.session.id
        self._cancellation_tokens.pop(session_id, None)


# Example usage
if __name__ == '__main__':
    try:
        from core.config import AgentConfig
        config = AgentConfig.from_env()
        print(f'Loaded config: model={config.model}')
        
        agent = AgentRuntime(config)
        print(f'Agent initialized with tools: {list(agent.tool_map.keys())}')
        
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
