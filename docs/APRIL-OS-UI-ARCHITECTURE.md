# APRIL OS UI Architecture

**Complete User Interface Design for APRIL Operating System**

---

## Overview

APRIL OS provides multiple UI interfaces for different use cases:

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACES                            │
│                                                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  SHELL   │ │ DESKTOP  │ │   WEB    │ │   API    │       │
│  │  (CLI)   │ │   (GUI)  │ │ Dashboard│ │ (REST)   │       │
│  │          │ │          │ │          │ │          │       │
│  │ Terminal │ │ Native   │ │ Browser  │ │ HTTP/WS  │       │
│  │ Interface│ │ Desktop  │ │ Access   │ │ Client   │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Presentation Layer  │
              │   (API Gateway)        │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │     APRIL KERNEL      │
              └───────────────────────┘
```

---

## 1. Shell (CLI)

**Terminal interface - Primary interface for power users**

### Design

```python
# user/shell.py
import asyncio
import readline  # History support
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import WordCompleter
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn
from rich.markdown import Markdown

class AprilShell:
    """
    APRIL Shell - Rich CLI interface
    
    Features:
    - Auto-completion
    - Command history
    - Rich formatting (tables, progress, markdown)
    - Syntax highlighting
    - Multi-line input
    - Interactive prompts
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.console = Console()
        
        # Prompt toolkit
        self.session = PromptSession(
            history=FileHistory('.april_shell_history'),
            auto_suggest=AutoSuggestFromHistory(),
            completer=self._build_completer()
        )
        
        # Style
        self.style = Style.from_dict({
            'prompt': 'cyan bold',
            'path': 'green',
            'pid': 'yellow',
        })
        
        # Current state
        self.current_project = None
        self.current_device = None
    
    async def run(self):
        """Main shell loop"""
        
        self.console.print(Panel.fit(
            "[bold cyan]APRIL OS Shell v1.0[/bold cyan]\n"
            "Type 'help' for commands, 'exit' to quit",
            title="Welcome"
        ))
        
        while self.kernel.running:
            try:
                # Build prompt
                prompt = self._build_prompt()
                
                # Read command with rich features
                user_input = await self.session.prompt_async(
                    prompt,
                    style=self.style,
                    multiline=False
                )
                
                # Execute
                await self._execute(user_input)
            
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted[/yellow]")
                continue
            except EOFError:
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
    
    def _build_prompt(self) -> str:
        """Build dynamic prompt"""
        
        parts = ["[prompt]aprilsade[/prompt]"]
        
        # Add current project
        if self.current_project:
            parts.append(f"[blue]{self.current_project}[/blue]")
        
        # Add current directory
        parts.append(f"[path]{self.kernel.filesystem.current_dir}[/path]")
        
        # Add indicator
        parts.append("[prompt]$[/prompt]")
        
        return " ".join(parts) + " "
    
    def _build_completer(self):
        """Build auto-completer"""
        
        commands = [
            "ls", "cd", "ps", "kill", "run", "devices",
            "projects", "skills", "workflows", "memory",
            "logs", "help", "version", "exit"
        ]
        
        return WordCompleter(commands)
    
    async def _execute(self, user_input: str):
        """Execute command with rich output"""
        
        if not user_input.strip():
            return
        
        parts = user_input.strip().split()
        cmd = parts[0]
        args = parts[1:]
        
        # Command routing
        if cmd == "ls":
            await self._cmd_ls(args)
        elif cmd == "ps":
            await self._cmd_ps(args)
        elif cmd == "devices":
            await self._cmd_devices(args)
        elif cmd == "run":
            await self._cmd_run(args)
        elif cmd == "watch":
            await self._cmd_watch(args)
        elif cmd == "help":
            self._cmd_help()
        else:
            self.console.print(f"[red]Unknown command: {cmd}[/red]")
    
    async def _cmd_ps(self, args: list):
        """List processes with rich table"""
        
        processes = self.kernel.process_manager.list_processes()
        
        table = Table(title="Processes")
        table.add_column("PID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("State", style="yellow")
        table.add_column("CPU", justify="right")
        
        for p in processes:
            table.add_row(
                str(p['pid']),
                p['name'],
                p['state'],
                f"{p['cpu_time']:.2f}s"
            )
        
        self.console.print(table)
    
    async def _cmd_devices(self, args: list):
        """List devices with rich output"""
        
        devices = await self.kernel.device_manager.list_all()
        
        table = Table(title="Connected Devices")
        table.add_column("Name", style="cyan")
        table.add_column("Domain", style="blue")
        table.add_column("Status", style="green")
        table.add_column("Risk", style="yellow")
        
        for d in devices:
            # Color code status
            status_style = {
                "online": "green",
                "offline": "red",
                "busy": "yellow"
            }.get(d['status'], "white")
            
            table.add_row(
                d['name'],
                d['domain'],
                f"[{status_style}]{d['status']}[/{status_style}]",
                d['risk_level']
            )
        
        self.console.print(table)
    
    async def _cmd_run(self, args: list):
        """Run workflow with progress indicator"""
        
        if not args:
            self.console.print("[red]Usage: run <workflow>[/red]")
            return
        
        workflow_name = args[0]
        
        with Progress(
            SpinnerColumn(),
            *Progress.get_default_columns(),
            console=self.console
        ) as progress:
            task = progress.add_task(f"[cyan]Running {workflow_name}...", total=100)
            
            # Run workflow
            try:
                result = await self.kernel.run_workflow(workflow_name)
                
                progress.update(task, completed=100)
                
                self.console.print(f"\n[green]✓[/green] Workflow completed")
                
                # Show result
                if result.get('output'):
                    self.console.print(Panel(
                        Markdown(result['output']),
                        title="Output"
                    ))
            
            except Exception as e:
                progress.stop()
                self.console.print(f"\n[red]✗ Error: {e}[/red]")
    
    async def _cmd_watch(self, args: list):
        """Real-time monitoring dashboard"""
        
        if args and args[0] == "devices":
            await self._watch_devices()
        elif args and args[0] == "processes":
            await self._watch_processes()
        else:
            self.console.print("[red]Usage: watch <devices|processes>[/red]")
    
    async def _watch_devices(self):
        """Real-time device monitoring"""
        
        self.console.clear()
        self.console.print("[bold]Device Monitor (Ctrl-C to exit)[/bold]\n")
        
        try:
            while True:
                # Get device status
                devices = await self.kernel.device_manager.list_all()
                
                # Create live table
                table = Table(title=f"Device Status - {datetime.now().strftime('%H:%M:%S')}")
                table.add_column("Device")
                table.add_column("Status")
                table.add_column("Last Seen")
                
                for d in devices:
                    table.add_row(
                        d['name'],
                        d['status'],
                        d.get('last_seen', 'N/A')
                    )
                
                self.console.print(table)
                await asyncio.sleep(2)
                
                # Clear for refresh
                self.console.clear()
        
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Stopped watching[/yellow]")
    
    def _cmd_help(self):
        """Show help with rich formatting"""
        
        help_text = """
