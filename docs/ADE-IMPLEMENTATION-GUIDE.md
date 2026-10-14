# ADE Implementation Guide

**Concrete patterns and code examples for building APRIL's Agent Development Environment**

---

## Core Runtime Implementation

### Agent Execution Loop

```python
# core/agent_runtime.py
from typing import Generator, Callable
from dataclasses import dataclass
import openai

@dataclass
class AgentState:
    model: str
    context: list[dict]  # conversation history
    tools: dict[str, Callable]
    max_iterations: int = 100
    
class AgentRuntime:
    def __init__(self, model: str, tools: dict[str, Callable]):
        self.state = AgentState(
            model=model,
            context=[],
            tools=tools
        )
    
    def run(self, user_request: str) -> Generator[dict, None, None]:
        """Execute agent loop with streaming updates"""
        
        # Add user request to context
        self.state.context.append({
            "role": "user",
            "content": user_request
        })
        
        iteration = 0
        while iteration < self.state.max_iterations:
            # Call LLM
            response = openai.chat.completions.create(
                model=self.state.model,
                messages=self.state.context,
                tools=self._format_tools(),
                tool_choice="auto"
            )
            
            msg = response.choices[0].message
            
            # Stream update
            yield {
                "type": "reasoning",
                "content": msg.content,
                "iteration": iteration
            }
            
            # Check if done
            if msg.content and not msg.tool_calls:
                self.state.context.append({
                    "role": "assistant",
                    "content": msg.content
                })
                yield {"type": "complete", "content": msg.content}
                return
            
            # Execute tool calls
            if msg.tool_calls:
                self.state.context.append(msg.to_dict())
                
                for tool_call in msg.tool_calls:
                    result = self._execute_tool(tool_call)
                    
                    yield {
                        "type": "tool_call",
                        "name": tool_call.function.name,
                        "input": tool_call.function.arguments,
                        "output": result
                    }
                    
                    # Add result to context
                    self.state.context.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result)
                    })
            
            iteration += 1
        
        yield {"type": "error", "content": "Max iterations exceeded"}
    
    def _execute_tool(self, tool_call) -> dict:
        """Safely execute tool with error handling"""
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        
        if tool_name not in self.state.tools:
            return {"error": f"Unknown tool: {tool_name}"}
        
        try:
            result = self.state.tools[tool_name](**tool_args)
            return {"success": True, "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    def _format_tools(self) -> list[dict]:
        """Format tools for OpenAI API"""
        # Implementation would introspect function signatures
        # and generate JSON schemas
        pass


# Usage
if __name__ == "__main__":
    tools = {
        "shell_execute": shell_execute,
        "file_read": file_read,
        "file_write": file_write
    }
    
    runtime = AgentRuntime(model="mistral-large", tools=tools)
    
    for update in runtime.run("Print hello world"):
        if update["type"] == "reasoning":
            print(f"[{update['iteration']}] {update['content']}")
        elif update["type"] == "tool_call":
            print(f"  Tool: {update['name']} → {update['output']}")
        elif update["type"] == "complete":
            print(f"Done: {update['content']}")
```

### Tool Framework

```python
# core/tool_framework.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable
import inspect
import json

@dataclass
class ToolMetadata:
    name: str
    description: str
    domain: str
    risk_level: str  # low, medium, high, critical
    input_schema: dict
    output_schema: dict

class Tool(ABC):
    """Base class for all APRIL tools"""
    
    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        pass
    
    def to_openai_schema(self) -> dict:
        """Convert to OpenAI tool schema"""
        return {
            "type": "function",
            "function": {
                "name": self.metadata.name,
                "description": self.metadata.description,
                "parameters": self.metadata.input_schema
            }
        }


# Example tool implementation
class ShellTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="shell_execute",
            description="Execute a shell command on the machine",
            domain="machine",
            risk_level="medium",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 30)",
                        "default": 30
                    }
                },
                "required": ["command"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "stdout": {"type": "string"},
                    "stderr": {"type": "string"},
                    "return_code": {"type": "integer"}
                }
            }
        )
    
    def execute(self, command: str, timeout: int = 30) -> dict:
        """Execute shell command"""
        import subprocess
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }


# Tool registry
class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool):
        if tool.metadata.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.metadata.name}")
        self._tools[tool.metadata.name] = tool
    
    def get(self, name: str) -> Tool:
        return self._tools.get(name)
    
    def all_schemas(self) -> list[dict]:
        return [tool.to_openai_schema() for tool in self._tools.values()]
    
    def execute(self, name: str, **kwargs) -> Any:
        tool = self.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        return tool.execute(**kwargs)


# Usage
registry = ToolRegistry()
registry.register(ShellTool())
registry.register(FileReadTool())
registry.register(FileWriteTool())

# In agent runtime
openai_tools = registry.all_schemas()

# When tool call happens
result = registry.execute("shell_execute", command="ls -la")
```

