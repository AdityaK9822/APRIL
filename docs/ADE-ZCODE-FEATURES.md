# ADE Features: ZCode-Inspired Architecture

**APRIL ADE with capabilities similar to ZCode's Agent Development Environment**

---

## ZCode Feature Mapping

ZCode provides a sophisticated agent development platform. Here's how APRIL's ADE can implement similar capabilities:

| ZCode Feature | APRIL ADE Equivalent | Purpose |
|---------------|---------------------|---------|
| **Skills** | Skill Library | Reusable capabilities loaded dynamically |
| **Agents** | Subagent Manager | Spawn specialized agents for tasks |
| **Workflows** | Dynamic Workflows | TypeScript/Python orchestration scripts |
| **MCP Servers** | MCP Client Layer | External tool integration |
| **Background Tasks** | Async Task Runner | Long-running operations |
| **Session Context** | Session Manager | Persistent conversation state |
| **Permissions** | Safety Engine | Approval flows for risky actions |
| **Todo Tracking** | Project Manager | Task lists and progress tracking |
| **Scheduling** | Cron System | Automate recurring tasks |
| **Visual Output** | Multi-modal Output | Images, videos, rendered content |

---

## Core Features Implementation

### 1. Skills System

**Like ZCode:** Load skills dynamically from markdown files

```python
# core/skills_system.py
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass
import yaml

@dataclass
class Skill:
    """Similar to ZCode skills"""
    name: str
    description: str
    instructions: str  # Main content (markdown)
    tools: List[str]   # Required MCP servers
    triggers: List[str]  # Auto-load on these patterns
    metadata: Dict
    
class SkillLoader:
    """Dynamic skill loading (like ZCode)"""
    
    def __init__(self, skill_paths: List[Path]):
        self.skill_paths = skill_paths
        self.loaded_skills: Dict[str, Skill] = {}
        self.skill_triggers: Dict[str, str] = {}  # pattern -> skill_name
    
    def discover_skills(self):
        """Auto-discover skills from paths"""
        for skill_dir in self.skill_paths:
            for skill_file in skill_dir.glob("**/SKILL.md"):
                self._load_skill(skill_file)
    
    def _load_skill(self, skill_file: Path):
        """Load skill from markdown file"""
        content = skill_file.read_text()
        
        # Parse frontmatter (like ZCode)
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                instructions = parts[2].strip()
                
                skill = Skill(
                    name=frontmatter.get("name", skill_file.parent.name),
                    description=frontmatter.get("description", ""),
                    instructions=instructions,
                    tools=frontmatter.get("tools", []),
                    triggers=frontmatter.get("triggers", []),
                    metadata=frontmatter
                )
                
                self.loaded_skills[skill.name] = skill
                
                # Register triggers
                for pattern in skill.triggers:
                    self.skill_triggers[pattern] = skill.name
    
    def match_skill(self, user_input: str) -> List[Skill]:
        """Match user input to skills (like ZCode auto-trigger)"""
        matched = []
        for pattern, skill_name in self.skill_triggers.items():
            if pattern.lower() in user_input.lower():
                if skill_name in self.loaded_skills:
                    matched.append(self.loaded_skills[skill_name])
        return matched
    
    def get_skill(self, name: str) -> Skill:
        """Get skill by name"""
        return self.loaded_skills.get(name)
```

**Example Skill Structure (like ZCode SKILL.md):**

```markdown
---
name: wifi-audit
description: Perform security audit of wifi networks
tools:
  - mcp-network-scanner
  - mcp-wifi-tools
triggers:
  - audit
  - wifi
  - network security
risk_level: medium
requires_approval: true
constraints:
  - Only on owned networks
  - Authorization required
---

# WiFi Audit Skill

## Purpose
Audit wifi networks for security vulnerabilities.

## Workflow
1. **Discovery**: Scan for connected devices
2. **Vulnerability Assessment**: Check encryption, open ports
3. **Report Generation**: Markdown findings

## Safety
- Confirm network ownership before scanning
- Never exploit, only detect
- Generate report, don't fix automatically

## Success Criteria
- All devices listed
- Vulnerabilities documented
- Recommendations provided
```

---

### 2. Subagent Manager

**Like ZCode's Agent tool:** Spawn specialized agents

