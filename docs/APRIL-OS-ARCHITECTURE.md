# APRIL OS Architecture

**A Complete Operating System for the Networked Physical World**

---

## Vision

**APRIL OS** is not just an agent framework - it's an operating system for managing software, devices, and physical infrastructure. Like a traditional OS manages CPU, memory, and disk, APRIL OS manages agents, tools, devices, and physical resources.

```
Traditional OS          →  Manages hardware + software
APRIL OS               →  Manages agents + networked physical world

Kernel                  →  Agent Runtime
Device Drivers          →  MCP Servers
Processes               →  Subagents
Filesystem              →  Projects & Artifacts
Memory                  →  Context & Sessions
Scheduler               →  Task & Workflow Engine
Security                →  Safety Engine
```

---

## OS Architecture Layers

```
┌────────────────────────────────────────────────────────────────┐
│                         USER SPACE                              │
│                                                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │   SHELL      │ │    GUI       │ │    API       │           │
│  │   (CLI)      │ │   Desktop    │ │  (REST/gRPC)│           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                 │
│  ┌───────────────────────────────────────────────────┐         │
│  │            APPLICATION LAYER                       │         │
│  │                                                    │         │
│  │  Projects │ Skills │ Workflows │ Apps            │         │
│  │  (User-level software running on APRIL OS)       │         │
│  └───────────────────────────────────────────────────┘         │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
                              │
                              │ System Calls (API)
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                        KERNEL SPACE                             │
│                                                                 │
│  ┌───────────────────────────────────────────────────┐         │
│  │            APRIL KERNEL                            │         │
│  │                                                    │         │
│  │  ┌─────────────┐  ┌──────────────┐               │         │
│  │  │ PROCESS     │  │ SCHEDULER    │               │         │
│  │  │ MANAGER     │  │              │               │         │
│  │  │             │  │ • Agent sched│               │         │
│  │  │ • Subagent  │  │ • Task queue│               │         │
│  │  │   lifecycle │  │ • Priorities│               │         │
│  │  │ • Context   │  │ • Preemption│               │         │
│  │  │   switch    │  └──────────────┘               │         │
│  │  └─────────────┘                                  │         │
│  │                                                    │         │
│  │  ┌─────────────┐  ┌──────────────┐               │         │
│  │  │ MEMORY      │  │ FILE         │               │         │
│  │  │ MANAGER     │  │ SYSTEM       │               │         │
│  │  │             │  │              │               │         │
│  │  │ • Sessions  │  │ • Projects   │               │         │
│  │  │ • Context   │  │ • Artifacts  │               │         │
│  │  │ • Cache     │  │ • Skills     │               │         │
│  │  └─────────────┘  └──────────────┘               │         │
│  │                                                    │         │
│  │  ┌─────────────┐  ┌──────────────┐               │         │
│  │  │ SECURITY    │  │ IPC          │               │         │
│  │  │ ENGINE      │  │ MANAGER      │               │         │
│  │  │             │  │              │               │         │
│  │  │ • Safety    │  │ • Inter-agent│               │         │
│  │  │ • Auth      │  │ • Workflows  │               │         │
│  │  │ • Audit     │  │ • Events     │               │         │
│  │  └─────────────┘  └──────────────┘               │         │
│  └───────────────────────────────────────────────────┘         │
│                                                                 │
│  ┌───────────────────────────────────────────────────┐         │
│  │            HAL (Hardware Abstraction Layer)        │         │
│  │                                                    │         │
│  │  ┌────────────────────────────────────────────┐   │         │
│  │  │        DEVICE DRIVER LAYER                  │   │         │
│  │  │                                              │   │         │
│  │  │  Manage via MCP Servers:                    │   │         │
│  │  │  • Local: Software apps (CAD, EDA, Vision)  │   │         │
│  │  │  • Network: Physical devices (ESP, Cam, CNC)│   │         │
│  │  └────────────────────────────────────────────┘   │         │
│  └───────────────────────────────────────────────────┘         │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                    PHYSICAL HARDWARE                            │
│                                                                 │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│   │ Machine  │  │ Network  │  │ Devices  │  │ Sensors  │     │
│   │ (Local)  │  │ (WiFi)   │  │ (ESP32)  │  │ (ECG)    │     │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
│                                                                 │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│   │ Camera   │  │ Printer  │  │ Robot    │  │ CNC      │     │
│   │ (Vision) │  │ (3D/CNC) │  │ (Arm)    │  │ (Mill)   │     │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
└────────────────────────────────────────────────────────────────┘
```

