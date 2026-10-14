"""
APRIL Agent Runtime

The core agent loop: manage context, call LLM, process tool calls.
"""

from typing import List, Dict, Optional, Callable, AsyncGenerator
import json
import threading
import os
from openai import OpenAI

from .config import AgentConfig
from .session import Session
from .database import MemoryDatabase
from .memory_extractor import MemoryExtractor
from .logging import get_logger, debug, info, warning, error
from tools.shell import ShellTool


class AgentRuntime:
    """
    The core agent runtime
    
    Manages conversation with an LLM, processes tool calls, and
    maintains session state.
    
    Example:
        >>> config = AgentConfig.from_env()
        >>> agent = AgentRuntime(config)
        >>> response = agent.run("What files are in this directory?")
        >>> print(response)
    """
    
    def __init__(self, config: AgentConfig, tools: Optional[List] = None):
        """
        Initialize agent runtime
        
        Args:
            config: Agent configuration
            tools: List of tool instances (default: ShellTool)
        """
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
                self.extractor._client = self.client  # Use same OpenAI client
            except Exception as e:
                print(f"Warning: Could not initialize memory: {e}")
        
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
    
    def _process_tool_calls(self, tool_calls: List) -> List[Dict]:
        """
        Process tool calls from LLM response
        
        Args:
            tool_calls: List of tool call objects from API
            
        Returns:
            List of tool result messages
        """
        results = []
        
        for call in tool_calls:
            tool_name = call.function.name
            tool_args = json.loads(call.function.arguments)
            
            # Find tool
            if tool_name not in self.tool_map:
                results.append({
                    'tool_call_id': call.id,
                    'role': 'tool',
                    'name': tool_name,
                    'content': f"Error: Unknown tool '{tool_name}'"
                })
                continue
            
            # Execute tool
            tool = self.tool_map[tool_name]
            
            try:
                # Call tool execute method
                if tool_name == 'shell_execute':
                    result = tool.execute(
                        command=tool_args.get('command'),
                        timeout=tool_args.get('timeout', 30)
                    )
                else:
                    # Generic tool call
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
        """
        Run the agent loop
        
        Args:
            user_input: User message
            max_iterations: Maximum tool call iterations (default: from config)
            
        Returns:
            Final response string
            
        Example:
            >>> agent = AgentRuntime(config)
            >>> response = agent.run('List files')
            >>> print(response)
        """
        if max_iterations is None:
            max_iterations = self.config.max_iterations
        
        # Augment context with relevant memories
        self._augment_context_with_memories(user_input)
        
        # Save user message to database
        self._save_conversation_turn('user', user_input)
        
        # Add user message to context
        self.session.add_message('user', user_input)
        
        # Agent loop
        iterations = 0
        while iterations < max_iterations:
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=self.session.context,
                tools=self.tool_schemas,
                temperature=self.config.temperature
            )
            
            message = response.choices[0].message
            
            # Check if we need to process tool calls
            if message.tool_calls:
                # Add assistant message with tool calls to context
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
                
                # Add tool results to context
                for result in tool_results:
                    self.session.context.append(result)
                
                iterations += 1
                continue
            
            # No tool calls - we have a final response
            self.session.add_message('assistant', message.content or '')
            final_response = message.content or ''
            
            # Save assistant response to database and trigger extraction
            if final_response:
                self._save_conversation_turn('assistant', final_response)
                self._extract_and_store_memories()
            
            return final_response
        
        # Max iterations reached
        return f'Reached maximum iterations ({max_iterations}) without completing. Last context length: {len(self.session.context)} messages.'
    
    def _save_conversation_turn(self, role: str, content: str):
        """
        Save conversation turn to database
        
        Args:
            role: Message role
            content: Message content
        """
        if self.db:
            self.db.save_message(self.session.id, role, content)
    
    def _augment_context_with_memories(self, user_input: str):
        """
        Add relevant memories to context
        
        Args:
            user_input: User's input message
        """
        if not self.db:
            return
        
        # Search for relevant memories
        memories = self.session.get_relevant_memories(user_input, limit=self.config.memory_max_context)
        
        if memories:
            # Format memories as context
            memory_text = "\n\nRelevant previous knowledge from past conversations:\n"
            for mem in memories:
                mem_type = mem['memory_type']
                text = mem['content'].get('text', '')
                memory_text += f"- [{mem_type.upper()}] {text}\n"
            
            # Add to context as system message (only if not already added)
            if not any(m.get('role') == 'system' and 'Relevant previous knowledge' in m.get('content', '') for m in self.session.context[-5:]):
                self.session.add_message('system', memory_text)
    
    def _extract_and_store_memories(self):
        """
        Extract memories from conversation and store
        
        Runs synchronously after agent response.
        Logs only when APRIL_LOG_LEVEL is DEBUG or lower.
        """
        if not self.db or not self.extractor or not self.session.id:
            return
        
        try:
            # Get unprocessed messages for this session
            messages = self.db.get_unprocessed_messages(self.session.id)
            
            if not messages:
                return
            
            info(f"Starting memory extraction for {len(messages)} messages")
            
            # Extract memories
            memories = self.extractor.extract(messages, client=self.client)
            
            info(f"Extracted {len(memories)} memories")
            
            # Store memories
            for memory in memories:
                self.db.save_memory(
                    session_id=self.session.id,
                    memory_type=memory['type'],
                    content=memory['content'],
                    confidence=memory['confidence'],
                    tags=memory['tags'],
                    source_message_ids=[m['id'] for m in messages]
                )
            
            # Mark messages as processed
            message_ids = [m['id'] for m in messages]
            self.db.mark_processed(message_ids)
            
            info(f"Marked {len(message_ids)} messages as processed")
            
        except Exception as e:
            error(f"Memory extraction failed: {e}")
    
    def run_conversation(self, user_messages: List[str]) -> str:
        """
        Run multiple messages through the agent
        
        Args:
            user_messages: List of user messages
            
        Returns:
            Final response after all messages
        """
        response = ''
        for msg in user_messages:
            response = self.run(msg)
        return response
    
    def clear_context(self) -> None:
        """Clear conversation context"""
        self.session.clear()
    
    def get_context_summary(self) -> Dict:
        """
        Get summary of current context
        
        Returns:
            Dictionary with context stats
        """
        return {
            'session_id': self.session.id,
            'message_count': len(self.session.context),
            'created_at': self.session.created_at.isoformat(),
            'tools_available': list(self.tool_map.keys())
        }


# Example usage
if __name__ == '__main__':
    # Test with environment config
    try:
        config = AgentConfig.from_env()
        print(f'Loaded config: model={config.model}')
        print(f'Memory enabled: {config.memory_enabled}')
        if config.memory_enabled:
            print(f'Memory DB path: {config.memory_db_path}')
        
        agent = AgentRuntime(config)
        print(f'Agent initialized with tools: {list(agent.tool_map.keys())}')
        print(f'Session: {agent.session.id}')
        
        if agent.db:
            print(f'Database initialized successfully')
            print(f'Stats: {agent.db.get_stats()}')
        
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
        print('Make sure to set up .env with OPENAI_API_KEY and OPENAI_API_BASE_URL')
