# Phase 1: Core Agent Implementation Plan

**Minimal working APRIL agent that can converse with LLM**

---

## Overview

**Purpose:** Build the foundation - a minimal agent that can:
- Connect to LLM (OpenAI-compatible endpoints)
- Hold conversations in terminal
- Execute simple shell commands
- Manage basic context

**Dependencies:** None (foundation)

**Estimated Time:** 2 weeks (10-12 days)

---

## Goals

### What We're Building

A **minimal viable agent** with:
- LLM communication (OpenAI API)
- Basic REPL (Read-Eval-Print Loop)
- Simple command execution
- Configuration loading
- Session management (ephemeral)

### What We're NOT Building (Yet)

- Tools/framework (Phase 4)
- Subagents (Phase 2)
- Skills (Phase 3)
- OS features (Phase 5+)
- GUI (Phase 14)

---

## Architecture

### Component Design

```
┌─────────────────────────────────────┐
│          APRIL Core Agent           │
│                                      │
│  ┌──────────────┐  ┌─────────────┐ │
│  │ AgentRuntime │  │ Config      │ │
│  │              │  │ Manager     │ │
│  │ • LLM client │  │             │ │
│  │ • Repl loop  │  │ • .env      │ │
│  │ • Context    │  │ • YAML      │ │
│  └──────────────┘  └─────────────┘ │
│                                      │
│  ┌──────────────┐  ┌─────────────┐ │
│  │ Session      │  │ Simple      │ │
│  │ Manager      │  │ Tools       │ │
│  │              │  │             │ │
│  │ • Memory     │  │ • Shell     │ │
│  │ • Context    │  │ • File read │ │
│  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────┘
```

### Key Classes

```python
class AgentRuntime:
    """Main agent execution loop"""
    def __init__(self, config: AgentConfig)
    async def run(self, user_input: str) -> AsyncGenerator[dict, None]
    async def execute_tool(self, name: str, args: dict) -> dict

class AgentConfig:
    """Agent configuration"""
    model: str
    api_key: str
    api_base_url: str
    max_context_length: int
    temperature: float

class Session:
    """Single conversation session"""
    id: str
    context: List[dict]  # Conversation history
    tools: Dict[str, Callable]
    created_at: datetime

class SimpleShellTool:
    """Basic shell command execution"""
    name: str = "shell_execute"
    def execute(self, command: str) -> dict
```

---

## Implementation Steps

### Step 1: Project Setup (Day 1)

**Directory structure:**
```bash
april_os/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── agent.py           # AgentRuntime
│   ├── config.py          # Configuration
│   └── session.py         # Session management
├── tools/
│   ├── __init__.py
│   └── shell.py           # Shell tool
├── cli/
│   ├── __init__.py
│   └── main.py            # CLI entry point
└── tests/
    ├── test_agent.py
    └── test_tools.py
```

**Tasks:**
- [x] Create project structure
- [x] Initialize git repository
- [x] Create requirements.txt
- [x] Setup .env.example

**requirements.txt:**
```txt
openai>=1.0.0
python-dotenv>=1.0.0
pyyaml>=6.0
prompt-toolkit>=3.0.0
rich>=13.0.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
```

**.env.example:**
```bash
OPENAI_API_KEY=your-key-here
OPENAI_API_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=mistral-large
APRIL_CONTEXT_WINDOW=128000
APRIL_TEMPERATURE=0.7
```

---

### Step 2: Configuration Management (Day 2)

**Implement config loader:**

```python
# core/config.py
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
import os
import yaml

@dataclass
class AgentConfig:
    """Agent configuration"""
    model: str
    api_key: str
    api_base_url: str
    max_context_length: int = 128000
    temperature: float = 0.7
    max_iterations: int = 100
    
    @classmethod
    def from_env(cls) -> 'AgentConfig':
        """Load configuration from environment"""
        load_dotenv()
        
        return cls(
            model=os.getenv("OPENAI_MODEL", "mistral-large"),
            api_key=os.getenv("OPENAI_API_KEY", ""),
            api_base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:11434/v1"),
            max_context_length=int(os.getenv("APRIL_CONTEXT_WINDOW", "128000")),
            temperature=float(os.getenv("APRIL_TEMPERATURE", "0.7"))
        )
    
    @classmethod
    def from_yaml(cls, path: Path) -> 'AgentConfig':
        """Load configuration from YAML file"""
        with open(path) as f:
            data = yaml.safe_load(f)
        
        return cls(**data)

# Usage
config = AgentConfig.from_env()
```