# APRIL Shell Commands

## Filesystem
- `ls [path]` - List files
- `cd <path>` - Change directory
- `cat <file>` - Read file

## Processes
- `ps` - List processes
- `run <workflow>` - Run workflow
- `kill <pid>` - Kill process

## Devices
- `devices` - List devices
- `device <name>` - Device details
- `watch devices` - Real-time monitor

## Monitoring
- `memory` - Memory status
- `logs` - View logs
- `watch processes` - Process monitor

## System
- `version` - Show version
- `help` - Show this help
- `exit` - Shutdown APRIL OS
        """
        
        self.console.print(Panel(Markdown(help_text), title="Help"))
```

---

## 2. Desktop GUI

**Native desktop interface for visual interaction**

### Architecture

```
april_os/desktop/
├── __init__.py
├── app.py                 # Main application
├── windows/
│   ├── main_window.py     # Main window
│   ├── project_window.py  # Project manager
│   ├── device_window.py   # Device manager
│   └── workflow_window.py # Workflow editor
├── widgets/
│   ├── device_card.py     # Device status card
│   ├── process_list.py    # Process table
│   ├── log_viewer.py      # Log viewer
│   └── workflow_canvas.py # Workflow diagram
└── resources/
    ├── icons/
    └── styles/
```

### Implementation (using PyQt6)

```python
# desktop/app.py
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
import sys

class AprilDesktop(QApplication):
    """
    APRIL Desktop Application
    
    Features:
    - System tray icon
    - Tab-based interface
    - Real-time updates
    - Notifications
    - Drag & drop workflows
    """
    
    def __init__(self, kernel):
        super().__init__(sys.argv)
        
        self.kernel = kernel
        
        # Set application properties
        self.setApplicationName("APRIL OS")
        self.setApplicationVersion("1.0.0")
        
        # Main window
        self.main_window = MainWindow(kernel)
        self.main_window.show()
        
        # System tray
        self.tray_icon = SystemTray(kernel)
        self.tray_icon.show()
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update)
        self.update_timer.start(1000)  # Update every second
    
    def _update(self):
        """Update all views"""
        self.main_window.update_views()

class MainWindow(QMainWindow):
    """Main desktop window"""
    
    def __init__(self, kernel):
        super().__init__()
        
        self.kernel = kernel
        
        self.setWindowTitle("APRIL OS Desktop")
        self.setGeometry(100, 100, 1200, 800)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Add tabs
        self.tabs.addTab(DashboardView(kernel), "Dashboard")
        self.tabs.addTab(DevicesView(kernel), "Devices")
        self.tabs.addTab(ProjectsView(kernel), "Projects")
        self.tabs.addTab(ProcessesView(kernel), "Processes")
        self.tabs.addTab(WorkflowsView(kernel), "Workflows")
        self.tabs.addTab(LogsView(kernel), "Logs")
        
        # Status bar
        self.statusBar().showMessage("APRIL OS Running")
        
        # Create menus
        self._create_menus()
    
    def _create_menus(self):
        """Create menu bar"""
        
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        file_menu.addAction("New Project", self._new_project)
        file_menu.addAction("Import Workflow", self._import_workflow)
        file_menu.addSeparator()
        file_menu.addAction("Settings", self._open_settings)
        file_menu.addSeparator()
        file_menu.addAction("Quit", self.close)
        
        # Devices menu
        devices_menu = menubar.addMenu("&Devices")
        devices_menu.addAction("Scan Network", self._scan_devices)
        devices_menu.addAction("Add Device", self._add_device)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction("Refresh", self._refresh)
    
    def update_views(self):
        """Update all views with latest data"""
        
        # Get current tab
        current_view = self.tabs.currentWidget()
        
        if hasattr(current_view, 'refresh'):
            current_view.refresh()

# desktop/windows/devices_view.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QScrollArea, QLabel, QPushButton, QGridLayout
)
from PyQt6.QtCore import Qt

class DevicesView(QWidget):
    """
    Device management view
    
    Features:
    - Grid of device cards
    - Real-time status updates
    - Device actions (connect, disconnect)
    - Device details panel
    """
    
    def __init__(self, kernel):
        super().__init__()
        
        self.kernel = kernel
        self.device_cards = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup UI layout"""
        
        layout = QVBoxLayout()
        
        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>Connected Devices</h2>"))
        header.addStretch()
        
        scan_btn = QPushButton("Scan Network")
        scan_btn.clicked.connect(self._scan_network)
        header.addWidget(scan_btn)
        
        layout.addLayout(header)
        
        # Device grid
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        self.device_grid = QWidget()
        self.grid_layout = QGridLayout()
        self.device_grid.setLayout(self.grid_layout)
        
        self.scroll_area.setWidget(self.device_grid)
        layout.addWidget(self.scroll_area)
        
        self.setLayout(layout)
    
    def refresh(self):
        """Refresh device list"""
        
        # Clear existing cards
        for card in self.device_cards.values():
            card.deleteLater()
        
        self.device_cards.clear()
        
        # Get devices
        devices = self.kernel.device_manager.list_all()
        
        # Add device cards
        for i, device in enumerate(devices):
            card = DeviceCard(device)
            
            row = i // 3
            col = i % 3
            
            self.grid_layout.addWidget(card, row, col)
            self.device_cards[device['name']] = card