---

## Device Registry Implementation

### Device Model

```python
# core/device_registry.py
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import asyncio

class Domain(Enum):
    VISION = "vision"
    SENSING = "sensing"
    HOME = "home"
    ROBOTICS = "robotics"
    NETWORK = "network"
    FABRICATION = "fabrication"

class Risk(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Status(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    FAULTED = "faulted"

@dataclass
class Device:
    name: str
    domain: Domain
    capabilities: list[str]
    risk_level: Risk
    endpoint: str
    metadata: dict = field(default_factory=dict)
    status: Status = Status.OFFLINE
    last_seen: Optional[datetime] = None
    
    def health_check(self) -> bool:
        """Verify device is reachable"""
        # Override in subclass
        raise NotImplementedError
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "domain": self.domain.value,
            "capabilities": self.capabilities,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "endpoint": self.endpoint,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None
        }
```

### ESP32 Device Example

```python
# devices/esp32_telemetry.py
from core.device_registry import Device, Domain, Risk, Status
import requests
from datetime import datetime

class ESP32Telemetry(Device):
    def __init__(self, name: str, endpoint: str):
        super().__init__(
            name=name,
            domain=Domain.SENSING,
            capabilities=[
                "read_temperature",
                "read_humidity",
                "read_pressure"
            ],
            risk_level=Risk.LOW,
            endpoint=endpoint
        )
    
    def health_check(self) -> bool:
        """Check if ESP32 is reachable"""
        try:
            response = requests.get(
                f"{self.endpoint}/health",
                timeout=5
            )
            
            if response.status_code == 200:
                self.status = Status.ONLINE
                self.last_seen = datetime.now()
                return True
        except:
            pass
        
        self.status = Status.OFFLINE
        return False
    
    def read_temperature(self) -> float:
        """Read temperature from sensor"""
        response = requests.get(f"{self.endpoint}/temperature")
        data = response.json()
        return data["temperature_celsius"]
    
    def read_humidity(self) -> float:
        """Read humidity from sensor"""
        response = requests.get(f"{self.endpoint}/humidity")
        data = response.json()
        return data["humidity_percent"]
```

### Device Registry Manager

```python
# core/device_registry.py (continued)
import asyncio
from typing import Callable

class DeviceRegistry:
    def __init__(self, scan_interval: int = 30):
        self._devices: dict[str, Device] = {}
        self._scan_interval = scan_interval
        self._on_change_callbacks: list[Callable] = []
    
    def register(self, device: Device):
        """Register a device"""
        if device.name in self._devices:
            raise ValueError(f"Device already registered: {device.name}")
        
        self._devices[device.name] = device
        
        # Initial health check
        device.health_check()
        
        # Notify listeners
        self._notify_change(device)
    
    def get(self, name: str) -> Optional[Device]:
        """Get device by name"""
        return self._devices.get(name)
    
    def list(self, domain: Optional[Domain] = None) -> list[Device]:
        """List all devices, optionally filtered by domain"""
        if domain:
            return [d for d in self._devices.values() if d.domain == domain]
        return list(self._devices.values())
    
    def available(self, device_name: str) -> bool:
        """Check if device is available for use"""
        device = self.get(device_name)
        return device and device.status == Status.ONLINE
    
    async def monitor_loop(self):
        """Continuously monitor device health"""
        while True:
            for device in self._devices.values():
                old_status = device.status
                is_alive = device.health_check()
                
                if device.status != old_status:
                    self._notify_change(device)
            
            await asyncio.sleep(self._scan_interval)
    
    def on_change(self, callback: Callable):
        """Register callback for device status changes"""
        self._on_change_callbacks.append(callback)
    
    def _notify_change(self, device: Device):
        for callback in self._on_change_callbacks:
            callback(device)


# Usage
registry = DeviceRegistry()

# Register devices
registry.register(ESP32Telemetry(
    name="esp-lab",
    endpoint="http://192.168.1.100"
))

registry.register(IPCamera(
    name="camera-gate",
    endpoint="rtsp://192.168.1.150:554"
))

# Start monitoring
asyncio.create_task(registry.monitor_loop())

# Query
if registry.available("esp-lab"):
    temp = registry.get("esp-lab").read_temperature()
```