```python
# core/subagent_manager.py
from typing import Dict, Optional
from dataclasses import dataclass
import asyncio

@dataclass
class SubagentConfig:
    """Configuration for subagent (like ZCode Agent parameters)"""
    name: str
    description: str
    skills: List[str]  # Skills to load
    model: Optional[str] = None  # Override model
    tools: Optional[List[str]] = None  # MCP servers needed
    max_iterations: int = 100
    timeout: int = 300

class SubagentManager:
    """Spawn and manage subagents (like ZCode Agent tool)"""
    
    def __init__(self, agent_runtime, skill_loader, mcp_manager):
        self.runtime = agent_runtime
        self.skills = skill_loader
        self.mcp = mcp_manager
        self.active_subagents: Dict[str, 'Subagent'] = {}
    
    async def spawn(
        self,
        config: SubagentConfig,
        task: str,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Spawn subagent for a task (like ZCode Agent tool)
        
        Returns: Agent result with status, output, tokens used
        """
        
        # Create subagent instance
        subagent = Subagent(
            config=config,
            runtime=self.runtime,
            skill_loader=self.skills,
            mcp_manager=self.mcp
        )
        
        # Load skills
        for skill_name in config.skills:
            skill = self.skills.get_skill(skill_name)
            if skill:
                subagent.load_skill(skill)
        
        # Execute task
        result = await subagent.execute(task, context)
        
        return result
    
    async def spawn_background(
        self,
        config: SubagentConfig,
        task: str,
        context: Optional[Dict] = None
    ) -> str:
        """
        Spawn subagent in background (like ZCode run_in_background)
        
        Returns: task_id for tracking
        """
        
        task_id = self._generate_task_id()
        
        # Store subagent
        self.active_subagents[task_id] = Subagent(
            config=config,
            runtime=self.runtime,
            skill_loader=self.skills,
            mcp_manager=self.mcp
        )
        
        # Run in background
        asyncio.create_task(
            self._run_subagent_background(task_id, task, context)
        )
        
        return task_id
    
    async def get_status(self, task_id: str) -> Dict:
        """Check subagent status (like ZCode TaskOutput)"""
        if task_id not in self.active_subagents:
            return {"status": "not_found"}
        
        subagent = self.active_subagents[task_id]
        return {
            "status": subagent.status,
            "progress": subagent.progress,
            "output": subagent.partial_output
        }
    
    async def stop(self, task_id: str) -> bool:
        """Stop subagent (like ZCode TaskStop)"""
        if task_id in self.active_subagents:
            self.active_subagents[task_id].cancel()
            return True
        return False

class Subagent:
    """Individual subagent instance"""
    
    def __init__(self, config, runtime, skill_loader, mcp_manager):
        self.config = config
        self.runtime = runtime
        self.skills = skill_loader
        self.mcp = mcp_manager
        self.loaded_skills: List[Skill] = []
        self.status = "pending"
        self.progress = 0
        self.partial_output = ""
    
    def load_skill(self, skill: Skill):
        """Load skill instructions into context"""
        self.loaded_skills.append(skill)
    
    async def execute(self, task: str, context: Optional[Dict] = None) -> Dict:
        """Execute task with loaded skills"""
        
        self.status = "running"
        
        # Build system prompt from skills
        system_prompt = self._build_system_prompt()
        
        # Build tools list from MCP servers
        tools = self._build_tools_list()
        
        # Execute
        try:
            result = await self.runtime.run_with_skills(
                system_prompt=system_prompt,
                tools=tools,
                user_input=task,
                context=context,
                max_iterations=self.config.max_iterations,
                timeout=self.config.timeout
            )
            
            self.status = "completed"
            return {
                "status": "success",
                "output": result,
                "tokens_used": self.runtime.tokens_used
            }
        
        except asyncio.TimeoutError:
            self.status = "timeout"
            return {"status": "error", "error": "Timeout"}
        
        except Exception as e:
            self.status = "failed"
            return {"status": "error", "error": str(e)}
    
    def _build_system_prompt(self) -> str:
        """Build system prompt from loaded skills"""
        prompt_parts = []
        
        for skill in self.loaded_skills:
            prompt_parts.append(f"## {skill.name}\n{skill.instructions}")
        
        return "\n\n".join(prompt_parts)
```

---

### 3. Dynamic Workflows

**Like ZCode's CreateWorkflow:** Orchestrate multiple steps