class DeviceCard(QWidget):
    """Widget showing device status"""
    
    def __init__(self, device_info):
        super().__init__()
        
        self.device = device_info
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup card UI"""
        
        # Set fixed size
        self.setFixedSize(300, 150)
        
        layout = QVBoxLayout()
        
        # Device name and icon
        header = QHBoxLayout()
        icon_label = QLabel("📷" if self.device['domain'] == 'vision' else "🔌")
        header.addWidget(icon_label)
        
        name_label = QLabel(f"<b>{self.device['name']}</b>")
        header.addWidget(name_label)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Status
        status_color = {
            'online': 'green',
            'offline': 'red',
            'busy': 'orange'
        }.get(self.device['status'], 'gray')
        
        status_label = QLabel(
            f"<span style='color:{status_color}'>●</span> {self.device['status'].title()}"
        )
        layout.addWidget(status_label)
        
        # Domain and risk
        details = QLabel(
            f"Domain: {self.device['domain']} | Risk: {self.device['risk_level']}"
        )
        details.setStyleSheet("color: gray")
        layout.addWidget(details)
        
        # Actions
        actions = QHBoxLayout()
        
        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self._connect)
        actions.addWidget(connect_btn)
        
        details_btn = QPushButton("Details")
        details_btn.clicked.connect(self._show_details)
        actions.addWidget(details_btn)
        
        layout.addLayout(actions)
        
        self.setLayout(layout)
        
        # Styling
        self.setStyleSheet("""
            QWidget {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 10px;
            }
        """)
    
    def _connect(self):
        """Connect to device"""
        print(f"Connecting to {self.device['name']}")
    
    def _show_details(self):
        """Show device details"""
        print(f"Details for {self.device['name']}")
```

---

## 3. Web Dashboard

**Browser-based interface for remote access**

### Architecture

```python
# user/web/app.py
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio

class WebDashboard:
    """
    Web dashboard for APRIL OS
    
    Features:
    - Real-time updates via WebSocket
    - Responsive design
    - Mobile-friendly
    - Live charts
    - Remote access
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.app = FastAPI()
        
        # Mount static files
        self.app.mount("/static", StaticFiles(directory="web/static"), name="static")
        
        # Routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup HTTP routes"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def home():
            """Dashboard home"""
            return self._render_dashboard()
        
        @self.app.get("/api/devices")
        async def get_devices():
            """Get device list"""
            return await self.kernel.device_manager.list_all()
        
        @self.app.get("/api/processes")
        async def get_processes():
            """Get process list"""
            return self.kernel.process_manager.list_processes()
        
        @self.app.get("/api/memory")
        async def get_memory():
            """Get memory status"""
            return self.kernel.memory_manager.memory_status()
        
        @self.app.post("/api/run")
        async def run_workflow(workflow: str):
            """Run workflow"""
            return await self.kernel.run_workflow(workflow)
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket for real-time updates"""
            await websocket.accept()
            
            while True:
                # Send updates
                data = {
                    "devices": await self.kernel.device_manager.list_all(),
                    "processes": self.kernel.process_manager.list_processes(),
                    "memory": self.kernel.memory_manager.memory_status()
                }
                
                await websocket.send_json(data)
                await asyncio.sleep(1)
    
    def _render_dashboard(self) -> str:
        """Render dashboard HTML"""
        
        return """