---

## Safety Engine Implementation

```python
# core/safety_engine.py
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass
import ipaddress

class RiskAction(Enum):
    AUTO = "auto"           # Proceed without prompt
    LOG = "log"             # Log and proceed
    PROMPT = "prompt"       # Ask user confirmation
    REQUIRE_CONFIRM = "require_confirm"  # Hard stop, require explicit confirmation

@dataclass
class SafetyPolicy:
    """Safety policy configuration"""
    
    # Network authorization
    owned_networks: list[str]  # CIDR notation e.g., "192.168.1.0/24"
    authorized_networks: list[str]
    
    # Risk thresholds
    risk_thresholds: dict[str, RiskAction] = None
    
    def __post_init__(self):
        if self.risk_thresholds is None:
            self.risk_thresholds = {
                "low": RiskAction.AUTO,
                "medium": RiskAction.LOG,
                "high": RiskAction.PROMPT,
                "critical": RiskAction.REQUIRE_CONFIRM
            }
    
    def check_network_authorization(self, target_ip: str) -> bool:
        """Check if network action is authorized"""
        target = ipaddress.ip_address(target_ip)
        
        # Check owned networks
        for network in self.owned_networks:
            if target in ipaddress.ip_network(network):
                return True
        
        # Check authorized networks
        for network in self.authorized_networks:
            if target in ipaddress.ip_network(network):
                return True
        
        return False
    
    def get_action_for_risk(self, risk_level: str) -> RiskAction:
        """Get action for risk level"""
        return self.risk_thresholds.get(risk_level, RiskAction.LOG)


class SafetyEngine:
    def __init__(self, policy: SafetyPolicy, prompt_func: Optional[Callable] = None):
        self.policy = policy
        self.prompt_func = prompt_func or input
    
    def check_device_action(self, device: Device, action: str) -> tuple[bool, str]:
        """
        Check if action on device is allowed
        Returns: (allowed, reason)
        """
        risk_level = device.risk_level.value
        action_type = self.policy.get_action_for_risk(risk_level)
        
        if action_type == RiskAction.AUTO:
            return True, "Auto-approved"
        
        if action_type == RiskAction.LOG:
            print(f"[SAFETY LOG] {device.name}: {action}")
            return True, "Logged"
        
        if action_type == RiskAction.PROMPT:
            confirmed = self._prompt_user(device, action)
            return confirmed, "User confirmation" if confirmed else "User denied"
        
        if action_type == RiskAction.REQUIRE_CONFIRM:
            # Hard stop - require explicit confirmation
            print(f"[SAFETY STOP] Critical device: {device.name}")
            print(f"  Action: {action}")
            print(f"  Risk: {device.risk_level.value}")
            confirmed = self._require_explicit_confirm(device, action)
            return confirmed, "Explicit confirmation" if confirmed else "Denied"
        
        return False, "Unknown action type"
    
    def check_network_action(self, target_ip: str) -> tuple[bool, str]:
        """
        Check if network action is authorized
        Returns: (allowed, reason)
        """
        if self.policy.check_network_authorization(target_ip):
            return True, "Authorized network"
        
        return False, f"Network not authorized: {target_ip}. Add to owned_networks or authorized_networks."
    
    def _prompt_user(self, device: Device, action: str) -> bool:
        """Prompt user for confirmation"""
        print(f"\n[SAFETY PROMPT] Device: {device.name}")
        print(f"  Action: {action}")
        print(f"  Risk: {device.risk_level.value}")
        
        response = self.prompt_func("Proceed? [y/N]: ")
        return response.lower() in ["y", "yes"]
    
    def _require_explicit_confirm(self, device: Device, action: str) -> bool:
        """Require explicit confirmation for critical devices"""
        print(f"\n[CRITICAL] You are about to control: {device.name}")
        print(f"  Device type: {device.domain.value}")
        print(f"  Risk level: {device.risk_level.value}")
        print(f"  Action: {action}")
        print("\nThis is a CRITICAL device.")
        
        response = self.prompt_func("Type 'CONFIRM' to proceed: ")
        return response == "CONFIRM"


# Usage
policy = SafetyPolicy(
    owned_networks=["192.168.1.0/24", "10.0.0.0/8"],
    authorized_networks=[],
    risk_thresholds={
        "low": RiskAction.AUTO,
        "medium": RiskAction.LOG,
        "high": RiskAction.PROMPT,
        "critical": RiskAction.REQUIRE_CONFIRM
    }
)

safety = SafetyEngine(policy)

# Check device action
cnc_printer = registry.get("cnc-main")
allowed, reason = safety.check_device_action(cnc_printer, "start_spindle")

if allowed:
    # Proceed with action
    cnc_printer.start_spindle()
else:
    print(f"Action denied: {reason}")

# Check network action
allowed, reason = safety.check_network_action("192.168.1.105")
if not allowed:
    print(f"Network action denied: {reason}")
```