---

## Core OS Components

### 1. APRIL Kernel

**The core runtime managing all system resources**

```python
# kernel/april_kernel.py
from typing import Dict, Any
import asyncio
import signal

class AprilKernel:
    """
    APRIL OS Kernel - Core system manager
    
    Responsibilities:
    - Initialize all subsystems
    - Bootstrap the system
    - Handle system-wide events
    - Manage kernel services
    - Provide system call interface
    """
    
    def __init__(self, config_path: str = "/etc/april/config.yaml"):
        self.config = self._load_config(config_path)
        self.running = False
        
        # Core subsystems (like OS kernel components)
        self.process_manager = ProcessManager(self)
        self.memory_manager = MemoryManager(self)
        self.filesystem = FileSystem(self)
        self.security_engine = SecurityEngine(self)
        self.scheduler = Scheduler(self)
        self.ipc_manager = IPCManager(self)
        self.device_manager = DeviceManager(self)
        self.service_manager = ServiceManager(self)
        self.logging = KernelLogger(self)
        
        # HAL (Hardware Abstraction Layer)
        self.hal = HAL(self)
        
        # System state
        self.system_state = SystemState()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
    
    async def boot(self):
        """
        Bootstrap APRIL OS
        
        Sequence:
        1. Load configuration
        2. Initialize hardware abstraction
        3. Mount filesystem (projects, artifacts)
        4. Start kernel services
        5. Launch init system
        6. Start shell/API services
        """
        
        self.logging.info("APRIL OS booting...")
        
        # Phase 1: Hardware Abstraction
        self.logging.info("[1/7] Initializing HAL...")
        await self.hal.initialize()
        
        # Phase 2: Load device drivers (MCP servers)
        self.logging.info("[2/7] Loading device drivers...")
        await self.device_manager.load_drivers()
        
        # Phase 3: Mount filesystem
        self.logging.info("[3/7] Mounting filesystem...")
        await self.filesystem.mount_all()
        
        # Phase 4: Start memory manager
        self.logging.info("[4/7] Initializing memory manager...")
        await self.memory_manager.initialize()
        
        # Phase 5: Start security engine
        self.logging.info("[5/7] Starting security engine...")
        await self.security_engine.start()
        
        # Phase 6: Launch init system (start background services)
        self.logging.info("[6/7] Launching init system...")
        await self.service_manager.start_services()
        
        # Phase 7: Start user-facing services
        self.logging.info("[7/7] Starting shell and API...")
        await self._start_user_services()
        
        self.running = True
        self.logging.info("APRIL OS booted successfully!")
        
        # Main kernel loop
        await self._kernel_loop()
    
    async def _kernel_loop(self):
        """Main kernel event loop"""
        
        while self.running:
            try:
                # Process kernel events
                await self.process_manager.yield_to_kernel()
                
                # Handle IPC messages
                await self.ipc_manager.process_messages()
                
                # Device health checks
                await self.device_manager.health_check()
                
                # Cleanup finished processes
                await self.process_manager.reap_zombies()
                
                # Brief sleep
                await asyncio.sleep(0.1)
            
            except Exception as e:
                self.logging.error(f"Kernel error: {e}")
                await self._handle_kernel_panic(e)
    
    async def shutdown(self):
        """Graceful shutdown"""
        
        self.logging.info("APRIL OS shutting down...")
        
        # Stop accepting new processes
        self.running = False
        
        # Terminate all user processes
        await self.process_manager.terminate_all()
        
        # Stop services
        await self.service_manager.stop_all()
        
        # Unmount filesystem
        await self.filesystem.unmount_all()
        
        # Shutdown HAL
        await self.hal.shutdown()
        
        self.logging.info("APRIL OS shutdown complete")
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        asyncio.create_task(self.shutdown())
    
    # System Call Interface
    async def syscall(self, call: str, *args, **kwargs) -> Any:
        """
        System call interface (like Unix syscalls)
        
        User space → Kernel space transition
        """
        
        # Permission check
        if not await self.security_engine.check_syscall(call):
            raise PermissionError(f"Syscall not permitted: {call}")
        
        # Route to appropriate subsystem
        if call == "spawn_process":
            return await self.process_manager.spawn(*args, **kwargs)
        elif call == "kill_process":
            return await self.process_manager.kill(*args, **kwargs)
        elif call == "read_file":
            return await self.filesystem.read(*args, **kwargs)
        elif call == "write_file":
            return await self.filesystem.write(*args, **kwargs)
        elif call == "call_device":
            return await self.device_manager.call(*args, **kwargs)
        elif call == "alloc_memory":
            return await self.memory_manager.allocate(*args, **kwargs)
        elif call == "ipc_send":
            return await self.ipc_manager.send(*args, **kwargs)
        else:
            raise ValueError(f"Unknown syscall: {call}")
```

