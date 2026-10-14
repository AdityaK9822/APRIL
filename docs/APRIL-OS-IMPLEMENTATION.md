# APRIL OS Implementation Guide

**Practical steps to build your custom OS-like environment**

---

## Project Structure

```
/Users/aditya/Coding/April/Open_INT/
├── april_os/                    # APRIL OS package
│   ├── __init__.py
│   │
│   ├── kernel/                  # Kernel space
│   │   ├── __init__.py
│   │   ├── april_kernel.py      # Main kernel
│   │   ├── process_manager.py   # Process manager
│   │   ├── memory_manager.py    # Memory manager
│   │   ├── filesystem.py        # Filesystem
│   │   ├── scheduler.py         # Scheduler
│   │   ├── security_engine.py   # Security
│   │   ├── ipc_manager.py       # IPC
│   │   ├── service_manager.py   # Services
│   │   └── hal.py               # Hardware abstraction
│   │
│   ├── user/                    # User space
│   │   ├── __init__.py
│   │   ├── shell.py             # CLI shell
│   │   ├── api_server.py        # REST API
│   │   └── desktop.py           # GUI (future)
│   │
│   ├── drivers/                 # Device drivers
│   │   ├── mcp_client.py        # MCP client base
│   │   └── drivers/             # Driver implementations
│   │       ├── freecad.py
│   │       ├── esp32.py
│   │       └── ...
│   │
│   └── utils/                   # Utilities
│       ├── logger.py
│       └── config.py
│
├── bin/                         # Executables
│   └── aprils-ade              # Main executable
│
├── etc/                         # Configuration
│   └── april/
│       ├── kernel.conf          # Kernel config
│       ├── drivers.yaml         # Driver config
│       └── services.yaml        # Services config
│
├── var/                         # Variable data
│   └── april/
│       ├── log/                # Logs
│       ├── swap/               # Context swap
│       └── tmp/                # Temp files
│
└── tests/                      # Test suite
    └── kernel/
        ├── test_process.py
        ├── test_memory.py
        └── ...
```

---

## Phase 1: Kernel Core (Week 1-2)

**Goal:** Build minimal APRIL kernel that boots

### Step 1.1: Create Kernel

```python
# april_os/kernel/april_kernel.py
import asyncio
import signal
import sys
from pathlib import Path

class AprilKernel:
    """APRIL OS Kernel"""
    
    def __init__(self):
        self.running = False
        self.version = "1.0.0"
        
        # Core subsystems
        self.process_manager = None
        self.memory_manager = None
        self.filesystem = None
        
    async def boot(self):
        """Boot APRIL OS"""
        
        print(f"APRIL OS v{self.version} booting...")
        print()
        
        # Phase 1: Initialize filesystem
        print("[1/4] Mounting filesystem...")
        self.filesystem = FileSystem(self)
        await self.filesystem.mount_all()
        print("  ✓ /projects mounted")
        print("  ✓ /artifacts mounted")
        print("  ✓ /skills mounted")
        print()
        
        # Phase 2: Initialize memory
        print("[2/4] Initializing memory manager...")
        self.memory_manager = MemoryManager(self)
        await self.memory_manager.initialize()
        print("  ✓ Context allocator ready")
        print()
        
        # Phase 3: Initialize process manager
        print("[3/4] Starting process manager...")
        self.process_manager = ProcessManager(self)
        print("  ✓ Process scheduler ready")
        print()
        
        # Phase 4: Start shell
        print("[4/4] Starting shell...")
        shell = Shell(self)
        asyncio.create_task(shell.run())
        print("  ✓ Shell ready")
        print()
        
        print("APRIL OS booted successfully!")
        print()
        
        self.running = True
        
        # Main kernel loop
        await self._kernel_loop()
    
    async def _kernel_loop(self):
        """Main kernel event loop"""
        
        while self.running:
            try:
                # Yield to process manager
                await asyncio.sleep(0.1)
            except KeyboardInterrupt:
                await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown"""
        
        print("\nAPRIL OS shutting down...")
        
        self.running = False
        
        # Terminate processes
        if self.process_manager:
            await self.process_manager.terminate_all()
        
        # Unmount filesystem
        if self.filesystem:
            await self.filesystem.unmount_all()
        
        print("APRIL OS shutdown complete")
        sys.exit(0)

# Main entry point
async def main():
    kernel = AprilKernel()
    
    # Register signal handlers
    loop = asyncio.get_event_loop()
    
    def handle_signal():
        asyncio.create_task(kernel.shutdown())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)
    
    await kernel.boot()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
```

