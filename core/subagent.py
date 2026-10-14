"""
APRIL Subagent System

Enables spawning specialized agents for specific tasks,
dispatching work, and aggregating results.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid
import threading
import queue

from .config import AgentConfig
from .agent import AgentRuntime
from .session import Session


class TaskStatus(Enum):
    """Task status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SubagentStatus(Enum):
    """Subagent status enum"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


@dataclass
class Task:
    """
    Task definition for subagent execution

    Attributes:
        id: Unique task identifier
        type: Task type (shell, analyze, etc.)
        description: Human-readable task description
        parameters: Task-specific parameters
        priority: Task priority (higher = more important)
        status: Current task status
        created_at: Task creation timestamp
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = "generic"
    description: str = ""
    parameters: Dict = field(default_factory=dict)
    priority: int = 1
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Serialize to dictionary"""
        return {
            'id': self.id,
            'type': self.type,
            'description': self.description,
            'parameters': self.parameters,
            'priority': self.priority,
            'status': self.status.value,
            'created_at': self.created_at.isoformat()
        }

    def to_json(self) -> str:
        """Serialize to JSON"""
        import json
        return json.dumps(self.to_dict())


@dataclass
class Result:
    """
    Result from subagent task execution

    Attributes:
        task_id: ID of the task
        subagent_id: ID of the subagent that executed
        success: Whether execution succeeded
        data: Result data (output, analysis, etc.)
        error: Error message if failed
        metadata: Additional metadata
        completed_at: Completion timestamp
    """

    task_id: str = ""
    subagent_id: str = ""
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    completed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Serialize to dictionary"""
        return {
            'task_id': self.task_id,
            'subagent_id': self.subagent_id,
            'success': self.success,
            'data': self.data,
            'error': self.error,
            'metadata': self.metadata,
            'completed_at': self.completed_at.isoformat()
        }

    def to_json(self) -> str:
        """Serialize to JSON"""
        import json
        return json.dumps(self.to_dict())


@dataclass
class SubagentConfig:
    """
    Subagent configuration

    Attributes:
        name: Subagent name
        role: Subagent role (file-handler, analyzer, etc.)
        capabilities: List of capabilities
        parent_id: ID of parent agent
        metadata: Additional metadata
        max_iterations: Maximum iterations for subagent
        tools: Tools available to subagent (None = all)
    """

    name: str = "unnamed"
    role: str = "general"
    capabilities: List[str] = field(default_factory=list)
    parent_id: str = ""
    metadata: Dict = field(default_factory=dict)
    max_iterations: int = 50
    tools: Optional[List[str]] = None