---

### 2. Process Manager

**Manages subagents like OS processes**

```python
# kernel/process_manager.py
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio

class ProcessState(Enum):
    CREATED = "created"
    RUNNING = "running"
    SLEEPING = "sleeping"
    STOPPED = "stopped"
    ZOMBIE = "zombie"
    TERMINATED = "terminated"

@dataclass
class ProcessControlBlock:
    """
    Process Control Block (PCB) - Like Unix process table entry
    
    Tracks all information about a process (subagent)
    """
    pid: int
    name: str
    parent_pid: Optional[int]
    state: ProcessState
    priority: int
    skills: list
    tools: list
    context: Dict  # Memory context
    cpu_time: float
    start_time: float
    exit_code: Optional[int] = None
    
class ProcessManager:
    """
    Manage processes (subagents)
    
    Like Unix process manager:
    - fork/exec (spawn processes)
    - kill, wait
    - Scheduling
    - Process isolation
    - Parent-child relationships
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.process_table: Dict[int, ProcessControlBlock] = {}
        self.pid_counter = 1000  # Start PIDs at 1000
        self.current_pid: Optional[int] = None
    
    async def spawn(
        self,
        name: str,
        skills: list,
        tools: list,
        task: str,
        parent_pid: Optional[int] = None,
        priority: int = 0
    ) -> int:
        """
        Spawn new process (like fork + exec)
        
        Returns: PID
        """
        
        # Allocate PID
        pid = self._allocate_pid()
        
        # Allocate memory (context)
        context = await self.kernel.memory_manager.allocate_context(pid)
        
        # Create PCB
        pcb = ProcessControlBlock(
            pid=pid,
            name=name,
            parent_pid=parent_pid,
            state=ProcessState.CREATED,
            priority=priority,
            skills=skills,
            tools=tools,
            context=context,
            cpu_time=0.0,
            start_time=time.time()
        )
        
        self.process_table[pid] = pcb
        
        # Load skills into context
        for skill_name in skills:
            skill = await self.kernel.filesystem.load_skill(skill_name)
            context["skills"].append(skill)
        
        # Schedule process
        await self.kernel.scheduler.schedule(pid, pcb)
        
        # Transition to running
        pcb.state = ProcessState.RUNNING
        
        return pid
    
    async def kill(self, pid: int, signal: str = "TERM"):
        """
        Terminate process (like kill syscall)
        """
        
        if pid not in self.process_table:
            raise ValueError(f"No such process: {pid}")
        
        pcb = self.process_table[pid]
        
        # Send signal
        if signal == "TERM":
            # Graceful termination
            pcb.state = ProcessState.STOPPED
            await self._cleanup_process(pcb)
        elif signal == "KILL":
            # Force termination
            pcb.state = ProcessState.TERMINATED
            await self._cleanup_process(pcb)
        
        # Notify parent
        if pcb.parent_pid:
            await self.kernel.ipc_manager.send(
                pcb.parent_pid,
                {"type": "child_exit", "pid": pid, "signal": signal}
            )
    
    async def wait(self, pid: int, options: dict = None):
        """
        Wait for process to complete (like wait syscall)
        """
        
        if pid not in self.process_table:
            raise ValueError(f"No such process: {pid}")
        
        pcb = self.process_table[pid]
        
        # Block until process completes
        while pcb.state not in [ProcessState.TERMINATED, ProcessState.ZOMBIE]:
            await asyncio.sleep(0.1)
        
        # Collect exit status
        exit_code = pcb.exit_code
        
        # Remove zombie
        if pcb.state == ProcessState.ZOMBIE:
            del self.process_table[pid]
        
        return exit_code
    
    async def reap_zombies(self):
        """Clean up zombie processes (like Unix reaper)"""
        
        zombies = [
            pcb for pcb in self.process_table.values()
            if pcb.state == ProcessState.ZOMBIE
        ]
        
        for zombie in zombies:
            # If parent has already exited, reap
            if zombie.parent_pid not in self.process_table:
                del self.process_table[zombie.pid]
    
    def _allocate_pid(self) -> int:
        """Allocate unique PID"""
        pid = self.pid_counter
        self.pid_counter += 1
        return pid
    
    async def _cleanup_process(self, pcb: ProcessControlBlock):
        """Release process resources"""
        
        # Free memory
        await self.kernel.memory_manager.free_context(pcb.pid)
        
        # Close file descriptors (artifacts)
        await self.kernel.filesystem.close_process_files(pcb.pid)
        
        # Release device locks
        await self.kernel.device_manager.release_process_devices(pcb.pid)
    
    async def list_processes(self) -> list:
        """List all processes (like ps command)"""
        
        return [
            {
                "pid": pcb.pid,
                "name": pcb.name,
                "state": pcb.state.value,
                "priority": pcb.priority,
                "cpu_time": pcb.cpu_time,
                "parent_pid": pcb.parent_pid
            }
            for pcb in self.process_table.values()
        ]
```