---

## Project Manager Implementation

```python
# core/project_manager.py
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from pathlib import Path
import json

class ProjectStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    FAILED = "failed"
    DONE = "done"

@dataclass
class Artifact:
    name: str
    path: Path
    type: str  # model, gcode, firmware, etc.
    created: datetime = field(default_factory=datetime.now)

@dataclass
class Project:
    id: str
    goal: str
    plan: list[dict] = field(default_factory=list)
    status: ProjectStatus = ProjectStatus.PENDING
    artifacts: list[Artifact] = field(default_factory=list)
    devices: list[str] = field(default_factory=list)  # device reservations
    created: datetime = field(default_factory=datetime.now)
    updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "plan": self.plan,
            "status": self.status.value,
            "artifacts": [
                {"name": a.name, "path": str(a.path), "type": a.type}
                for a in self.artifacts
            ],
            "devices": self.devices,
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat()
        }

class ProjectManager:
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._projects: dict[str, Project] = {}
        self._load_projects()
    
    def create(self, goal: str) -> Project:
        """Create new project"""
        project_id = self._generate_id()
        
        project = Project(
            id=project_id,
            goal=goal
        )
        
        self._projects[project_id] = project
        self._save_project(project)
        
        return project
    
    def get(self, project_id: str) -> Optional[Project]:
        """Get project by ID"""
        return self._projects.get(project_id)
    
    def update(self, project: Project):
        """Update project"""
        project.updated = datetime.now()
        self._save_project(project)
    
    def add_artifact(self, project_id: str, artifact: Artifact):
        """Add artifact to project"""
        project = self.get(project_id)
        if project:
            project.artifacts.append(artifact)
            self.update(project)
    
    def reserve_device(self, project_id: str, device_name: str):
        """Reserve device for project"""
        project = self.get(project_id)
        if project:
            project.devices.append(device_name)
            self.update(project)
    
    def _generate_id(self) -> str:
        """Generate unique project ID"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _save_project(self, project: Project):
        """Persist project to disk"""
        project_file = self.storage_path / f"{project.id}.json"
        project_file.write_text(json.dumps(project.to_dict(), indent=2))
    
    def _load_projects(self):
        """Load all projects from disk"""
        for project_file in self.storage_path.glob("*.json"):
            data = json.loads(project_file.read_text())
            
            project = Project(
                id=data["id"],
                goal=data["goal"],
                plan=data["plan"],
                status=ProjectStatus(data["status"]),
                artifacts=[
                    Artifact(
                        name=a["name"],
                        path=Path(a["path"]),
                        type=a["type"]
                    )
                    for a in data["artifacts"]
                ],
                devices=data["devices"],
                created=datetime.fromisoformat(data["created"]),
                updated=datetime.fromisoformat(data["updated"])
            )
            
            self._projects[project.id] = project


# Usage
project_manager = ProjectManager(Path(".ade/projects"))

# Create project
project = project_manager.create("Print a bracket that holds board at 30°")

# Update plan
project.plan = [
    {"step": 1, "subagent": "CAD Designer", "task": "Design bracket model"},
    {"step": 2, "subagent": "Slicer", "task": "Generate G-code"},
    {"step": 3, "subagent": "Printer Control", "task": "Execute print"}
]
project_manager.update(project)

# Add artifact
project_manager.add_artifact(
    project.id,
    Artifact(
        name="bracket.step",
        path=Path("artifacts/bracket.step"),
        type="model"
    )
)

# Reserve device
project_manager.reserve_device(project.id, "3d-printer")
```

---

## Skill Library Implementation