**Tasks:**
- [x] Implement AgentConfig class
- [x] Add .env loading
- [x] Add YAML config support
- [x] Write config tests

**Tests:**
```python
# tests/test_config.py
def test_config_from_env():
    config = AgentConfig.from_env()
    assert config.model is not None
    assert config.api_key is not None

def test_config_defaults():
    config = AgentConfig(
        model="test",
        api_key="test",
        api_base_url="http://test"
    )
    assert config.max_context_length == 128000
    assert config.temperature == 0.7
```

---

### Step 3: Basic Tools (Day 3-4)

**Implement simple shell tool:**

```python
# tools/shell.py
from dataclasses import dataclass
import subprocess
import shlex

@dataclass
class ToolResult:
    """Tool execution result"""
    success: bool
    output: str
    error: str = ""
    return_code: int = 0

class ShellTool:
    """Execute shell commands"""
    
    name = "shell_execute"
    description = "Execute a shell command"
    
    @staticmethod
    def schema() -> dict:
        """OpenAI function schema"""
        return {
            "type": "function",
            "function": {
                "name": "shell_execute",
                "description": "Execute a shell command",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Shell command to execute"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout in seconds",
                            "default": 30
                        }
                    },
                    "required": ["command"]
                }
            }
        }
    
    def execute(self, command: str, timeout: int = 30) -> ToolResult:
        """Execute shell command"""
        try:
            result = subprocess.run(
                shlex.split(command),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                return_code=result.returncode
            )
        
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout}s"
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )

# tools/__init__.py
ALL_TOOLS = {
    "shell_execute": ShellTool()
}

def get_tool_schemas() -> list:
    """Get all tool schemas for OpenAI"""
    return [tool.schema() for tool in ALL_TOOLS.values()]
```

**Tasks:**
- [x] Implement ShellTool
- [x] Add ToolResult dataclass
- [x] Create tool registry
- [x] Write tool tests

**Tests:**
```python
# tests/test_tools.py
def test_shell_tool_ls():
    tool = ShellTool()
    result = tool.execute("ls")
    assert result.success
    assert result.output

def test_shell_tool_invalid():
    tool = ShellTool()
    result = tool.execute("nonexistentcommand123")
    assert not result.success
    assert result.error

def test_tool_schema():
    schema = ShellTool.schema()
    assert schema ["type"] == "function"
    assert schema ["function"]["name"] == "shell_execute"
```

---

### Step 4: Agent Runtime (Day 5-7)

**Implement main agent loop:**