```python
# core/workflow_engine.py
from typing import Dict, List, Any
from dataclasses import dataclass
import asyncio

@dataclass
class WorkflowStep:
    """Single workflow step"""
    name: str
    agent_config: SubagentConfig
    task: str
    depends_on: List[str] = None
    
@dataclass
class WorkflowResult:
    """Result from workflow execution"""
    workflow_id: str
    status: str
    steps_completed: List[str]
    steps_failed: List[str]
    artifacts: Dict[str, Any]
    total_tokens: int

class WorkflowEngine:
    """
    Dynamic workflow orchestration (like ZCode CreateWorkflow)
    
    Features:
    - Define multi-step workflows
    - Parallel execution
    - Dependencies between steps
    - Fan-out/fan-in patterns
    - Error handling and retry
    - Artifact collection
    """
    
    def __init__(self, subagent_manager):
        self.subagent_manager = subagent_manager
        self.workflows: Dict[str, 'Workflow'] = {}
    
    async def create_workflow(
        self,
        name: str,
        steps: List[WorkflowStep],
        max_concurrency: int = 5
    ) -> str:
        """
        Create workflow (like ZCode CreateWorkflow)
        
        Returns: workflow_id
        """
        
        workflow_id = self._generate_workflow_id(name)
        
        workflow = Workflow(
            id=workflow_id,
            name=name,
            steps=steps,
            max_concurrency=max_concurrency
        )
        
        self.workflows[workflow_id] = workflow
        
        # Execute workflow
        asyncio.create_task(self._execute_workflow(workflow))
        
        return workflow_id
    
    async def _execute_workflow(self, workflow: 'Workflow'):
        """Execute workflow with dependency management"""
        
        workflow.status = "running"
        completed_steps = set()
        failed_steps = set()
        
        # Build dependency graph
        dependency_graph = self._build_dependency_graph(workflow.steps)
        
        # Execute steps respecting dependencies
        while len(completed_steps) < len(workflow.steps):
            # Find ready steps (dependencies satisfied)
            ready_steps = [
                step for step in workflow.steps
                if step.name not in completed_steps
                and step.name not in failed_steps
                and self._dependencies_met(step, completed_steps)
            ]
            
            if not ready_steps:
                # Check for deadlock
                if failed_steps:
                    workflow.status = "partial_failure"
                    break
                else:
                    workflow.status = "deadlock"
                    break
            
            # Execute ready steps (up to max_concurrency)
            batch = ready_steps[:workflow.max_concurrency]
            
            tasks = [
                self._execute_step(workflow, step)
                for step in batch
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for step, result in zip(batch, results):
                if isinstance(result, Exception):
                    failed_steps.add(step.name)
                    workflow.step_results[step.name] = {
                        "status": "error",
                        "error": str(result)
                    }
                else:
                    completed_steps.add(step.name)
                    workflow.step_results[step.name] = result
        
        workflow.status = "completed" if not failed_steps else "partial"
    
    async def _execute_step(self, workflow: 'Workflow', step: WorkflowStep) -> Dict:
        """Execute single workflow step"""
        
        result = await self.subagent_manager.spawn(
            config=step.agent_config,
            task=step.task,
            context=workflow.context
        )
        
        # Collect artifacts
        if "artifacts" in result:
            workflow.artifacts.update(result["artifacts"])
        
        return result
    
    async def get_workflow_status(self, workflow_id: str) -> Dict:
        """Get workflow status (like ZCode GetWorkflowRun)"""
        
        if workflow_id not in self.workflows:
            return {"error": "Workflow not found"}
        
        workflow = self.workflows[workflow_id]
        
        return {
            "id": workflow.id,
            "name": workflow.name,
            "status": workflow.status,
            "steps_completed": list(workflow.steps_completed),
            "steps_failed": list(workflow.steps_failed),
            "artifacts": workflow.artifacts,
            "total_tokens": workflow.total_tokens
        }
    
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel workflow (like ZCode AmendWorkflow)"""
        
        if workflow_id in self.workflows:
            workflow = self.workflows[workflow_id]
            workflow.status = "cancelled"
            # Cancel all active subagents
            for task_id in workflow.active_tasks:
                await self.subagent_manager.stop(task_id)
            return True
        
        return False

# Workflow definition DSL (like ZCode workflows)
class WorkflowBuilder:
    """Build workflows programmatically"""
    
    def __init__(self, name: str):
        self.name = name
        self.steps: List[WorkflowStep] = []
        self.max_concurrency = 5
    
    def add_step(
        self,
        name: str,
        agent_config: SubagentConfig,
        task: str,
        depends_on: List[str] = None
    ):
        """Add workflow step"""
        self.steps.append(WorkflowStep(
            name=name,
            agent_config=agent_config,
            task=task,
            depends_on=depends_on or []
        ))
        return self
    
    def set_concurrency(self, max_concurrency: int):
        """Set max parallel steps"""
        self.max_concurrency = max_concurrency
        return self
    
    def build(self) -> 'Workflow':
        """Build workflow"""
        return Workflow(
            id=None,
            name=self.name,
            steps=self.steps,
            max_concurrency=self.max_concurrency
        )
```