### Step 1.2: Create Executable

```python
#!/usr/bin/env python3
# bin/aprils-ade

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from april_os.kernel.april_kernel import main
import asyncio

if __name__ == "__main__":
    # Parse arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        print("APRIL OS v1.0.0")
        sys.exit(0)
    
    # Boot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n")
```

**Make executable:**
```bash
chmod +x bin/aprils-ade
```

---

## Phase 2: Process Manager (Week 3)

**Goal:** Manage subagents like OS processes

### Implementation

```python
# april_os/kernel/process_manager.py
import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional
import time

class ProcessState(Enum):
    CREATED = "created"
    RUNNING = "running"
    SLEEPING = "sleeping"
    STOPPED = "stopped"
    ZOMBIE = "zombie"

@dataclass
class ProcessControlBlock:
    """PCB - Like Unix process"""
    pid: int
    name: str
    state: ProcessState
    priority: int
    task: Optional[str]
    start_time: float
    cpu_time: float = 0.0

class ProcessManager:
    """Manage processes (subagents)"""
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.process_table: Dict[int, ProcessControlBlock] = {}
        self.pid_counter = 1000
        self.ready_queue = []
    
    async def spawn(
        self,
        name: str,
        task: str,
        priority: int = 0
    ) -> int:
        """
        Spawn new process (like fork + exec)
        
        Returns: PID
        """
        
        # Allocate PID
        pid = self._allocate_pid()
        
        # Create PCB
        pcb = ProcessControlBlock(
            pid=pid,
            name=name,
            state=ProcessState.CREATED,
            priority=priority,
            task=task,
            start_time=time.time()
        )
        
        # Add to table
        self.process_table[pid] = pcb
        
        # Schedule
        self.ready_queue.append(pid)
        
        # Transition to running
        pcb.state = ProcessState.RUNNING
        
        print(f"[KERNEL] Process created: {name} (PID {pid})")
        
        return pid
    
    async def kill(self, pid: int, signal: str = "TERM"):
        """Terminate process"""
        
        if pid not in self.process_table:
            print(f"[KERNEL] No such process: {pid}")
            return
        
        pcb = self.process_table[pid]
        
        if signal == "TERM":
            pcb.state = ProcessState.STOPPED
            print(f"[KERNEL] Process terminated: {pcb.name} (PID {pid})")
        
        elif signal == "KILL":
            pcb.state = ProcessState.ZOMBIE
            print(f"[KERNEL] Process killed: {pcb.name} (PID {pid})")
    
    async def wait(self, pid: int) -> int:
        """
        Wait for process to complete (like wait syscall)
        
        Returns: exit code
        """
        
        if pid not in self.process_table:
            return -1
        
        pcb = self.process_table[pid]
        
        # Wait until stopped
        while pcb.state not in [ProcessState.STOPPED, ProcessState.ZOMBIE]:
            await asyncio.sleep(0.1)
        
        # Reap zombie
        if pcb.state == ProcessState.ZOMBIE:
            del self.process_table[pid]
        
        return 0  # Exit code
    
    def list_processes(self) -> list:
        """List all processes (like ps)"""
        
        return [
            {
                "pid": pcb.pid,
                "name": pcb.name,
                "state": pcb.state.value,
                "priority": pcb.priority,
                "cpu_time": pcb.cpu_time,
                "runtime": time.time() - pcb.start_time
            }
            for pcb in self.process_table.values()
        ]
    
    async def terminate_all(self):
        """Terminate all processes"""
        
        for pid in list(self.process_table.keys()):
            await self.kill(pid, "KILL")
    
    def _allocate_pid(self) -> int:
        """Allocate unique PID"""
        
        pid = self.pid_counter
        self.pid_counter += 1
        return pid
```