---

### 3. Memory Manager

**Manages context and sessions like OS memory**

```python
# kernel/memory_manager.py
from typing import Dict, Optional
import psutil

class MemoryManager:
    """
    Manage memory (context and sessions)
    
    Like OS memory manager:
    - Allocate/deallocate contexts
    - Memory isolation between processes
    - Paging/swapping (context to disk)
    - Memory protection
    - Shared memory (IPC)
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.contexts: Dict[int, Dict] = {}
        self.physical_memory_limit = psutil.virtual_memory().total * 0.7  # 70% of RAM
        self.used_memory = 0
    
    async def allocate_context(self, pid: int) -> Dict:
        """
        Allocate memory context for process
        
        Like OS allocates address space for process
        """
        
        context = {
            "pid": pid,
            "skills": [],
            "knowledge": [],
            "conversation": [],
            "state": {},
            "heap_size": 0,
            "pages": []
        }
        
        self.contexts[pid] = context
        
        return context
    
    async def free_context(self, pid: int):
        """Free process memory"""
        
        if pid in self.contexts:
            del self.contexts[pid]
    
    async def swap_out(self, pid: int):
        """
        Swap context to disk (aged processes)
        
        Like OS swapping
        """
        
        if pid in self.contexts:
            context = self.contexts[pid]
            
            # Serialize to disk
            await self.kernel.filesystem.write(
                f"/var/april/swap/{pid}.ctx",
                json.dumps(context)
            )
            
            # Free memory
            del self.contexts[pid]
    
    async def swap_in(self, pid: int) -> Dict:
        """Swap context back from disk"""
        
        context_data = await self.kernel.filesystem.read(
            f"/var/april/swap/{pid}.ctx"
        )
        
        context = json.loads(context_data)
        self.contexts[pid] = context
        
        return context
    
    def memory_status(self) -> dict:
        """Get memory usage (like free command)"""
        
        return {
            "total": self.physical_memory_limit,
            "used": self.used_memory,
            "free": self.physical_memory_limit - self.used_memory,
            "contexts": len(self.contexts)
        }
```

---

### 4. Filesystem

**Manages projects, artifacts, skills like OS filesystem**