**Example Workflow (like ZCode):**

```python
# Example: Bracket fabrication workflow
workflow = (WorkflowBuilder("3d-print-bracket")
    .add_step(
        name="design",
        agent_config=SubagentConfig(
            name="cad-designer",
            skills=["cad-design"],
            tools=["mcp-freecad"]
        ),
        task="Design a bracket 50x30mm with 30° angle"
    )
    .add_step(
        name="slice",
        agent_config=SubagentConfig(
            name="slicer",
            skills=["fdm-slicing"],
            tools=["mcp-prusa-slicer"]
        ),
        task="Slice bracket.step for PLA at 0.2mm layer height",
        depends_on=["design"]  # Wait for design step
    )
    .add_step(
        name="print",
        agent_config=SubagentConfig(
            name="printer-controller",
            skills=["3d-printing"],
            tools=["mcp-octoprint"]
        ),
        task="Print bracket.gcode",
        depends_on=["slice"]  # Wait for slicing
    )
    .build()
)

workflow_id = await workflow_engine.create_workflow(
    name="print-bracket",
    steps=workflow.steps,
    max_concurrency=2  # Design and slice can run in parallel
)
```

---

### 4. Background Tasks

**Like ZCode's run_in_background:** Asynchronous task execution

```python
# core/background_tasks.py
from typing import Dict, Callable
from dataclasses import dataclass
import asyncio

@dataclass
class BackgroundTask:
    """Background task (like ZCode background tasks)"""
    id: str
    name: str
    status: str  # pending, running, completed, failed
    progress: float
    result: Any
    error: Optional[str]

class BackgroundTaskManager:
    """Manage background tasks (like ZCode)"""
    
    def __init__(self):
        self.tasks: Dict[str, BackgroundTask] = {}
    
    async def run_background(
        self,
        task_func: Callable,
        task_name: str,
        *args,
        **kwargs
    ) -> str:
        """
        Run task in background (like ZCode run_in_background)
        
        Returns: task_id
        """
        
        task_id = self._generate_task_id(task_name)
        
        task = BackgroundTask(
            id=task_id,
            name=task_name,
            status="pending",
            progress=0,
            result=None,
            error=None
        )
        
        self.tasks[task_id] = task
        
        # Run in background
        asyncio.create_task(self._run_task(task, task_func, args, kwargs))
        
        return task_id
    
    async def _run_task(self, task: BackgroundTask, func: Callable, args, kwargs):
        """Execute task in background"""
        
        task.status = "running"
        task.progress = 0
        
        try:
            # Execute with progress updates
            result = await func(*args, **kwargs)
            
            task.status = "completed"
            task.progress = 100
            task.result = result
        
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
    
    async def get_task_output(self, task_id: str) -> Dict:
        """Get task output (like ZCode TaskOutput)"""
        
        if task_id not in self.tasks:
            return {"error": "Task not found"}
        
        task = self.tasks[task_id]
        
        return {
            "id": task.id,
            "name": task.name,
            "status": task.status,
            "progress": task.progress,
            "result": task.result if task.status == "completed" else None,
            "error": task.error
        }
    
    async def stop_task(self, task_id: str) -> bool:
        """Stop task (like ZCode TaskStop)"""
        
        # Implementation would cancel the asyncio task
        pass
```

---

### 5. Permission & Approval System

**Like ZCode's permission prompts:** Ask user for risky actions