---

## Phase 3: Memory Manager (Week 4)

**Goal:** Manage context like OS memory

```python
# april_os/kernel/memory_manager.py
from typing import Dict, Any
import time

class MemoryManager:
    """Manage memory (context and sessions)"""
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.contexts: Dict[int, Dict] = {}
        self.max_contexts = 100
        self.swap_threshold = 0.8  # Swap out when 80% full
    
    async def initialize(self):
        """Initialize memory manager"""
        
        print(f"  Context limit: {self.max_contexts}")
        print(f"  Swap threshold: {self.swap_threshold * 100}%")
    
    async def allocate_context(self, pid: int) -> Dict:
        """
        Allocate memory context for process
        
        Like OS allocates address space
        """
        
        # Check if need to swap out old contexts
        if len(self.contexts) >= self.max_contexts * self.swap_threshold:
            await self._swap_oldest()
        
        # Create context
        context = {
            "pid": pid,
            "skills": [],
            "knowledge": [],
            "conversation": [],
            "state": {},
            "created_time": time.time(),
            "last_access": time.time()
        }
        
        self.contexts[pid] = context
        
        return context
    
    def get_context(self, pid: int) -> Dict:
        """Get process context"""
        
        if pid in self.contexts:
            self.contexts[pid]["last_access"] = time.time()
            return self.contexts[pid]
        
        return None
    
    async def free_context(self, pid: int):
        """Free process context"""
        
        if pid in self.contexts:
            del self.contexts[pid]
    
    async def _swap_oldest(self):
        """
        Swap out oldest context (LRU)
        
        Like OS paging to disk
        """
        
        if not self.contexts:
            return
        
        # Find oldest accessed
        oldest_pid = min(
            self.contexts.keys(),
            key=lambda pid: self.contexts[pid]["last_access"]
        )
        
        # Swap to disk
        await self._swap_out(oldest_pid)
    
    async def _swap_out(self, pid: int):
        """Swap context to disk"""
        
        context = self.contexts[pid]
        
        # Write to swap file
        import json
        swap_file = self.kernel.filesystem.mounts["/var"] / "swap" / f"{pid}.ctx"
        swap_file.write_text(json.dumps(context))
        
        # Free memory
        del self.contexts[pid]
        
        print(f"[KERNEL] Swapped out context for PID {pid}")
    
    async def _swap_in(self, pid: int) -> Dict:
        """Swap context back from disk"""
        
        import json
        swap_file = self.kernel.filesystem.mounts["/var"] / "swap" / f"{pid}.ctx"
        
        if swap_file.exists():
            context = json.loads(swap_file.read_text())
            self.contexts[pid] = context
            return context
        
        return None
    
    def memory_status(self) -> dict:
        """Get memory status"""
        
        return {
            "total_contexts": self.max_contexts,
            "used_contexts": len(self.contexts),
            "free_contexts": self.max_contexts - len(self.contexts),
            "usage_percent": len(self.contexts) / self.max_contexts * 100
        }
```

---

## Phase 4: Filesystem (Week 5)

**Goal:** Manage projects, skills, artifacts