```python
# core/agent.py
from typing import AsyncGenerator, Dict, List, Callable
import openai
import json

class AgentRuntime:
    """
    Main agent execution loop
    
    Responsibilities:
    - Execute agent Repl (Read-Eval-Print Loop)
    - Call LLM
    - Execute tools
    - Manage context
    """
    
    def __init__(self, config: 'AgentConfig'):
        self.config = config
        self.client = openai.OpenAI(
            api_key=config.api_key,
            base_url=config.api_base_url
        )
        self.tools: Dict[str, Callable] = {}
        self.context: List[dict] = []
    
    def register_tool(self, name: str, func: Callable):
        """Register a tool"""
        self.tools[name] = func
    
    async def run(
        self,
        user_input: str,
        system_prompt: str = "You are APRIL, a helpful assistant."
    ) -> AsyncGenerator[dict, None]:
        """
        Run agent loop
        
        Yields: Stream of events
        - {"type": "reasoning", "content": "..."}
        - {"type": "tool_call", "name": "...", "args": {...}}
        - {"type": "tool_result", "result": {...}}
        - {"type": "complete", "content": "..."}
        - {"type": "error", "error": "..."}
        """
        
        # Add user message to context
        self.context.append({
            "role": "user",
            "content": user_input
        })
        
        # Add system prompt if not present
        if not any(msg["role"] == "system" for msg in self.context):
            self.context.insert(0, {
                "role": "system",
                "content": system_prompt
            })
        
        iteration = 0
        
        while iteration < self.config.max_iterations:
            try:
                # Call LLM
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=self.context,
                    tools=self._get_tool_schemas(),
                    tool_choice="auto",
                    temperature=self.config.temperature
                )
                
                msg = response.choices[0].message
                
                # Yield reasoning
                if msg.content:
                    yield {
                        "type": "reasoning",
                        "content": msg.content,
                        "iteration": iteration
                    }
                
                # Check if done
                if msg.content and not msg.tool_calls:
                    self.context.append({
                        "role": "assistant",
                        "content": msg.content
                    })
                    yield {"type": "complete", "content": msg.content}
                    return
                
                # Execute tool calls
                if msg.tool_calls:
                    self.context.append(msg.to_dict())
                    
                    for tool_call in msg.tool_calls:
                        # Yield tool call event
                        yield {
                            "type": "tool_call",
                            "name": tool_call.function.name,
                            "args": json.loads(tool_call.function.arguments)
                        }
                        
                        # Execute tool
                        result = await self._execute_tool(
                            tool_call.function.name,
                            json.loads(tool_call.function.arguments)
                        )
                        
                        # Yield result
                        yield {"type": "tool_result", "result": result}
                        
                        # Add to context
                        self.context.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result)
                        })
                
                iteration += 1
            
            except Exception as e:
                yield {"type": "error", "error": str(e)}
                return
        
        yield {"type": "error", "error": "Max iterations exceeded"}
    
    async def _execute_tool(self, name: str, args: dict) -> dict:
        """Execute a tool"""
        if name not in self.tools:
            return {"error": f"Unknown tool: {name}"}
        
        try:
            result = self.tools[name](**args)
            
            if hasattr(result, '__dict__'):
                return result.__dict__
            
            return {"success": True, "data": result}
        
        except Exception as e:
            return {"error": str(e)}
    
    def _get_tool_schemas(self) -> list:
        """Get tool schemas for OpenAI"""
        # For now, return shell tool schema
        from tools import ALL_TOOLS
        return [tool.schema() for tool in ALL_TOOLS.values()]
    
    def clear_context(self):
        """Clear conversation context"""
        self.context = []

# Usage
async def main():
    config = AgentConfig.from_env()
    agent = AgentRuntime(config)
    
    # Register tools
    from tools import ALL_TOOLS
    for name, tool in ALL_TOOLS.items():
        agent.register_tool(name, tool.execute)
    
    # Run
    async for event in agent.run("List current directory"):
        print(event)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

**Tasks:**
- [x] Implement AgentRuntime
- [x] Add OpenAI client integration
- [x] Implement tool execution
- [x] Add context management
- [x] Write agent tests

**Tests:**
```python
# tests/test_agent.py
import pytest
from core.agent import AgentRuntime
from core.config import AgentConfig

@pytest.mark.asyncio
async def test_agent_conversation():
    config = AgentConfig.from_env()
    agent = AgentRuntime(config)
    
    events = []
    async for event in agent.run("Hello"):
        events.append(event)
    
    assert len(events) > 0
    assert events[-1]["type"] == "complete"

@pytest.mark.asyncio
async def test_agent_tool_execution():
    config = AgentConfig.from_env()
    agent = AgentRuntime(config)
    
    # Register shell tool
    from tools.shell import ShellTool
    agent.register_tool("shell_execute", ShellTool().execute)
    
    events = []
    async for event in agent.run("Execute: echo hello"):
        events.append(event)
    
    # Should have tool call
    tool_calls = [e for e in events if e["type"] == "tool_call"]
    assert len(tool_calls) > 0
```

---

### Step 5: Session Management (Day 8)

**Implement basic session:**

```python
# core/session.py
from dataclasses import dataclass, field
from typing import List, Dict
from datetime import datetime
import uuid

