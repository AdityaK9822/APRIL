# Phase 2: Subagent System Implementation Plan

## Overview

**Purpose:** Enable the main agent to spawn specialized subagents for specific tasks, dispatch work to them, and aggregate results.

**Dependencies:** Phase 1 (Core Agent) - completed ✅

**Estimated time:** 2 weeks

---

## Goals

The subagent system enables:
1. **Spawning** - Create specialized agents for specific task types
2. **Dispatching** - Route tasks to appropriate subagents
3. **Communication** - Enable agent-to-agent messaging
4. **Aggregation** - Collect and merge results from multiple subagents
5. **Lifecycle** - Manage subagent creation, execution, and cleanup

This mirrors Unix process model: parent process spawns child processes, communicates via IPC, and collects results.

---

## Architecture

### Design Decisions

**1. Subagent as Process**
- Each subagent runs in its own context (like Unix process)
- Isolated execution environment
- Independent session management

**2. Task Queue Pattern**
- Main agent dispatches tasks to queue
- Subagent picks up tasks
- Results stored in result buffer

**3. Message Passing**
- Agent-to-agent via message queue
- Async communication pattern
- Structured message format

**4. Result Aggregation**
- Subagent returns structured results
- Main agent can merge/combine results
- Support for streaming results

### Key Classes

```python
# Subagent definition
class SubagentConfig:
    name: str
    role: str
    capabilities: List[str]
    parent_id: str
    metadata: Dict

# Subagent process
class SubagentProcess:
    id: str
    config: SubagentConfig
    agent: AgentRuntime
    status: str  # idle, running, completed, failed
    result: Optional[Any]
    
    def run(self, task: Task) -> Result
    def get_status(self) -> str
    def kill(self) -> None

# Subagent manager
class SubagentManager:
    subagents: Dict[str, SubagentProcess]
    
    def spawn(self, config: SubagentConfig) -> SubagentProcess
    def dispatch(self, subagent_id: str, task: Task) -> None
    def get_result(self, subagent_id: str) -> Result
    def list_subagents(self) -> List[SubagentProcess]
    def kill(self, subagent_id: str) -> None

# Task definition
class Task:
    id: str
    type: str
    description: str
    parameters: Dict
    priority: int

# Result definition
class Result:
    task_id: str
    subagent_id: str
    success: bool
    data: Any
    error: Optional[str]
    metadata: Dict
```

### Interfaces

```python
# Spawn interface
manager.spawn(config) -> SubagentProcess

# Dispatch interface
manager.dispatch(subagent_id, task) -> None

# Result interface
manager.get_result(subagent_id) -> Result

# Communication interface (future)
manager.send_message(subagent_id, message) -> None
manager.receive_message(subagent_id) -> Message
```

---

## Implementation Steps

### Step 1: Setup
- [x] Create implementation plan document
- [ ] Create directory structure: `april_os/core/subagent.py`
- [ ] Add task/result classes
- [ ] Setup testing framework

**Directory structure:**
```
april_os/
├── core/
│   ├── subagent.py       # SubagentManager and related classes
│   └── ...
└── tests/
    └── test_subagent.py  # Subagent tests
```

### Step 2: Core Implementation

#### Task and Result Classes
- [ ] Implement Task dataclass
- [ ] Implement Result dataclass
- [ ] Add serialization methods

#### SubagentProcess Class
- [ ] Implement SubagentProcess class
- [ ] Add status tracking
- [ ] Implement run() method
- [ ] Add error handling

#### SubagentManager Class
- [ ] Implement SubagentManager class
- [ ] Implement spawn() method
- [ ] Implement dispatch() method
- [ ] Implement get_result() method
- [ ] Implement list_subagents() method
- [ ] Implement kill() method

#### Agent Integration
- [ ] Add subagent tool to AgentRuntime
- [ ] Enable agent to spawn subagents
- [ ] Add subagent tool schema

### Step 3: Integration

- [ ] Integrate SubagentManager with AgentRuntime
- [ ] Test spawning from main agent
- [ ] Test task dispatching
- [ ] Test result collection
- [ ] Update documentation

### Step 4: Polish

- [ ] Add logging for subagent lifecycle
- [ ] Add timeout handling
- [ ] Add error recovery
- [ ] Performance optimization
- [ ] Final testing

---

## Testing Strategy

### Unit Tests