```python
# core/skill_library.py
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import yaml

@dataclass
class SkillMetadata:
    name: str
    domain: str
    description: str
    tools: list[str]
    risk_level: str
    constraints: list[str]

@dataclass
class Skill:
    metadata: SkillMetadata
    instructions: str  # Markdown content
    examples: list[str]

class SkillLibrary:
    def __init__(self, library_path: Path):
        self.library_path = library_path
        self.library_path.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, Skill] = {}
        self._load_skills()
    
    def add(self, skill: Skill):
        """Add skill to library"""
        self._skills[skill.metadata.name] = skill
        self._save_skill(skill)
    
    def get(self, name: str) -> Optional[Skill]:
        """Get skill by name"""
        return self._skills.get(name)
    
    def list(self, domain: Optional[str] = None) -> list[Skill]:
        """List skills, optionally filtered by domain"""
        if domain:
            return [s for s in self._skills.values() if s.metadata.domain == domain]
        return list(self._skills.values())
    
    def _save_skill(self, skill: Skill):
        """Persist skill to disk"""
        skill_dir = self.library_path / skill.metadata.name
        skill_dir.mkdir(exist_ok=True)
        
        # Save metadata
        metadata_file = skill_dir / "metadata.yaml"
        metadata_file.write_text(yaml.dump({
            "name": skill.metadata.name,
            "domain": skill.metadata.domain,
            "description": skill.metadata.description,
            "tools": skill.metadata.tools,
            "risk_level": skill.metadata.risk_level,
            "constraints": skill.metadata.constraints
        }))
        
        # Save instructions
        instructions_file = skill_dir / "instructions.md"
        instructions_file.write_text(skill.instructions)
    
    def _load_skills(self):
        """Load all skills from disk"""
        for skill_dir in self.library_path.iterdir():
            if skill_dir.is_dir():
                metadata_file = skill_dir / "metadata.yaml"
                instructions_file = skill_dir / "instructions.md"
                
                if metadata_file.exists() and instructions_file.exists():
                    metadata = yaml.safe_load(metadata_file.read_text())
                    instructions = instructions_file.read_text()
                    
                    skill = Skill(
                        metadata=SkillMetadata(**metadata),
                        instructions=instructions,
                        examples=[]
                    )
                    
                    self._skills[skill.metadata.name] = skill


# Usage
library = SkillLibrary(Path(".ade/skills"))

# Create skill
skill = Skill(
    metadata=SkillMetadata(
        name="esp32-telemetry",
        domain="sensing",
        description="Read telemetry data from ESP32 sensors",
        tools=["http_client"],
        risk_level="low",
        constraints=[
            "Never send commands, only read",
            "Telemetry is for monitoring only"
        ]
    ),
    instructions="""
# ESP32 Telemetry Skill

## Purpose
Read sensor data from ESP32-based telemetry nodes.

## Workflow
1. Check device health: GET /health
2. Read sensor: GET /temperature, GET /humidity
3. Parse JSON response
4. Report values

## Success Criteria
- All sensors respond
- Values in valid ranges
""",
    examples=[]
)

library.add(skill)

# Retrieve
skill = library.get("esp32-telemetry")
```

---

## Testing Utilities

### Mock Devices

```python
# testing/mock_devices.py
from flask import Flask, jsonify
from typing import Optional
import threading
import time

class MockESP32:
    """Mock ESP32 device for testing"""
    
    def __init__(self, port: int = 5000):
        self.port = port
        self.app = Flask(__name__)
        self.server: Optional[threading.Thread] = None
        
        # Mock sensor values
        self.temperature = 22.5
        self.humidity = 45.0
        
        # Routes
        self.app.route("/health")(self.health)
        self.app.route("/temperature")(self.get_temperature)
        self.app.route("/humidity")(self.get_humidity)
    
    def start(self):
        """Start mock server"""
        self.server = threading.Thread(
            target=self.app.run,
            kwargs={"port": self.port, "threaded": True}
        )
        self.server.daemon = True
        self.server.start()
        time.sleep(1)  # Wait for server to start
    
    def health(self):
        return jsonify({"status": "ok"})
    
    def get_temperature(self):
        return jsonify({"temperature_celsius": self.temperature})
    
    def get_humidity(self):
        return jsonify({"humidity_percent": self.humidity})


# Testing with mock
if __name__ == "__main__":
    # Start mock device
    mock_esp = MockESP32(port=5000)
    mock_esp.start()
    
    # Test device registration
    from core.device_registry import DeviceRegistry, ESP32Telemetry
    
    registry = DeviceRegistry()
    device = ESP32Telemetry(
        name="esp-test",
        endpoint="http://localhost:5000"
    )
    
    registry.register(device)
    
    # Test read
    assert device.health_check() == True
    assert device.status == Status.ONLINE
    
    temp = device.read_temperature()
    print(f"Temperature: {temp}°C")
    
    assert temp == 22.5
    print("✓ Mock device test passed")
```