```python
# kernel/filesystem.py
from pathlib import Path
from typing import Dict, Any

class FileSystem:
    """
    APRIL Filesystem
    
    Like Unix filesystem:
    - Hierarchical structure
    - Mount points
    - File permissions
    - Cached access
    
    Structure:
    /april/               (Root)
    ├── projects/         (User projects)
    ├── artifacts/        (Generated files)
    ├── skills/           (Skill library)
    ├── devices/          (Device configs)
    ├── var/              (Variable data)
    │   ├── log/          (System logs)
    │   ├── swap/         (Context swap)
    │   └── tmp/          (Temporary files)
    └── etc/              (Configuration)
        └── april.conf    (Main config)
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.mounts: Dict[str, Path] = {}
        
        # Virtual filesystem structure
        self.vfs = {
            "/projects": Path(".ade/projects"),
            "/artifacts": Path(".ade/artifacts"),
            "/skills": Path(".ade/skills"),
            "/devices": Path(".ade/devices"),
            "/var": Path(".ade/var"),
            "/etc": Path(".ade/etc")
        }
    
    async def mount_all(self):
        """Mount all filesystems"""
        
        for mount_point, path in self.vfs.items():
            path.mkdir(parents=True, exist_ok=True)
            self.mounts[mount_point] = path
        
        # Create standard directories
        (self.mounts["/var"] / "log").mkdir(exist_ok=True)
        (self.mounts["/var"] / "swap").mkdir(exist_ok=True)
        (self.mounts["/var"] / "tmp").mkdir(exist_ok=True)
    
    async def read(self, path: str) -> Any:
        """
        Read from VFS
        
        Like Unix read syscall
        """
        
        # Resolve virtual path to physical
        physical_path = self._resolve_path(path)
        
        if not physical_path.exists():
            raise FileNotFoundError(f"No such file: {path}")
        
        # Check permissions
        if not await self.kernel.security_engine.check_file_access(path, "read"):
            raise PermissionError(f"Read denied: {path}")
        
        return physical_path.read_text()
    
    async def write(self, path: str, data: Any):
        """
        Write to VFS
        
        Like Unix write syscall
        """
        
        # Resolve virtual path
        physical_path = self._resolve_path(path)
        
        # Check permissions
        if not await self.kernel.security_engine.check_file_access(path, "write"):
            raise PermissionError(f"Write denied: {path}")
        
        # Create parent directories
        physical_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write
        if isinstance(data, str):
            physical_path.write_text(data)
        else:
            physical_path.write_bytes(data)
    
    async def load_project(self, project_id: str) -> Dict:
        """Load project from /projects"""
        
        project_path = f"/projects/{project_id}.json"
        return json.loads(await self.read(project_path))
    
    async def save_project(self, project_id: str, project: Dict):
        """Save project to /projects"""
        
        project_path = f"/projects/{project_id}.json"
        await self.write(project_path, json.dumps(project, indent=2))
    
    async def load_skill(self, skill_name: str) -> Dict:
        """Load skill from /skills"""
        
        skill_dir = f"/skills/{skill_name}"
        
        # Load SKILL.md
        skill_file = f"{skill_dir}/SKILL.md"
        content = await self.read(skill_file)
        
        # Parse
        return parse_skill_markdown(content)
    
    def _resolve_path(self, virtual_path: str) -> Path:
        """Resolve virtual path to physical path"""
        
        # Find mount point
        for mount, physical in self.mounts.items():
            if virtual_path.startswith(mount):
                relative = virtual_path[len(mount):].lstrip("/")
                return physical / relative
        
        raise ValueError(f"Unknown mount point: {virtual_path}")
    
    async def unmount_all(self):
        """Unmount all filesystems"""
        
        # Flush caches
        self.mounts.clear()
```

---

### 5. Device Manager (HAL)

**Hardware Abstraction Layer - Manages MCP servers as device drivers**

```python
# kernel/hal.py
from typing import Dict
import asyncio

class HAL:
    """
    Hardware Abstraction Layer
    
    Like OS HAL:
    - Abstract hardware differences
    - Device driver interface
    - Hardware initialization
    - Device discovery
    - Interrupt handling
    
    In APRIL OS:
    - MCP servers ARE device drivers
    - Hardware = Software apps + Network devices
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.drivers: Dict[str, 'Driver'] = {}
    
    async def initialize(self):
        """
        Initialize hardware abstraction layer
        
        Phase 1: Detect machine hardware (local)
        Phase 2: Scan network devices
        Phase 3: Load drivers (MCP servers)
        """
        
        # Probe local machine
        await self._probe_machine()
        
        # Scan network
        await self._scan_network()
        
        # Load drivers
        await self._load_drivers()
    
    async def _probe_machine(self):
        """Probe local machine capabilities"""
        
        # CPU, memory, storage
        import platform
        import psutil
        
        self.kernel.system_state["machine"] = {
            "hostname": platform.node(),
            "os": platform.system(),
            "cpu_count": psutil.cpu_count(),
            "memory_gb": psutil.virtual_memory().total / (1024**3)
        }
    
    async def _scan_network(self):
        """Discover network devices"""
        
        # Scan for devices (ESP32, cameras, etc.)
        # Could use network discovery, mDNS, etc.
        
        self.kernel.system_state["network"] = {
            "devices": []
        }
    
    async def _load_drivers(self):
        """
        Load device drivers (MCP servers)
        
        Like OS loading kernel modules
        """
        
        driver_configs = self.kernel.config.get("drivers", [])
        
        for driver_config in driver_configs:
            driver = Driver(
                name=driver_config["name"],
                command=driver_config["command"],
                args=driver_config.get("args", []),
                kernel=self.kernel
            )
            
            await driver.load()
            
            self.drivers[driver.name] = driver

class Driver:
    """
    Device driver (MCP server wrapper)
    
    Like OS device driver:
    - Initialize device
    - Provide I/O interface
    - Handle interrupts (events)
    - Clean up on shutdown
    """
    
    def __init__(self, name: str, command: str, args: list, kernel):
        self.name = name
        self.command = command
        self.args = args
        self.kernel = kernel
        self.process: Optional[subprocess.Popen] = None
        self.tools: List[dict] = []
    
    async def load(self):
        """Load driver (start MCP server)"""
        
        self.process = subprocess.Popen(
            [self.command] + self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Initialize MCP connection
        await self._initialize_mcp()
        
        # Discover tools
        self.tools = await self._discover_tools()
    
    async def call(self, tool_name: str, args: dict) -> Any:
        """
        Call device function
        
        Like Unix ioctl syscall
        """
        
        # Send MCP request
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": args
            }
        }
        
        response = await self._send_mcp(request)
        
        return response.get("result")
    
    async def unload(self):
        """Unload driver (stop MCP server)"""
        
        if self.process:
            self.process.terminate()
            self.process.wait()
```