<!DOCTYPE html>
<html>
<head>
    <title>APRIL OS Dashboard</title>
    <link rel="stylesheet" href="/static/style.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <header>
            <h1>APRIL OS Dashboard</h1>
            <nav>
                <a href="/">Dashboard</a>
                <a href="/devices">Devices</a>
                <a href="/projects">Projects</a>
                <a href="/workflows">Workflows</a>
            </nav>
        </header>
        
        <main>
            <div class="row">
                <div class="card">
                    <h3>Devices</h3>
                    <canvas id="devicesChart"></canvas>
                </div>
                
                <div class="card">
                    <h3>Processes</h3>
                    <canvas id="processesChart"></canvas>
                </div>
                
                <div class="card">
                    <h3>Memory</h3>
                    <div class="gauge" id="memoryGauge"></div>
                </div>
            </div>
            
            <div class="row">
                <div class="card">
                    <h3>Active Processes</h3>
                    <table id="processTable">
                        <thead>
                            <tr>
                                <th>PID</th>
                                <th>Name</th>
                                <th>State</th>
                                <th>CPU</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
        </main>
    </div>
    
    <script src="/static/dashboard.js"></script>
</body>
</html>
        """

# web/static/dashboard.js
class AprilDashboard {
    constructor() {
        this.ws = null;
        this.init();
    }
    
    init() {
        this.connectWebSocket();
        this.initCharts();
    }
    
    connectWebSocket() {
        this.ws = new WebSocket('ws://localhost:8000/ws');
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.updateDashboard(data);
        };
    }
    
    updateDashboard(data) {
        // Update process table
        const tbody = document.querySelector('#processTable tbody');
        tbody.innerHTML = '';
        
        data.processes.forEach(proc => {
            const row = tbody.insertRow();
            row.innerHTML = `
                <td>${proc.pid}</td>
                <td>${proc.name}</td>
                <td><span class="badge">${proc.state}</span></td>
                <td>${proc.cpu_time.toFixed(2)}s</td>
            `;
        });
        
        // Update charts
        this.updateCharts(data);
    }
    
    initCharts() {
        // Initialize Chart.js charts
    }
    
    updateCharts(data) {
        // Update chart data
    }
}

new AprilDashboard();
```

---

## 4. API Server

**REST API for programmatic access**

```python
# user/api_server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

class AprilAPIServer:
    """
    REST API for APRIL OS
    
    Endpoints:
    - GET  /api/status          - System status
    - GET  /api/processes       - List processes
    - POST /api/processes       - Create process
    - GET  /api/processes/{pid} - Get process
    - DEL  /api/processes/{pid} - Kill process
    - GET  /api/devices         - List devices
    - GET  /api/devices/{name}  - Get device
    - POST /api/workflows       - Run workflow
    - GET  /api/projects        - List projects
    - POST /api/projects        - Create project
    - WS   /ws                  - WebSocket updates
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.app = FastAPI(title="APRIL OS API", version="1.0.0")
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup API routes"""
        
        @self.app.get("/api/status")
        async def get_status():
            """Get system status"""
            return {
                "status": "running",
                "version": self.kernel.version,
                "uptime": time.time() - self.kernel.start_time,
                "processes": len(self.kernel.process_manager.process_table),
                "devices": len(await self.kernel.device_manager.list_all()),
                "memory": self.kernel.memory_manager.memory_status()
            }
        
        @self.app.get("/api/processes")
        async def list_processes():
            """List all processes"""
            return self.kernel.process_manager.list_processes()
        
        @self.app.post("/api/processes")
        async def create_process(request: ProcessCreate):
            """Create new process"""
            pid = await self.kernel.process_manager.spawn(
                name=request.name,
                task=request.task,
                priority=request.priority
            )
            
            return {"pid": pid, "status": "created"}
        
        @self.app.get("/api/processes/{pid}")
        async def get_process(pid: int):
            """Get process by PID"""
            if pid not in self.kernel.process_manager.process_table:
                raise HTTPException(status_code=404, detail="Process not found")
            
            pcb = self.kernel.process_manager.process_table[pid]
            
            return {
                "pid": pcb.pid,
                "name": pcb.name,
                "state": pcb.state.value,
                "priority": pcb.priority,
                "cpu_time": pcb.cpu_time
            }
        
        @self.app.delete("/api/processes/{pid}")
        async def kill_process(pid: int):
            """Kill process"""
            await self.kernel.process_manager.kill(pid)
            
            return {"status": "killed"}
        
        @self.app.get("/api/devices")
        async def list_devices():
            """List all devices"""
            return await self.kernel.device_manager.list_all()
        
        @self.app.post("/api/workflows")
        async def run_workflow(request: WorkflowRun):
            """Run workflow"""
            result = await self.kernel.run_workflow(
                name=request.name,
                params=request.params
            )
            
            return result
        
        @self.app.get("/api/projects")
        async def list_projects():
            """List all projects"""
            return await self.kernel.filesystem.list_projects()
        
        @self.app.post("/api/projects")
        async def create_project(request: ProjectCreate):
            """Create new project"""
            project_id = await self.kernel.project_manager.create(
                goal=request.goal,
                plan=request.plan
            )
            
            return {"project_id": project_id}
    
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Run API server"""
        uvicorn.run(self.app, host=host, port=port)