```python
# core/permission_system.py
from enum import Enum
from typing import Callable, Optional

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class PermissionSystem:
    """
    Permission system (like ZCode approval flows)
    
    Three modes:
    - yolo: Auto-approve all
    - auto: Auto-approve low/medium, prompt high/critical
    - interactive: Always prompt
    """
    
    def __init__(self, mode: str = "auto"):
        self.mode = mode
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self.approval_callback: Optional[Callable] = None
    
    async def check_permission(
        self,
        action: str,
        risk_level: RiskLevel,
        context: Dict
    ) -> bool:
        """
        Check if action is permitted (like ZCode permission flow)
        
        Returns: True if approved
        """
        
        # Auto-approve based on mode
        if self.mode == "yolo":
            return True
        
        if self.mode == "auto":
            if risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]:
                return True
        
        # Need approval
        approval_id = self._generate_approval_id()
        
        request = ApprovalRequest(
            id=approval_id,
            action=action,
            risk_level=risk_level,
            context=context,
            status="pending"
        )
        
        self.pending_approvals[approval_id] = request
        
        # Prompt user (like ZCode AskUserQuestion)
        if self.approval_callback:
            approved = await self.approval_callback(request)
        else:
            approved = self._default_prompt(request)
        
        request.status = "approved" if approved else "denied"
        
        return approved
    
    def _default_prompt(self, request: 'ApprovalRequest') -> bool:
        """Default CLI prompt for approval"""
        
        print(f"\n[APPROVAL REQUIRED]")
        print(f"  Action: {request.action}")
        print(f"  Risk: {request.risk_level.value}")
        print(f"  Context: {request.context}")
        
        response = input("Approve? [y/N]: ")
        return response.lower() in ["y", "yes"]

@dataclass
class ApprovalRequest:
    id: str
    action: str
    risk_level: RiskLevel
    context: Dict
    status: str
    response: Optional[str] = None
```

---

### 6. Todo Tracking

**Like ZCode's TodoWrite:** Track tasks and progress

```python
# core/todo_tracker.py
from typing import List
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TodoItem:
    """Todo item (like ZCode todos)"""
    content: str
    status: str  # pending, in_progress, completed
    priority: str  # high, medium, low

class TodoTracker:
    """Todo tracking (like ZCode TodoWrite/TodoRead)"""
    
    def __init__(self):
        self.todos: List[TodoItem] = []
        self.callbacks: List[Callable] = []
    
    def read(self) -> List[Dict]:
        """Read todos (like ZCode TodoRead)"""
        return [
            {
                "content": todo.content,
                "status": todo.status,
                "priority": todo.priority
            }
            for todo in self.todos
        ]
    
    def write(self, todos: List[Dict]):
        """Write todos (like ZCode TodoWrite)"""
        
        new_todos = [
            TodoItem(
                content=item["content"],
                status=item["status"],
                priority=item.get("priority", "medium")
            )
            for item in todos
        ]
        
        self.todos = new_todos
        
        # Notify listeners
        for callback in self.callbacks:
            callback(self.todos)
    
    def add_callback(self, callback: Callable):
        """Add callback for todo updates"""
        self.callbacks.append(callback)
```

---

### 7. Scheduling System

**Like ZCode's CronCreate:** Schedule recurring tasks

```python
# core/scheduler.py
from typing import Callable
from dataclasses import dataclass
import asyncio
from datetime import datetime, timedelta

@dataclass
class ScheduledTask:
    """Scheduled task (like ZCode automations)"""
    id: str
    name: str
    schedule: str  # cron expression or interval
    task_func: Callable
    args: tuple
    kwargs: dict
    last_run: datetime = None
    next_run: datetime = None
    enabled: bool = True

class Scheduler:
    """Task scheduling (like ZCode CronCreate)"""
    
    def __init__(self):
        self.scheduled_tasks: Dict[str, ScheduledTask] = {}
        self.running = False
    
    async def create(
        self,
        name: str,
        schedule: str,
        task_func: Callable,
        *args,
        **kwargs
    ) -> str:
        """
        Create scheduled task (like ZCode CronCreate)
        
        Args:
            schedule: Cron expression or "every N minutes"
        """
        
        task_id = self._generate_task_id(name)
        
        task = ScheduledTask(
            id=task_id,
            name=name,
            schedule=schedule,
            task_func=task_func,
            args=args,
            kwargs=kwargs
        )
        
        self.scheduled_tasks[task_id] = task
        
        # Start scheduler if not running
        if not self.running:
            asyncio.create_task(self._scheduler_loop())
        
        return task_id
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        
        self.running = True
        
        while True:
            now = datetime.now()
            
            for task in self.scheduled_tasks.values():
                if task.enabled and self._should_run(task, now):
                    # Execute task
                    asyncio.create_task(
                        self._execute_task(task)
                    )
                    task.last_run = now
            
            # Check every minute
            await asyncio.sleep(60)
    
    async def _execute_task(self, task: ScheduledTask):
        """Execute scheduled task"""
        try:
            await task.task_func(*task.args, **task.kwargs)
        except Exception as e:
            print(f"Scheduled task {task.name} failed: {e}")
    
    def _should_run(self, task: ScheduledTask, now: datetime) -> bool:
        """Check if task should run based on schedule"""
        # Parse cron or interval
        # Simplified: just check "every N minutes"
        if "every" in task.schedule:
            minutes = int(task.schedule.split()[1])
            if task.last_run:
                return (now - task.last_run) >= timedelta(minutes=minutes)
            return True
        return False
```