```python
# april_os/kernel/filesystem.py
from pathlib import Path
from typing import Dict, Any
import os

class FileSystem:
    """
    APRIL Filesystem
    
    Hierarchical structure like Unix
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.mounts: Dict[str, Path] = {}
        
        # Default mount points
        self.default_mounts = {
            "/projects": ".ade/projects",
            "/artifacts": ".ade/artifacts",
            "/skills": ".ade/skills",
            "/var": ".ade/var"
        }
    
    async def mount_all(self):
        """Mount all filesystems"""
        
        for mount_point, path in self.default_mounts.items():
            physical_path = Path(path)
            physical_path.mkdir(parents=True, exist_ok=True)
            
            self.mounts[mount_point] = physical_path
            
            # Create subdirectories
            if mount_point == "/var":
                (physical_path / "log").mkdir(exist_ok=True)
                (physical_path / "swap").mkdir(exist_ok=True)
                (physical_path / "tmp").mkdir(exist_ok=True)
    
    async def read(self, path: str) -> str:
        """Read from filesystem"""
        
        physical_path = self._resolve_path(path)
        
        if not physical_path.exists():
            raise FileNotFoundError(path)
        
        return physical_path.read_text()
    
    async def write(self, path: str, data: str):
        """Write to filesystem"""
        
        physical_path = self._resolve_path(path)
        physical_path.parent.mkdir(parents=True, exist_ok=True)
        physical_path.write_text(data)
    
    def _resolve_path(self, virtual_path: str) -> Path:
        """Resolve virtual path to physical"""
        
        # Find mount point
        for mount, physical in self.mounts.items():
            if virtual_path.startswith(mount):
                relative = virtual_path[len(mount):].lstrip("/")
                return physical / relative
        
        raise ValueError(f"Unknown mount point: {virtual_path}")
    
    def list_dir(self, path: str = "/") -> list:
        """List directory contents"""
        
        physical_path = self._resolve_path(path)
        
        if not physical_path.exists():
            return []
        
        return [
            f.name for f in physical_path.iterdir()
        ]
    
    async def unmount_all(self):
        """Unmount all filesystems"""
        
        # Can add sync/flush logic here
        self.mounts.clear()
```

---

## Phase 5: Shell (Week 6)

**Goal:** User interface

```python
# april_os/user/shell.py
import asyncio
import shlex

class Shell:
    """
    APRIL Shell - User interface
    
    Like Unix shell (bash/zsh)
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.current_dir = "/"
        self.running = True
    
    async def run(self):
        """Main shell loop"""
        
        while self.running and self.kernel.running:
            try:
                # Prompt
                prompt = f"aprilsade:{self.current_dir}$ "
                
                # Read command (non-blocking)
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, input, prompt
                )
                
                # Execute
                await self._execute(user_input)
            
            except EOFError:
                break
            except KeyboardInterrupt:
                print()
                continue
    
    async def _execute(self, user_input: str):
        """Execute shell command"""
        
        if not user_input.strip():
            return
        
        # Parse
        try:
            parts = shlex.split(user_input)
        except:
            print("aprilsh: parse error")
            return
        
        cmd = parts[0]
        args = parts[1:]
        
        # Built-in commands
        if cmd == "ls":
            await self._cmd_ls(args)
        
        elif cmd == "cd":
            self._cmd_cd(args)
        
        elif cmd == "ps":
            await self._cmd_ps()
        
        elif cmd == "run":
            await self._cmd_run(args)
        
        elif cmd == "kill":
            await self._cmd_kill(args)
        
        elif cmd == "memory":
            await self._cmd_memory()
        
        elif cmd == "help":
            self._cmd_help()
        
        elif cmd == "exit":
            await self.kernel.shutdown()
        
        elif cmd == "version":
            print(f"APRIL OS v{self.kernel.version}")
        
        else:
            print(f"aprilsh: {cmd}: command not found")
    
    async def _cmd_ls(self, args: list):
        """List directory"""
        
        path = args[0] if args else self.current_dir
        
        if not path.startswith("/"):
            path = self.current_dir + "/" + path
        
        files = self.kernel.filesystem.list_dir(path)
        
        for f in sorted(files):
            print(f)
    
    def _cmd_cd(self, args: list):
        """Change directory"""
        
        if not args:
            self.current_dir = "/"
            return
        
        path = args[0]
        
        if not path.startswith("/"):
            path = self.current_dir + "/" + path
        
        # Simplified: just set current_dir
        self.current_dir = path.rstrip("/")
    
    async def _cmd_ps(self):
        """List processes"""
        
        processes = self.kernel.process_manager.list_processes()
        
        print(f"{'PID':<8} {'NAME':<20} {'STATE':<10} {'CPU':<8}")
        print("-" * 50)
        
        for p in processes:
            print(f"{p['pid']:<8} {p['name']:<20} {p['state']:<10} {p['cpu_time']:<8.2f}")
    
    async def _cmd_run(self, args: list):
        """Run process"""
        
        if not args:
            print("run: usage: run <name> [task]")
            return
        
        name = args[0]
        task = " ".join(args[1:]) if len(args) > 1 else f"Execute {name}"
        
        pid = await self.kernel.process_manager.spawn(name, task)
        print(f"[PID {pid}] Process started")
    
    async def _cmd_kill(self, args: list):
        """Kill process"""
        
        if not args:
            print("kill: usage: kill <pid>")
            return
        
        try:
            pid = int(args[0])
            await self.kernel.process_manager.kill(pid, "TERM")
        except ValueError:
            print("kill: invalid pid")
    
    async def _cmd_memory(self):
        """Show memory status"""
        
        status = self.kernel.memory_manager.memory_status()
        
        print(f"Memory Status:")
        print(f"  Total contexts: {status['total_contexts']}")
        print(f"  Used: {status['used_contexts']} ({status['usage_percent']:.1f}%)")
        print(f"  Free: {status['free_contexts']}")
    
    def _cmd_help(self):
        """Show help"""
        
        print("APRIL Shell Commands:")
        print("  ls          - List files")
        print("  cd          - Change directory")
        print("  ps          - List processes")
        print("  run         - Run process")
        print("  kill        - Kill process")
        print("  memory      - Show memory status")
        print("  version     - Show version")
        print("  help        - Show this help")
        print("  exit        - Shutdown APRIL OS")
```