---

### 6. Scheduler

**Schedules processes like OS scheduler**

```python
# kernel/scheduler.py
from typing import Dict, List
import asyncio

class Scheduler:
    """
    Process scheduler (like OS scheduler)
    
    Features:
    - Priority scheduling
    - Preemptive multitasking
    - Round robin
    - Real-time processes
    - CPU time accounting
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.ready_queue: List[int] = []  # PIDs
        self.current_pid: Optional[int] = None
        self.time_slice = 0.1  # 100ms quantum
    
    async def schedule(self, pid: int, pcb: 'ProcessControlBlock'):
        """
        Add process to ready queue
        
        Like OS scheduler adding process
        """
        
        # Insert by priority
        self.ready_queue.append(pid)
        self._sort_by_priority()
    
    async def run(self):
        """
        Main scheduler loop
        
        Like OS scheduler: pick next process, run for time slice
        """
        
        while self.kernel.running:
            if self.ready_queue:
                # Pick next process
                pid = self.ready_queue.pop(0)
                self.current_pid = pid
                
                # Run for time slice
                await self._run_process(pid)
            
            await asyncio.sleep(self.time_slice)
    
    async def _run_process(self, pid: int):
        """
        Execute process for time slice
        
        Like OS context switch to process
        """
        
        pcb = self.kernel.process_manager.process_table[pid]
        
        if pcb.state != ProcessState.RUNNING:
            return
        
        # Check if process needs to be swapped in
        if pid not in self.kernel.memory_manager.contexts:
            await self.kernel.memory_manager.swap_in(pid)
        
        # Execute one iteration
        try:
            result = await pcb.context["agent"].step()
            
            # Update CPU time
            pcb.cpu_time += self.time_slice
            
            # Re-queue if not done
            if not result.get("done"):
                self.ready_queue.append(pid)
            
        except Exception as e:
            # Handle process error
            pcb.state = ProcessState.STOPPED
            await self.kernel.process_manager.kill(pid, "KILL")
    
    def _sort_by_priority(self):
        """Sort by priority (higher first)"""
        
        self.ready_queue.sort(
            key=lambda pid: self.kernel.process_manager.process_table[pid].priority,
            reverse=True
        )
```

---

### 7. Security Engine

**Enforces safety like OS security**

```python
# kernel/security_engine.py
from enum import Enum
from typing import Optional

class SecurityEngine:
    """
    Security engine (like OS security)
    
    Three axes (from APRIL design):
    1. Physical risk (per-device)
    2. Network authorization
    3. Data sensitivity
    
    Like OS security:
    - Permission checks
    - Audit logging
    - Capability-based security
    - Mandatory access control (MAC)
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.audit_log: List[dict] = []
        self.capabilities: Dict[str, set] = {}
    
    async def check_syscall(self, syscall: str) -> bool:
        """
        Check if syscall is permitted (like Linux capabilities)
        """
        
        # Kernel can always do anything
        # User processes need capabilities
        
        return True  # Simplified
    
    async def check_file_access(self, path: str, mode: str) -> bool:
        """
        Check file access (like Unix permissions)
        """
        
        # Check read/write/execute permissions
        return True  # Simplified
    
    async def check_device_action(
        self,
        device_name: str,
        action: str,
        process_context: dict
    ) -> tuple[bool, str]:
        """
        Check device action permission
        
        Returns: (allowed, reason)
        """
        
        # Get device
        device = await self.kernel.device_manager.get_device(device_name)
        
        if not device:
            return False, f"Device not found: {device_name}"
        
        # Check risk level
        risk_level = device.get("risk_level", "low")
        
        if risk_level in ["high", "critical"]:
            # Require approval
            approved = await self._request_approval(device, action)
            
            if not approved:
                return False, "User denied"
        
        # Audit log
        self.audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "device": device_name,
            "action": action,
            "pid": process_context.get("pid"),
            "result": "allowed"
        })
        
        return True, "Approved"
    
    async def _request_approval(self, device: dict, action: str) -> bool:
        """Request user approval for high-risk action"""
        
        # Show prompt (like UAC on Windows)
        print(f"\n[SECURITY] High-risk device action:")
        print(f"  Device: {device['name']}")
        print(f"  Risk: {device['risk_level']}")
        print(f"  Action: {action}")
        print(f"  Approve? [y/N]: ", end="")
        
        response = input()
        return response.lower() in ["y", "yes"]
```