class SubagentProcess:
    """
    A running subagent process

    Manages execution lifecycle and state.
    """

    def __init__(self, config: SubagentConfig, agent_config: AgentConfig):
        """
        Initialize subagent process

        Args:
            config: Subagent configuration
            agent_config: Agent configuration for runtime
        """
        self.id = str(uuid.uuid4())[:8]
        self.config = config
        self.agent_config = agent_config

        # Create isolated agent runtime
        self.agent = AgentRuntime(agent_config)

        # Set session metadata
        self.agent.session.metadata.update({
            'subagent_id': self.id,
            'subagent_name': config.name,
            'subagent_role': config.role,
            'parent_id': config.parent_id
        })

        self.status = SubagentStatus.IDLE
        self.current_task: Optional[Task] = None
        self.result: Optional[Result] = None
        self.created_at = datetime.now()
        self.completed_at: Optional[datetime] = None

        # Task queue for threading (future use)
        self._task_queue = queue.Queue()
        self._result_queue = queue.Queue()

    def run(self, task: Task) -> Result:
        """
        Run a task

        Args:
            task: Task to execute

        Returns:
            Execution result
        """
        self.current_task = task
        self.status = SubagentStatus.RUNNING
        task.status = TaskStatus.RUNNING

        try:
            # Execute task via agent
            response = self.agent.run(
                task.description,
                max_iterations=self.config.max_iterations
            )

            # Create successful result
            self.result = Result(
                task_id=task.id,
                subagent_id=self.id,
                success=True,
                data=response,
                metadata={'task_type': task.type}
            )

            task.status = TaskStatus.COMPLETED
            self.status = SubagentStatus.COMPLETED

        except Exception as e:
            # Create failed result
            self.result = Result(
                task_id=task.id,
                subagent_id=self.id,
                success=False,
                data=None,
                error=str(e)
            )

            task.status = TaskStatus.FAILED
            self.status = SubagentStatus.FAILED

        self.completed_at = datetime.now()
        return self.result

    def get_status(self) -> Dict:
        """
        Get subagent status

        Returns:
            Status dictionary
        """
        return {
            'id': self.id,
            'name': self.config.name,
            'role': self.config.role,
            'status': self.status.value,
            'current_task': self.current_task.to_dict() if self.current_task else None,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

    def kill(self):
        """Kill subagent"""
        self.status = SubagentStatus.KILLED
        self.completed_at = datetime.now()


class SubagentManager:
    """
    Manages subagent lifecycle and task routing

    Provides interface for spawning, dispatching, and collecting results.
    """

    def __init__(self, config: AgentConfig):
        """
        Initialize subagent manager

        Args:
            config: Agent configuration for subagents
        """
        self.config = config
        self.subagents: Dict[str, SubagentProcess] = {}
        self.created_at = datetime.now()

    def spawn(self, subagent_config: SubagentConfig) -> SubagentProcess:
        """
        Spawn a new subagent

        Args:
            subagent_config: Subagent configuration

        Returns:
            Created subagent process

        Example:
            >>> manager.spawn(SubagentConfig(
            ...     name="file-handler",
            ...     role="file-operations"
            ... ))
        """
        process = SubagentProcess(subagent_config, self.config)
        self.subagents[process.id] = process
        return process

    def dispatch(self, subagent_id: str, task: Task) -> Result:
        """
        Dispatch task to subagent

        Args:
            subagent_id: Subagent ID
            task: Task to execute

        Returns:
            Execution result

        Raises:
            ValueError: If subagent not found
        """
        if subagent_id not in self.subagents:
            raise ValueError(f"Subagent {subagent_id} not found")

        subagent = self.subagents[subagent_id]
        return subagent.run(task)

    def dispatch_and_wait(self, subagent_id: str, task: Task, timeout: Optional[float] = None) -> Result:
        """
        Dispatch task and wait for result

        Args:
            subagent_id: Subagent ID
            task: Task to execute
            timeout: Timeout in seconds

        Returns:
            Execution result
        """
        # For now, synchronous execution
        # In future, add threading for async
        return self.dispatch(subagent_id, task)

    def get_result(self, subagent_id: str) -> Optional[Result]:
        """
        Get result from subagent

        Args:
            subagent_id: Subagent ID

        Returns:
            Last result or None
        """
        if subagent_id not in self.subagents:
            return None

        return self.subagents[subagent_id].result

    def get_subagent(self, subagent_id: str) -> Optional[SubagentProcess]:
        """
        Get subagent by ID

        Args:
            subagent_id: Subagent ID

        Returns:
            SubagentProcess or None
        """
        return self.subagents.get(subagent_id)

    def list_subagents(self) -> List[Dict]:
        """
        List all subagents

        Returns:
            List of subagent status dictionaries
        """
        return [subagent.get_status() for subagent in self.subagents.values()]

    def kill(self, subagent_id: str) -> bool:
        """
        Kill a subagent

        Args:
            subagent_id: Subagent ID

        Returns:
            True if killed, False if not found
        """
        if subagent_id not in self.subagents:
            return False

        self.subagents[subagent_id].kill()
        return True

    def kill_all(self):
        """Kill all subagents"""
        for subagent in self.subagents.values():
            subagent.kill()

    def cleanup_completed(self):
        """Remove completed subagents"""
        to_remove = [
            sid for sid, subagent in self.subagents.items()
            if subagent.status in [SubagentStatus.COMPLETED, SubagentStatus.FAILED, SubagentStatus.KILLED]
        ]
        for sid in to_remove:
            del self.subagents[sid]

    def get_stats(self) -> Dict:
        """
        Get manager statistics

        Returns:
            Statistics dictionary
        """
        status_counts = {}
        for status in SubagentStatus:
            status_counts[status.value] = sum(
                1 for s in self.subagents.values()
                if s.status == status
            )

        return {
            'total_subagents': len(self.subagents),
            'status_counts': status_counts,
            'created_at': self.created_at.isoformat()
        }


# Example usage
if __name__ == "__main__":
    from .config import AgentConfig

    try:
        # Create manager
        config = AgentConfig.from_env()
        manager = SubagentManager(config)

        print(f"SubagentManager created")
        print(f"Stats: {manager.get_stats()}")

        # Spawn subagent
        subagent = manager.spawn(SubagentConfig(
            name="test-agent",
            role="executor",
            parent_id="main"
        ))

        print(f"\nSpawned subagent: {subagent.id}")
        print(f"Status: {subagent.get_status()}")

        # List subagents
        print(f"\nActive subagents: {manager.list_subagents()}")

        # Cleanup
        manager.kill_all()
        print("\nAll subagents killed")

    except Exception as e:
        print(f"Error: {e}")
        print("Make sure .env is configured")