---

### 8. Multi-modal Output

**Like ZCode's image/video support:** Rich output rendering

```python
# core/multimodal_output.py
from typing import Union
from pathlib import Path
import base64

class MultiModalOutput:
    """
    Multi-modal output (like ZCode)
    
   Supports:
    - Text
    - Images (PNG, JPG)
    - Videos (MP4, etc.)
    - Documents (PDF, DOCX, etc.)
    - Code blocks
    - Markdown
    """
    
    def __init__(self):
        self.outputs: List[Dict] = []
    
    def text(self, content: str):
        """Add text output"""
        self.outputs.append({
            "type": "text",
            "content": content
        })
    
    def image(self, path: Path, caption: str = ""):
        """Add image output (like ZCode Read for images)"""
        self.outputs.append({
            "type": "image",
            "path": str(path),
            "caption": caption,
            "base64": self._encode_image(path)
        })
    
    def video(self, path: Path, caption: str = ""):
        """Add video output"""
        self.outputs.append({
            "type": "video",
            "path": str(path),
            "caption": caption
        })
    
    def code(self, code: str, language: str = ""):
        """Add code block"""
        self.outputs.append({
            "type": "code",
            "content": code,
            "language": language
        })
    
    def markdown(self, content: str):
        """Add markdown content"""
        self.outputs.append({
            "type": "markdown",
            "content": content
        })
    
    def document(self, path: Path, doc_type: str):
        """Add document output"""
        self.outputs.append({
            "type": "document",
            "path": str(path),
            "doc_type": doc_type
        })
    
    def render(self) -> List[Dict]:
        """Render all outputs"""
        return self.outputs
    
    def _encode_image(self, path: Path) -> str:
        """Encode image as base64"""
        return base64.b64encode(path.read_bytes()).decode()
```

---

## Complete ADE Architecture (ZCode-Inspired)