---

### 8. IPC Manager

**Inter-process communication**

```python
# kernel/ipc_manager.py
from typing import Dict, List
import asyncio

class IPCManager:
    """
    Inter-process communication (like Unix IPC)
    
    Features:
    - Message passing (like queues)
    - Shared memory
    - Signals
    - Pipes
    - Events
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.message_queues: Dict[int, asyncio.Queue] = {}
    
    async def send(self, pid: int, message: dict):
        """
        Send message to process (like Unix signals)
        """
        
        if pid not in self.message_queues:
            self.message_queues[pid] = asyncio.Queue()
        
        await self.message_queues[pid].put(message)
    
    async def receive(self, pid: int) -> dict:
        """
        Receive message for process (like Unix signal handling)
        """
        
        if pid not in self.message_queues:
            return None
        
        return await self.message_queues[pid].get()
    
    async def broadcast(self, message: dict):
        """
        Broadcast to all processes
        """
        
        for pid in self.message_queues:
            await self.send(pid, message)
```

---

### 9. Service Manager (Init System)

**Background services like Unix init**

```python
# kernel/service_manager.py
from typing import Dict

class ServiceManager:
    """
    Service manager (like systemd/init)
    
    Features:
    - Start/stop services
    - Service dependencies
    - Auto-restart
    - Service monitoring
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.services: Dict[str, 'Service'] = {}
    
    async def start_services(self):
        """
        Start system services (like init)
        
        Services:
        - health-monitor: Device health checks
        - scheduler: Scheduled tasks
        - audit-logger: Security audit logging
        - network-scanner: Device discovery
        """
        
        # Define services
        services_config = [
            {
                "name": "health-monitor",
                "command": self._health_monitor_loop,
                "auto_restart": True
            },
            {
                "name": "scheduler",
                "command": self.kernel.scheduler.run,
                "auto_restart": True
            },
            {
                "name": "audit-logger",
                "command": self._audit_log_loop,
                "auto_restart": True
            }
        ]
        
        for config in services_config:
            service = Service(**config)
            self.services[service.name] = service
            await service.start()
    
    async def stop_all(self):
        """Stop all services"""
        
        for service in self.services.values():
            await service.stop()

class Service:
    """System service (daemon)"""
    
    def __init__(self, name: str, command: Callable, auto_restart: bool = True):
        self.name = name
        self.command = command
        self.auto_restart = auto_restart
        self.task: Optional[asyncio.Task] = None
        self.running = False
    
    async def start(self):
        """Start service"""
        
        self.running = True
        self.task = asyncio.create_task(self._run())
    
    async def _run(self):
        """Run service"""
        
        while self.running:
            try:
                await self.command()
            except Exception as e:
                log.error(f"Service {self.name} error: {e}")
                
                if self.auto_restart:
                    await asyncio.sleep(5)
                else:
                    break
    
    async def stop(self):
        """Stop service"""
        
        self.running = False
        if self.task:
            self.task.cancel()
```

---

## User Space: Shell