# Request models
class ProcessCreate(BaseModel):
    name: str
    task: str
    priority: Optional[int] = 0

class WorkflowRun(BaseModel):
    name: str
    params: Optional[dict] = {}

class ProjectCreate(BaseModel):
    goal: str
    plan: List[str]
```

---

## 5. System Tray

**Background indicator for quick access**

```python
# desktop/tray.py
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon

class SystemTray(QSystemTrayIcon):
    """
    System tray icon for APRIL OS
    
    Features:
    - Status indicator
    - Quick actions
    - Notifications
    - Background running
    """
    
    def __init__(self, kernel):
        super().__init__()
        
        self.kernel = kernel
        
        # Set icon
        self.setIcon(QIcon("resources/icons/april.png"))
        
        # Context menu
        menu = QMenu()
        
        # Status
        status_action = menu.addAction("APRIL OS: Running")
        status_action.setEnabled(False)
        
        menu.addSeparator()
        
        # Actions
        menu.addAction("Open Dashboard", self._open_dashboard)
        menu.addAction("New Project", self._new_project)
        menu.addAction("Run Workflow", self._run_workflow)
        
        menu.addSeparator()
        
        # Devices
        devices_menu = menu.addMenu("Devices")
        # Add devices dynamically
        
        menu.addSeparator()
        
        # System
        menu.addAction("Settings", self._open_settings)
        menu.addAction("Quit", self._quit)
        
        self.setContextMenu(menu)
        
        # Show notification on boot
        self.showMessage(
            "APRIL OS",
            "APRIL OS is running in the background",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )
    
    def _open_dashboard(self):
        """Open web dashboard"""
        import webbrowser
        webbrowser.open("http://localhost:8000")
    
    def _new_project(self):
        """Create new project"""
        print("New project")
    
    def _run_workflow(self):
        """Run workflow"""
        print("Run workflow")
    
    def _open_settings(self):
        """Open settings"""
        print("Settings")
    
    def _quit(self):
        """Quit APRIL OS"""
        asyncio.create_task(self.kernel.shutdown())