```python
# test_subagent.py

def test_task_creation():
    """Test Task instantiation"""
    task = Task(
        id="test-1",
        type="shell",
        description="Test shell command"
    )
    assert task.id == "test-1"
    assert task.status == "pending"

def test_result_serialization():
    """Test Result serialization"""
    result = Result(
        task_id="test-1",
        success=True,
        data="output"
    )
    assert result.to_dict()["success"] is True

def test_subagent_spawn():
    """Test spawning a subagent"""
    manager = SubagentManager(config)
    subagent = manager.spawn(SubagentConfig(
        name="test-agent",
        role="executor"
    ))
    assert subagent.id is not None
    assert subagent.status == "idle"

def test_subagent_dispatch():
    """Test dispatching task to subagent"""
    manager = SubagentManager(config)
    subagent = manager.spawn(...)
    task = Task(...)
    manager.dispatch(subagent.id, task)
    result = manager.get_result(subagent.id)
    assert result.success

def test_subagent_manager_list():
    """Test listing subagents"""
    manager = SubagentManager(config)
    manager.spawn(...)
    manager.spawn(...)
    subagents = manager.list_subagents()
    assert len(subagents) == 2
```

### Integration Tests

```python
def test_agent_spawns_subagent():
    """Test main agent spawning subagent"""
    agent = AgentRuntime(config)
    response = agent.run("Create a subagent to list files")
    assert "subagent" in response.lower()

def test_subagent_task_completion():
    """Test subagent completes task"""
    manager = SubagentManager(config)
    subagent = manager.spawn(...)
    task = Task(type="shell", description="ls -la")
    result = manager.dispatch_and_wait(subagent.id, task)
    assert result.success
```

### Manual Tests

```bash
# Test 1: Spawn subagent from CLI
python -m april_os.cli.main
> Create a subagent named 'file-lister' that can list files

# Test 2: Dispatch task
> Send this task to file-lister: "List all Python files in this directory"

# Test 3: Get result
> What did file-lister return?

# Test 4: Multiple subagents
> Create two subagents: one for file operations, one for network operations

# Test 5: Parallel dispatch
> Send tasks to both subagents and show me results
```

---

## Success Criteria

Phase 2 is complete when:

### Functional Requirements
- [x] Can spawn a subagent with specific role
- [ ] Can dispatch task to subagent
- [ ] Subagent executes task and returns result
- [ ] Can get result from subagent
- [ ] Can list all active subagents
- [ ] Can kill a subagent

### Technical Requirements
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Manual tests successful
- [ ] Code documented
- [ ] README updated

### Performance Requirements
- [ ] Subagent spawn < 1 second
- [ ] Task dispatch < 100ms
- [ ] Can handle 10+ concurrent subagents

---

## Code Examples

### Spawning a Subagent

```python
from april_os.core.subagent import SubagentManager, SubagentConfig
from april_os.core.config import AgentConfig

# Create manager
config = AgentConfig.from_env()
manager = SubagentManager(config)

# Spawn subagent
subagent = manager.spawn(SubagentConfig(
    name="file-operations",
    role="file-handler",
    capabilities=["read", "write", "list"],
    parent_id="main-agent"
))

print(f"Spawned subagent: {subagent.id}")
```

### Dispatching a Task

```python
from april_os.core.subagent import Task

# Create task
task = Task(
    id="task-1",
    type="list",
    description="List all Python files",
    parameters={"directory": "/path/to/dir", "pattern": "*.py"}
)

# Dispatch to subagent
manager.dispatch(subagent.id, task)

# Get result
result = manager.get_result(subagent.id)

if result.success:
    print(f"Found {len(result.data)} files")
else:
    print(f"Error: {result.error}")
```

### Using from Main Agent

```python
# In main agent session
agent.run("Create a subagent to analyze the codebase")

# Agent internally:
# 1. Calls spawn_subagent tool
# 2. Manager creates new SubagentProcess
# 3. Subagent gets own AgentRuntime with specialized role
# 4. Main agent can dispatch tasks
```

---

## Implementation Notes

### Subagent Context Isolation

Each subagent has its own session:
- Separate message history
- Independent context management
- No shared state (unless explicitly passed)

### Parent-Child Relationship

```
Main Agent (id: main-1)
├── Subagent 1 (id: sub-a1, parent: main-1)
├── Subagent 2 (id: sub-a2, parent: main-1)
└── Subagent 3 (id: sub-a3, parent: main-1)
    └── Sub-subagent (id: sub-a3-b1, parent: sub-a3)
```

### Task Routing

```
User Request → Main Agent
                │
                ├─ Analyzes request
                ├─ Decides to delegate
                ├─ Spawns subagent
                ├─ Dispatches task
                ├─ Waits for result
                └─ Returns response
```

---

## Next Phase

Phase 2 enables:

**Phase 3: Skills System**
- Skills can define what subagents to spawn
- Skill auto-triggering based on request type
- Specialized skill agents

**Phase 4: MCP Integration**
- Subagents can call MCP tools
- Device-specific subagents
- Networked subagent communication

---

## References

- Phase 1: `01-CORE-IMPLEMENTATION.md`
- Architecture: `/docs/architecture/APRIL-OS-ARCHITECTURE.md`
- ZCode Features: `/docs/architecture/ADE-ZCODE-FEATURES.md`
- Master Roadmap: `MASTER-IMPLEMENTATION-ROADMAP.md`

---

**Ready to implement? Let's start coding!** 🚀