```python
# user/shell.py
class AprilShell:
    """
    APRIL Shell - User interface
    
    Like Unix shell (bash/zsh):
    - Command line interface
    - Scripting
    - Process control
    - Filesystem navigation
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.current_project = None
        self.env = {}
    
    async def run(self):
        """Main shell loop"""
        
        while True:
            # Prompt
            cwd = self.kernel.filesystem.current_dir
            prompt = f"aprilsade:{cwd}$ "
            
            # Read command
            try:
                user_input = input(prompt)
            except EOFError:
                break
            
            # Parse command
            cmd, args = self._parse(user_input)
            
            # Execute
            await self._execute(cmd, args)
    
    async def _execute(self, cmd: str, args: list):
        """Execute shell command"""
        
        # Built-in commands
        if cmd == "cd":
            self.kernel.filesystem.chdir(args[0])
        
        elif cmd == "ls":
            files = await self.kernel.filesystem.list_dir(args[0] if args else ".")
            for f in files:
                print(f)
        
        elif cmd == "ps":
            processes = await self.kernel.process_manager.list_processes()
            print(f"{'PID':<8} {'NAME':<20} {'STATE':<10} {'CPU':<8}")
            for p in processes:
                print(f"{p['pid']:<8} {p['name']:<20} {p['state']:<10} {p['cpu_time']:<8.2f}")
        
        elif cmd == "kill":
            pid = int(args[0])
            await self.kernel.process_manager.kill(pid)
        
        elif cmd == "devices":
            devices = await self.kernel.device_manager.list_devices()
            print(f"{'NAME':<20} {'STATUS':<10} {'RISK':<10}")
            for d in devices:
                print(f"{d['name']:<20} {d['status']:<10} {d['risk_level']:<10}")
        
        elif cmd == "projects":
            projects = await self.kernel.filesystem.list_projects()
            for p in projects:
                print(p)
        
        elif cmd == "run":
            # Run skill or workflow
            await self.kernel.syscall("spawn_process", name=args[0])
        
        elif cmd == "exit":
            await self.kernel.shutdown()
        
        else:
            print(f"aprilsh: {cmd}: command not found")
    
    def _parse(self, input: str) -> tuple[str, list]:
        """Parse command line"""
        
        parts = input.strip().split()
        if not parts:
            return "", []
        
        return parts[0], parts[1:]
```

---

## Complete System Boot Sequence

```bash
$ aprils-ade boot

APRIL OS v1.0.0 booting...

[1/7] Initializing HAL...
  - Probing machine: MacBook Pro M1
  - Scanning network: 5 devices found
  - Loading drivers: 8 MCP servers loaded

[2/7] Mounting filesystem...
  - /projects mounted
  - /artifacts mounted
  - /skills mounted
  - /devices mounted
  - /var mounted

[3/7] Initializing memory manager...
  - Available memory: 12.4 GB
  - Context cache: 512 MB

[4/7] Starting security engine...
  - Safety policy loaded
  - Risk thresholds: low=auto, medium=log, high=prompt, critical=require_confirm

[5/7] Loading device drivers...
  - mcp-freecad: loaded
  - mcp-slicer-prusa: loaded
  - mcp-vision-llava: loaded
  - mcp-esp32-bridge: loaded (2 devices)
  - mcp-camera-bridge: loaded (1 device)
  - mcp-octoprint-bridge: loaded
  - mcp-cnc-bridge: loaded

[6/7] Starting services...
  - health-monitor: started
  - scheduler: started
  - audit-logger: started

[7/7] Starting user services...
  - shell: ready
  - api server: listening on http://localhost:8000

APRIL OS booted successfully!

aprilsade:/$ ls
drwxr-xr-x  projects/
drwxr-xr-x  artifacts/
drwxr-xr-x  skills/
drwxr-xr-x  devices/
drwxr-xr-x  var/
drwxr-xr-x  etc/

aprilsade:/$ devices
NAME                 STATUS     RISK
esp-lab              online     low
esp-workshop         online     low
camera-gate          online     medium
printer-3d           online     high
cnc-main             offline    critical

aprilsade:/$ ps
PID      NAME                 STATE      CPU
1001     april-agent          running    12.34
1002     vision-subagent      sleeping   2.45
1003     health-monitor       running    0.12

aprilsade:/$ run print-bracket
[APRIL] Spawning workflow: print-bracket
[APRIL] Step 1/3: Design (subagent spawned, PID 1004)
[APRIL] Step 2/3: Slice (waiting on step 1)
[APRIL] Step 3/3: Print (waiting on step 2)

aprilsade:/$
```

---

## Summary

**APRIL OS** provides a complete operating system-like environment:

### Kernel Components:
1. **Process Manager** - Subagent lifecycle
2. **Memory Manager** - Context and sessions
3. **Filesystem** - Projects, artifacts, skills
4. **Scheduler** - Process scheduling
5. **Security Engine** - 3-axis safety
6. **IPC Manager** - Inter-agent communication
7. **Service Manager** - Background services
8. **HAL** - Device abstraction (MCP servers)

### User Space:
- **Shell** - CLI interface
- **Applications** - Projects, workflows
- **Tools** - User skills

### Benefits:
- ✅ Complete isolation between processes
- ✅ Resource management
- ✅ Security enforcement
- ✅ Standard interfaces
- ✅ Familiar OS concepts
- ✅ Multi-user (future)
- ✅ Fault tolerance

**APRIL as an OS is the ultimate realization: managing the physical world like an operating system!**