@dataclass
class Session:
    """
    Single conversation session
    
    Responsibilities:
    - Track conversation history
    - Manage ephemeral memory
    - Store session metadata
    """
    
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    context: List[dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def add_message(self, role: str, content: str):
        """Add message to context"""
        self.context.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_context(self) -> List[dict]:
        """Get conversation context"""
        return self.context
    
    def clear(self):
        """Clear session"""
        self.context = []
    
    def to_dict(self) -> dict:
        """Serialize session"""
        return {
            "id": self.id,
            "context": self.context,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }

class SessionManager:
    """Manage multiple sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
    
    def create_session(self) -> Session:
        """Create new session"""
        session = Session()
        self.sessions[session.id] = session
        return session
    
    def get_session(self, session_id: str) -> Session:
        """Get session by ID"""
        return self.sessions.get(session_id)
    
    def delete_session(self, session_id: str):
        """Delete session"""
        if session_id in self.sessions:
            del self.sessions[session_id]

# Tests
def test_session_creation():
    session = Session()
    assert session.id
    assert session.context == []

def test_session_add_message():
    session = Session()
    session.add_message("user", "Hello")
    assert len(session.context) == 1
    assert session.context[0]["role"] == "user"
```

---

### Step 6: CLI Interface (Day 9-10)

**Implement terminal interface:**

```python
# cli/main.py
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.panel import Panel
import asyncio
from core.agent import AgentRuntime
from core.config import AgentConfig
from tools.shell import ShellTool

class AprilCLI:
    """
    APRIL command-line interface
    
    Features:
    - Rich terminal UI
    - Command history
    - Real-time agent responses
    """
    
    def __init__(self):
        self.console = Console()
        self.session = PromptSession(
            history=FileHistory('.april_history')
        )
        self.config = AgentConfig.from_env()
        self.agent = AgentRuntime(self.config)
        
        # Register tools
        self.agent.register_tool("shell_execute", ShellTool().execute)
    
    async def run(self):
        """Run CLI loop"""
        
        self.console.print(Panel.fit(
            "[bold cyan]APRIL Agent v0.1.0[/bold cyan]\n"
            "Type 'exit' to quit",
            title="Welcome"
        ))
        
        while True:
            try:
                # Read user input
                user_input = await self.session.prompt_async(
                    "[cyan]april[/cyan]> ",
                )
                
                if user_input.strip().lower() == "exit":
                    self.console.print("[yellow]Goodbye![/yellow]")
                    break
                
                # Run agent
                await self._run_agent(user_input)
            
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted[/yellow]")
                continue
            except EOFError:
                break
        
        self.console.print("[yellow]Session ended[/yellow]")
    
    async def _run_agent(self, user_input: str):
        """Run agent and display results"""
        
        try:
            async for event in self.agent.run(user_input):
                if event["type"] == "reasoning":
                    self.console.print(f"[dim]{event['content']}[/dim]")
                
                elif event["type"] == "tool_call":
                    self.console.print(f"[blue]Tool: {event['name']}[/blue]")
                
                elif event["type"] == "tool_result":
                    result = event["result"]
                    if result.get("success"):
                        self.console.print(f"[green]{result.get('output', '')}[/green]")
                    else:
                        self.console.print(f"[red]{result.get('error', 'Unknown error')}[/red]")
                
                elif event["type"] == "complete":
                    self.console.print(f"\n[bold]{event['content']}[/bold]\n")
                
                elif event["type"] == "error":
                    self.console.print(f"[red]Error: {event['error']}[/red]")
        
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")

def main():
    """Entry point"""
    cli = AprilCLI()
    asyncio.run(cli.run())

if __name__ == "__main__":
    main()
```

**Tasks:**
- [x] Implement CLI
- [x] Add rich output
- [x] Add command history
- [x] Handle errors gracefully

---

### Step 7: Integration & Testing (Day 11-12)

**Integration tests:**

```python
# tests/integration/test_core_integration.py
import pytest
from core.agent import AgentRuntime
from core.config import AgentConfig
from core.session import Session
from tools.shell import ShellTool

@pytest.mark.asyncio
async def test_full_conversation():
    """Test full conversation flow"""
    
    # Setup
    config = AgentConfig.from_env()
    agent = AgentRuntime(config)
    agent.register_tool("shell_execute", ShellTool().execute)
    
    # Run conversation
    events = []
    async for event in agent.run("What files are in current directory?"):
        events.append(event)
    
    # Verify
    assert len(events) > 0
    assert any(e["type"] == "complete" for e in events)

@pytest.mark.asyncio
async def test_tool_execution_flow():
    """Test tool execution"""
    
    config = AgentConfig.from_env()
    agent = AgentRuntime(config)
    agent.register_tool("shell_execute", ShellTool().execute)
    
    events = []
    async for event in agent.run("Execute: echo 'hello world'"):
        events.append(event)
    
    # Should execute tool
    tool_calls = [e for e in events if e["type"] == "tool_call"]
    assert len(tool_calls) > 0
    assert tool_calls[0]["name"] == "shell_execute"
```

**Tasks:**
- [x] Write integration tests
- [x] Test end-to-end flow
- [x] Test error scenarios
- [x] Test context management

---

## Success Criteria

### Definition of Done

Phase 1 is complete when:

- [ ] Agent can hold conversations with LLM
- [ ] Agent can execute shell commands
- [ ] CLI interface works with rich output
- [ ] Command history is saved
- [ ] Configuration loads from .env
- [ ] All unit tests pass (pytest tests/)
- [ ] Integration tests pass
- [ ] Manual test: Can chat via CLI

### Manual Test Procedure

```bash
# 1. Setup
cp .env.example .env
# Edit .env with your LLM config

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run agent
python -m april_os.cli.main

# 4. Test conversation
aprils> Hello
[Agent responds]

# 5. Test tool execution
aprils> List files in current directory
[Agent executes: ls -la]

# 6. Exit
aprils> exit
```

**Expected output:**
```
╭─────────────────────────────────╮
│ APRIL Agent v0.1.0              │
│ Type 'exit' to quit             │
╰─────────────────────────────────╯

aprils> Hello
[APRIL reasoning...]
Hello! I'm APRIL, how can I help you today?

aprils> List files
[Using shell_execute...]
total 32
drwxr-xr-x  8 user  staff   256 Sep 27 10:00 .
drwxr-xr-x  3 user  staff    96 Sep 27 09:00 ..
-rw-r--r--  1 user  staff   123 Sep 27 10:00 README.md
...
```

---

## Next Phase

**Phase 2:** `02-SUBAGENT-IMPLEMENTATION.md`

Phase 1 provides:
- ✅ Working agent runtime
- ✅ Tool execution framework
- ✅ Session management
- ✅ CLI interface

Phase 2 will add:
- Subagent spawning
- Agent-to-agent communication
- Task dispatching
- Specialized agents

---

## Troubleshooting

### Common Issues

**1. LLM connection fails**
```bash
# Check .env
cat .env

# Test connection
curl http://localhost:11434/v1/models
```

**2. Shell tool not working**
```python
# Test shell tool directly
from tools.shell import ShellTool
tool = ShellTool()
result = tool.execute("ls")
print(result)
```

**3. Context too long**
```python
# Clear context
agent.clear_context()
```

---

## Files Created

```
april_os/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── agent.py           ✅ Implemented
│   ├── config.py          ✅ Implemented
│   └── session.py         ✅ Implemented
├── tools/
│   ├── __init__.py        ✅ Implemented
│   └── shell.py           ✅ Implemented
├── cli/
│   ├── __init__.py
│   └── main.py            ✅ Implemented
└── tests/
    ├── test_agent.py      ✅ Tests
    ├── test_config.py     ✅ Tests
    ├── test_tools.py      ✅ Tests
    └── integration/
        └── test_core.py   ✅ Integration
```

---

## Milestone Release

**Tag:** `v0.1.0`

```bash
git tag -a v0.1.0 -m "Phase 1: Core Agent"
git push origin v0.1.0
```

---

**Ready to build Phase 1? Let's code!** 🚀