```

---

## 6. Notification System

```python
# desktop/notifications.py
from PyQt6.QtWidgets import QSystemTrayIcon

class NotificationManager:
    """
    Notification system
    
    Types:
    - Device status changes
    - Process completion
    - Security alerts
    - Workflow progress
    """
    
    def __init__(self, tray_icon):
        self.tray = tray_icon
    
    def notify_device_online(self, device_name: str):
        """Notify device came online"""
        self.tray.showMessage(
            f"{device_name} Online",
            f"Device {device_name} is now connected",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )
    
    def notify_device_offline(self, device_name: str):
        """Notify device went offline"""
        self.tray.showMessage(
            f"{device_name} Offline",
            f"Device {device_name} disconnected",
            QSystemTrayIcon.MessageIcon.Warning,
            3000
        )
    
    def notify_workflow_complete(self, workflow_name: str):
        """Notify workflow completed"""
        self.tray.showMessage(
            f"Workflow Complete",
            f"{workflow_name} finished successfully",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )
    
    def notify_security_alert(self, message: str):
        """Notify security issue"""
        self.tray.showMessage(
            "Security Alert",
            message,
            QSystemTrayIcon.MessageIcon.Critical,
            5000
        )
```

---

## UI Features Summary

| Interface | Technology | Use Case |
|-----------|-------------|----------|
| **Shell** | prompt-toolkit + Rich | Power users, scripting |
| **Desktop** | PyQt6 | Visual management, drag & drop |
| **Web** | FastAPI + WebSocket | Remote access, monitoring |
| **API** | REST + JSON | Integration, automation |
| **Tray** | System tray | Background, notifications |
| **Mobile** | Responsive web | On-the-go access |

---

## Setup Instructions

### Install UI Dependencies

```bash
# Add to requirements.txt
prompt-toolkit>=3.0.0
rich>=13.0.0
PyQt6>=6.5.0
fastapi>=0.104.0
uvicorn>=0.24.0
websockets>=12.0
```

### Start UI Components

```bash
# Start kernel with all UIs
aprils-ade boot --ui all

# Start specific UIs
aprils-ade boot --ui shell
aprils-ade boot --ui desktop
aprils-ade boot --ui web --port 8000
aprils-ade boot --ui api --port 8080

# Start multiple UIs
aprils-ade boot --ui shell,web,api
```

---

## Complete UI Architecture

```
User Interfaces
├── Shell (CLI)
│   ├── Rich terminal UI
│   ├── Auto-completion
│   ├── Command history
│   └── Real-time monitoring
│
├── Desktop (GUI)
│   ├── MainWindow (tabs)
│   ├── Dashboard view
│   ├── Device manager
│   ├── Project manager
│   ├── Workflow editor
│   ├── Process monitor
│   └── System tray
│
├── Web Dashboard
│   ├── Browser-based UI
│   ├── Real-time updates (WebSocket)
│   ├── Charts and graphs
│   ├── Mobile responsive
│   └── Remote access
│
└── API Server
    ├── REST endpoints
    ├── WebSocket updates
    ├── JSON responses
    └── Automation friendly
```

---

**Your complete UI layer for APRIL OS!** 🎨