```python
# ade/april_ade.py
from pathlib import Path

class AprilADE:
    """
    Complete ADE with ZCode-inspired features
    
    Features:
    - Skills (dynamic loading)
    - Subagents (spawn agents)
    - Workflows (orchestrate multiple steps)
    - MCP servers (tool integration)
    - Background tasks
    - Permissions/approvals
    - Todo tracking
    - Scheduling
    - Multi-modal output
    """
    
    def __init__(self, config_path: Path = None):
        # Core components (like ZCode)
        self.skill_loader = SkillLoader(skill_paths=[])
        self.mcp_manager = MCPManager()
        self.subagent_manager: SubagentManager = None
        self.workflow_engine: WorkflowEngine = None
        self.background_tasks = BackgroundTaskManager()
        self.permissions = PermissionSystem(mode="auto")
        self.todos = TodoTracker()
        self.scheduler = Scheduler()
        self.session_manager = SessionManager()
        
        # Load config
        if config_path:
            self._load_config(config_path)
        
        # Initialize components
        self._initialize()
    
    def _initialize(self):
        """Initialize all components"""
        # Discover skills
        self.skill_loader.discover_skills()
        
        # Initialize subagent manager
        self.subagent_manager = SubagentManager(
            agent_runtime=AgentRuntime(),
            skill_loader=self.skill_loader,
            mcp_manager=self.mcp_manager
        )
        
        # Initialize workflow engine
        self.workflow_engine = WorkflowEngine(
            subagent_manager=self.subagent_manager
        )
    
    async def chat(self, user_input: str) -> MultiModalOutput:
        """
        Main chat interface (like ZCode chat)
        
        Handles:
        - Skill matching
        - Permission checks
        - Subagent spawning
        - Output rendering
        """
        
        # Match skills (auto-load)
        matched_skills = self.skill_loader.match_skill(user_input)
        
        # Create subagent with matched skills
        if matched_skills:
            config = SubagentConfig(
                name="matched-agent",
                skills=[s.name for s in matched_skills],
                tools=sum([s.tools for s in matched_skills], [])
            )
            
            result = await self.subagent_manager.spawn(
                config=config,
                task=user_input,
                context=self.session_manager.get_context()
            )
            
            # Update session
            self.session_manager.add_interaction(user_input, result)
            
            # Render output
            output = MultiModalOutput()
            output.text(result["output"])
            
            return output
        
        # Default: spawn general agent
        # ...
    
    async def create_workflow(self, name: str, steps: List[Dict]) -> str:
        """Create workflow (like ZCode CreateWorkflow)"""
        # Build workflow from steps
        # ...
    
    async def spawn_agent(
        self,
        skills: List[str],
        task: str,
        background: bool = False
    ) -> str:
        """Spawn agent (like ZCode Agent tool)"""
        # ...
    
    async def schedule_task(
        self,
        name: str,
        schedule: str,
        task_func: Callable
    ) -> str:
        """Schedule task (like ZCode CronCreate)"""
        return await self.scheduler.create(name, schedule, task_func)
```

---

## Usage Examples

### Example 1: Load and use skills (like ZCode)

```python
# Initialize ADE
ade = AprilADE(config_path=Path(".ade/config.yaml"))

# Skills auto-loaded from .ade/skills/
# Trigger skill by keyword
response = await ade.chat("Audit my wifi network")
# Auto-loads wifi-audit skill
```

### Example 2: Spawn subagent (like ZCode Agent)

```python
# Spawn specialized agent
task_id = await ade.spawn_agent(
    skills=["esp32-telemetry"],
    task="Read temperature from all sensors",
    background=True  # Like ZCode run_in_background
)

# Check status
status = await ade.background_tasks.get_task_output(task_id)
```

### Example 3: Create workflow (like ZCode CreateWorkflow)

```python
# Define workflow
workflow_id = await ade.create_workflow(
    name="print-bracket",
    steps=[
        {
            "name": "design",
            "skills": ["cad-design"],
            "task": "Design bracket 30°"
        },
        {
            "name": "slice",
            "skills": ["slicing"],
            "task": "Slice for PLA",
            "depends_on": ["design"]
        },
        {
            "name": "print",
            "skills": ["3d-printing"],
            "task": "Print bracket",
            "depends_on": ["slice"]
        }
    ]
)
```

### Example 4: Schedule recurring task (like ZCode CronCreate)

```python
# Schedule telemetry logging
await ade.schedule_task(
    name="log-temperature",
    schedule="every 5 minutes",
    task_func=lambda: log_all_temperatures()
)
```

---

## Summary: ZCode-Feature Parity

| Feature | ZCode | APRIL ADE | Status |
|---------|-------|-----------|--------|
| Skills | ✅ | ✅ Skill Library | Designed |
| Agents | ✅ | ✅ Subagent Manager | Designed |
| Workflows | ✅ | ✅ Workflow Engine | Designed |
| MCP Servers | ✅ | ✅ MCP Client Layer | Designed |
| Background Tasks | ✅ | ✅ Background Task Manager | Designed |
| Permissions | ✅ | ✅ Permission System | Designed |
| Todo Tracking | ✅ | ✅ Todo Tracker | Designed |
| Scheduling | ✅ | ✅ Scheduler | Designed |
| Multi-modal | ✅ | ✅ Multi-modal Output | Designed |
| Session Context | ✅ | ✅ Session Manager | Designed |

**All core ZCode features mapped to APRIL ADE architecture!**

---

## Next Steps

1. **Review this design** - Does this match your vision?
2. **Prioritize features** - Which to build first?
3. **Start implementation** - Begin with Skills + MCP client layer
4. **Iterate** - Add features incrementally

**Ready to build ZCode-inspired ADE for APRIL!** 🚀