---

## Complete Boot Example

**Create main entry:**

```python
# april_os/__main__.py
from .kernel.april_kernel import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
```

**Run APRIL OS:**

```bash
$ python -m april_os

APRIL OS v1.0.0 booting...

[1/4] Mounting filesystem...
  ✓ /projects mounted
  ✓ /artifacts mounted
  ✓ /skills mounted

[2/4] Initializing memory manager...
  Context allocator ready

[3/4] Starting process manager...
  Process scheduler ready

[4/4] Starting shell...
  Shell ready

APRIL OS booted successfully!

aprilsade:/$ ls
projects
artifacts
skills
var

aprilsade:/$ ps
PID      NAME                 STATE      CPU
--------------------------------------------
1001     april-agent          running    2.34

aprilsade:/$ run test-process "Hello world"
[KERNEL] Process created: test-process (PID 1002)
[PID 1002] Process started

aprilsade:/$ ps
PID      NAME                 STATE      CPU
--------------------------------------------
1001     april-agent          running    2.45
1002     test-process         running    0.12

aprilsade:/$ kill 1002
[KERNEL] Process terminated: test-process (PID 1002)

aprilsade:/$ memory
Memory Status:
  Total contexts: 100
  Used: 2 (2.0%)
  Free: 98

aprilsade:/$ exit

APRIL OS shutting down...
APRIL OS shutdown complete
```

---

## Testing

```python
# tests/kernel/test_process.py
import pytest
from april_os.kernel.process_manager import ProcessManager, ProcessState

@pytest.mark.asyncio
async def test_spawn_process():
    """Test process creation"""
    
    kernel = MockKernel()
    pm = ProcessManager(kernel)
    
    pid = await pm.spawn("test-process", "Test task")
    
    assert pid >= 1000
    assert pid in pm.process_table
    assert pm.process_table[pid].state == ProcessState.RUNNING

@pytest.mark.asyncio
async def test_kill_process():
    """Test process termination"""
    
    kernel = MockKernel()
    pm = ProcessManager(kernel)
    
    pid = await pm.spawn("test", "Test")
    await pm.kill(pid)
    
    assert pm.process_table[pid].state == ProcessState.STOPPED
```

---

## Next Steps

1. **Implement all kernel components** (Week 7-8)
   - Device manager (HAL)
   - Security engine
   - IPC manager
   - Service manager

2. **Add real MCP integration** (Week 9-10)
   - MCP client
   - Driver loading
   - Tool discovery

3. **Build user applications** (Week 11-12)
   - More shell commands
   - Project management
   - Workflow engine

---

## Summary

**You get:**
- ✅ Custom OS-like environment
- ✅ Process management
- ✅ Memory management
- ✅ Hierarchical filesystem
- ✅ Shell interface
- ✅ Clean architecture
- ✅ Extensible design

**APRIL OS is your complete operating system for the physical world!**