### Integration Test Runner

```python
# testing/scenario_runner.py
from dataclasses import dataclass
from typing import Optional
import time

@dataclass
class TestResult:
    passed: bool
    duration: float
    error: Optional[str] = None

class ScenarioRunner:
    def __init__(self, agent_runtime, device_registry, project_manager):
        self.runtime = agent_runtime
        self.devices = device_registry
        self.projects = project_manager
    
    def run(
        self,
        request: str,
        mock_devices: Optional[list[str]] = None,
        verify_artifacts: Optional[list[str]] = None,
        timeout: int = 60
    ) -> TestResult:
        """
        Run integration test scenario
        
        Args:
            request: User request to test
            mock_devices: Devices to mock (e.g., ["3d-printer"])
            verify_artifacts: Expected artifacts (e.g., ["bracket.step"])
            timeout: Test timeout in seconds
        """
        
        start_time = time.time()
        
        try:
            # Setup mocks
            if mock_devices:
                self._setup_mocks(mock_devices)
            
            # Run agent
            result = None
            for update in self.runtime.run(request):
                if update["type"] == "complete":
                    result = update["content"]
                    break
                elif update["type"] == "error":
                    raise Exception(update["content"])
            
            # Verify artifacts
            if verify_artifacts:
                # Would check if artifacts were created
                pass
            
            duration = time.time() - start_time
            return TestResult(passed=True, duration=duration)
        
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(passed=False, duration=duration, error=str(e))
        
        finally:
            # Cleanup mocks
            if mock_devices:
                self._teardown_mocks(mock_devices)
    
    def _setup_mocks(self, devices: list[str]):
        # Setup mock devices
        pass
    
    def _teardown_mocks(self, devices: list[str]):
        # Cleanup mock devices
        pass


# Usage
runner = ScenarioRunner(runtime, registry, project_manager)

result = runner.run(
    request="Read temperature from esp-lab",
    verify_artifacts=None,
    timeout=30
)

if result.passed:
    print(f"✓ Test passed in {result.duration:.2f}s")
else:
    print(f"✗ Test failed: {result.error}")
```

---

## Configuration Loading

```python
# config/loader.py
import yaml
from pathlib import Path
from typing import Any

class Config:
    def __init__(self, config_path: Path = Path(".ade/config.yaml")):
        self.config_path = config_path
        self.data = self._load()
    
    def _load(self) -> dict:
        """Load configuration from YAML"""
        if not self.config_path.exists():
            return self._defaults()
        
        with open(self.config_path) as f:
            return yaml.safe_load(f)
    
    def _defaults(self) -> dict:
        """Default configuration"""
        return {
            "agent": {
                "name": "APRIL",
                "model": "mistral-large",
                "context_window": 128000
            },
            "devices": {
                "registry_path": ".ade/devices",
                "auto_discover": True,
                "scan_interval": 30
            },
            "skills": {
                "library_path": ".ade/skills",
                "hot_reload": True
            },
            "safety": {
                "owned_networks": ["192.168.1.0/24"],
                "authorized_networks": [],
                "risk_thresholds": {
                    "low": "auto",
                    "medium": "log",
                    "high": "prompt",
                    "critical": "require_confirm"
                }
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-notation key"""
        keys = key.split(".")
        value = self.data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value


# Usage
config = Config()

model = config.get("agent.model")
scan_interval = config.get("devices.scan_interval", 30)
```

---

## Summary

This implementation guide provides concrete patterns for:

1. **Agent Runtime** - Execution loop with streaming updates
2. **Tool Framework** - Base classes and registry pattern
3. **Device Registry** - Auto-discovery and health monitoring
4. **Safety Engine** - Multi-axis risk policy enforcement
5. **Project Manager** - Durable state and artifact tracking
6. **Skill Library** - Dynamic skill loading and management
7. **Testing Utilities** - Mock devices and integration tests
8. **Configuration** - YAML-based config with defaults

All components follow these principles:
- Minimal dependencies (stdlib-first)
- Type-safe with dataclasses
- Async-ready for monitoring loops
- Persistent state where needed
- Testable with mocks

**Next:** Choose a component and start building!
