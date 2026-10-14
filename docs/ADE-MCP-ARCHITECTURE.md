# ADE MCP Integration Architecture

**How APRIL's ADE uses MCP servers to manage software and devices**

---

## Architectural Clarification

**Key insight:** The ADE runs locally on the machine and manages:
1. **Software applications** → via local MCP servers
2. **Physical devices** → via network + MCP servers

This means the Tool Layer should be redesigned as an **MCP Client Layer** that discovers and communicates with MCP servers, rather than implementing tools directly.

---

## Revised Three-Pillar Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    APRIL ADE                                 │
│                   (on the machine)                           │
│                                                              │
│    ┌─────────────────────────────────────────────────┐      │
│    │            CORE AGENT RUNTIME                    │      │
│    │  • Conversation loop                             │      │
│    │  • Skill dispatch                                │      │
│    │  • Safety enforcement                            │      │
│    └─────────────────────────────────────────────────┘      │
│                            │                                 │
│                            ▼                                 │
│    ┌─────────────────────────────────────────────────┐      │
│    │            MCP CLIENT LAYER                      │      │
│    │  • Server discovery                              │      │
│    │  • Protocol handling (JSON-RPC over stdio/SSE)  │      │
│    │  • Tool registration                             │      │
│    │  • Resource management                           │      │
│    └─────────────────────────────────────────────────┘      │
│                            │                                 │
└────────────────────────────┼─────────────────────────────────┘
                             │
                  ┌──────────┴──────────┐
                  │                     │
        ┌─────────▼────────┐   ┌───────▼──────────┐
        │   LOCAL MCP      │   │   NETWORK MCP    │
        │   SERVERS        │   │   SERVERS        │
        │                  │   │                  │
        │  (Software       │   │  (Device        │
        │   integration)   │   │   bridges)      │
        └──────────────────┘   └──────────────────┘
                  │                     │
        ┌─────────▼────────┐   ┌───────▼──────────┐
        │   SOFTWARE       │   │   DEVICES        │
        │   APPLICATIONS   │   │   (Body)         │
        │                  │   │                  │
        │  • CAD/EDA       │   │  • Cameras       │
        │  • Slicers       │   │  • ESP32         │
        │  • Vision models │   │  • Appliances    │
        │  • Code tools    │   │  • Robots        │
        └──────────────────┘   │  • Machines      │
                               └──────────────────┘
```

---

## MCP Server Categories

### 1. **Local MCP Servers** (Software Integrations)

These servers run locally on the machine and bridge to software applications:

| MCP Server | Manages | Transport | Risk Level |
|------------|---------|-----------|------------|
| `mcp-cad-freecad` | FreeCAD API | stdio | medium |
| `mcp-eda-kicad` | KiCad CLI | stdio | medium |
| `mcp-slicer-prusa` | PrusaSlicer | stdio | high |
| `mcp-vision-llava` | LLaVA vision model | HTTP/SSE | low |
| `mcp-code-filesystem` | File editing | stdio | medium |
| `mcp-shell-command` | Shell execution | stdio | medium |

### 2. **Network MCP Servers** (Device Bridges)

These servers run as bridges on the network (or locally) and communicate with physical devices:

| MCP Server | Manages | Connection | Risk Level |
|------------|---------|------------|------------|
| `mcp-esp32-bridge` | ESP32 devices | HTTP → Device | varies |
| `mcp-camera-rtsp` | RTSP cameras | RTSP stream | medium |
| `mcp-home-smart` | Smart home devices | WiFi/Zigbee | medium |
| `mcp-printer-3d` | 3D printer (OctoPrint) | HTTP API | high |
| `mcp-cnc-controller` | CNC machine | Serial/G-code | critical |
| `mcp-robot-arm` | Robot arm (ROS/ESP) | HTTP/Serial | critical |

---

## MCP Integration Architecture

### Core Components

```python
# core/mcp_client.py
from dataclasses import dataclass
from typing import Optional
import subprocess
import json
import asyncio

@dataclass
class MCPServerConfig:
    """Configuration for an MCP server"""
    name: str
    command: str  # Command to start server
    args: list[str] = None
    env: dict = None
    transport: str = "stdio"  # stdio, sse, http
    
class MCPClient:
    """Client for communicating with MCP servers"""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.initialized = False
        self.tools: list[dict] = []
        self.resources: list[dict] = []
    
    async def start(self):
        """Start MCP server process"""
        if self.config.transport == "stdio":
            self.process = subprocess.Popen(
                [self.config.command] + (self.config.args or []),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, **(self.config.env or {})}
            )
            
            # Initialize connection
            await self._send_initialize()
    
    async def _send_initialize(self):
        """Send initialize request to MCP server"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": "APRIL-ADE",
                    "version": "1.0.0"
                }
            }
        }
        
        response = await self._send_request(request)
        
        if response.get("result"):
            self.initialized = True
            # Discover available tools
            await self._discover_tools()
    
    async def _discover_tools(self):
        """Discover tools provided by this server"""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        
        response = await self._send_request(request)
        
        if "result" in response:
            self.tools = response["result"].get("tools", [])
    
    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Call a tool on the MCP server"""
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        }
        
        return await self._send_request(request)
    
    async def _send_request(self, request: dict) -> dict:
        """Send JSON-RPC request to server"""
        if not self.process:
            raise RuntimeError("MCP server not started")
        
        # Write request
        request_str = json.dumps(request) + "\n"
        self.process.stdin.write(request_str.encode())
        self.process.stdin.flush()
        
        # Read response
        response_str = self.process.stdout.readline().decode()
        return json.loads(response_str)
    
    def _next_id(self) -> int:
        """Generate next request ID"""
        if not hasattr(self, '_id_counter'):
            self._id_counter = 0
        self._id_counter += 1
        return self._id_counter
    
    async def shutdown(self):
        """Gracefully shutdown server"""
        if self.process:
            request = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "shutdown"
            }
            await self._send_request(request)
            self.process.terminate()
            self.process.wait()
```

### MCP Server Manager

```python
# core/mcp_manager.py
from typing import Dict, List
import asyncio

class MCPManager:
    """Manages all MCP server connections"""
    
    def __init__(self):
        self._servers: Dict[str, MCPClient] = {}
        self._tool_index: Dict[str, str] = {}  # tool_name -> server_name
    
    async def register_server(self, config: MCPServerConfig):
        """Register and start an MCP server"""
        client = MCPClient(config)
        await client.start()
        
        self._servers[config.name] = client
        
        # Index tools
        for tool in client.tools:
            tool_name = tool["name"]
            self._tool_index[tool_name] = config.name
    
    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Call a tool on the appropriate server"""
        if name not in self._tool_index:
            raise ValueError(f"Tool not found: {name}")
        
        server_name = self._tool_index[name]
        server = self._servers[server_name]
        
        return await server.call_tool(name, arguments)
    
    def list_tools(self) -> List[dict]:
        """List all available tools across all servers"""
        all_tools = []
        for server in self._servers.values():
            all_tools.extend(server.tools)
        return all_tools
    
    def to_openai_tools(self) -> List[dict]:
        """Convert MCP tools to OpenAI function format"""
        openai_tools = []
        
        for tool in self.list_tools():
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {})
                }
            }
            openai_tools.append(openai_tool)
        
        return openai_tools
    
    async def shutdown_all(self):
        """Shutdown all servers"""
        for server in self._servers.values():
            await server.shutdown()
```

---

## Example MCP Server Implementations

### Local Software Integration: FreeCAD MCP Server

```python
# mcp_servers/freecad_server.py
# This would be an external MCP server process

from mcp.server import Server
from mcp.server.stdio import stdio_server
import FreeCAD
import Part

app = Server("freecad-server")

@app.tool("create_box")
async def create_box(width: float, height: float, depth: float) -> str:
    """Create a 3D box in FreeCAD"""
    doc = FreeCAD.newDocument("Untitled")
    box = doc.addObject("Part::Box", "Box")
    box.Length = width
    box.Width = height
    box.Height = depth
    
    # Export to STEP
    import Export
    Export.export([box], "/tmp/box.step")
    
    return "/tmp/box.step"

@app.tool("export_step")
async def export_step(filepath: str) -> dict:
    """Export active document to STEP format"""
    FreeCAD.getDocument("Untitled").saveAs(filepath)
    return {"status": "saved", "path": filepath}

if __name__ == "__main__":
    stdio_server.run(app)
```

### Network Device Bridge: ESP32 MCP Server

```python
# mcp_servers/esp32_bridge_server.py
# This runs as a bridge, could be local or on network device

from mcp.server import Server
from mcp.server.stdio import stdio_server
import requests

app = Server("esp32-bridge")

# Device registry (config)
DEVICES = {
    "esp-lab": "http://192.168.1.100",
    "esp-workshop": "http://192.168.1.101"
}

@app.tool("read_temperature")
async def read_temperature(device_name: str) -> dict:
    """Read temperature from ESP32 device"""
    if device_name not in DEVICES:
        return {"error": f"Unknown device: {device_name}"}
    
    endpoint = DEVICES[device_name]
    response = requests.get(f"{endpoint}/temperature", timeout=5)
    
    if response.status_code == 200:
        data = response.json()
        return {
            "device": device_name,
            "temperature_celsius": data["temperature_celsius"],
            "timestamp": data.get("timestamp")
        }
    else:
        return {"error": f"Device error: {response.status_code}"}

@app.tool("read_humidity")
async def read_humidity(device_name: str) -> dict:
    """Read humidity from ESP32 device"""
    if device_name not in DEVICES:
        return {"error": f"Unknown device: {device_name}"}
    
    endpoint = DEVICES[device_name]
    response = requests.get(f"{endpoint}/humidity", timeout=5)
    
    if response.status_code == 200:
        data = response.json()
        return {
            "device": device_name,
            "humidity_percent": data["humidity_percent"],
            "timestamp": data.get("timestamp")
        }
    else:
        return {"error": f"Device error: {response.status_code}"}

if __name__ == "__main__":
    stdio_server.run(app)
```

---

## Configuration Schema

### `.ade/mcp_config.yaml`

```yaml
# MCP Server Configuration

version: 1

# Local software MCP servers
local_servers:
  - name: freecad
    command: python
    args: ["/path/to/mcp_servers/freecad_server.py"]
    transport: stdio
    enabled: true
    metadata:
      domain: fabrication
      risk: medium
    
  - name: vision-llava
    command: python
    args: ["/path/to/mcp_servers/vision_server.py"]
    transport: stdio
    enabled: true
    metadata:
      domain: vision
      risk: low
  
  - name: shell-commands
    command: python
    args: ["/path/to/mcp_servers/shell_server.py"]
    transport: stdio
    enabled: true
    metadata:
      domain: machine
      risk: medium

# Network device MCP bridges
network_servers:
  - name: esp32-bridge
    command: python
    args: ["/path/to/mcp_servers/esp32_bridge_server.py"]
    transport: stdio
    enabled: true
    metadata:
      domain: sensing
      devices: [esp-lab, esp-workshop]
      risk: low
  
  - name: camera-bridge
    command: python
    args: ["/path/to/mcp_servers/camera_bridge_server.py"]
    transport: stdio
    enabled: true
    metadata:
      domain: vision
      devices: [camera-gate, camera-workshop]
      risk: medium

# Discovery and health check
discovery:
  auto_discover_network_servers: false
  health_check_interval: 30  # seconds
  
# Safety: which server actions require approval
safety:
  server_risk_overrides:
    shell-commands:
      risk: medium  # Override default
    # Critical servers always require confirmation
```

---

## Updated Tool Flow

### Before (Direct Tool Implementation):

```python
# Old: APRIL directly implements tools
class ShellTool(Tool):
    def execute(self, command: str):
        return subprocess.run(command, ...)
        
runtime = AgentRuntime(tools={"shell_execute": ShellTool()})
```

### After (MCP Client Layer):

```python
# New: APRIL calls tools via MCP servers
mcp_manager = MCPManager()

await mcp_manager.register_server(MCPServerConfig(
    name="shell-commands",
    command="python",
    args=["mcp_servers/shell_server.py"]
))

# Agent runtime uses MCP manager
runtime = AgentRuntime(
    tools=mcp_manager.to_openai_tools(),
    tool_executor=mcp_manager.call_tool
)

# Tool call flow:
# APRIL → MCP Client → shell-commands MCP server → subprocess → result back
```

---

## Benefits of MCP Architecture

### 1. **Separation of Concerns**
- ADE focuses on orchestration, safety, state management
- MCP servers handle specific integrations
- Clean interfaces between components

### 2. **Modularity**
- Add new software/device by adding MCP server
- No changes to ADE core
- Mix and match servers

### 3. **Isolation**
- MCP servers run as separate processes
- Crashes don't bring down ADE
- Better error handling

### 4. **Standardized Protocol**
- All integrations use same protocol
- Easy to debug (JSON-RPC)
- Standard tool discovery
- Built-in resource management

### 5. **Network Flexibility**
- MCP servers can run anywhere
- Device bridges can be local or remote
- Protocol works over stdio, HTTP, SSE

### 6. **Language Agnostic**
- MCP servers can be written in any language
- Python server for FreeCAD
- Node.js server for web tools
- Go server for robotics

---

## Security Considerations

### MCP Server Sandboxing

Each MCP server should declare its capabilities:

```python
# mcp_servers/manifest.json for esp32-bridge
{
  "name": "esp32-bridge",
  "version": "1.0.0",
  "capabilities": {
    "tools": ["read_temperature", "read_humidity"],
    "resources": ["devices"],
    "network": {
      "allowed_hosts": ["192.168.1.100", "192.168.1.101"],
      "allowed_ports": [80]
    }
  },
  "risk_level": "low",
  "requires_approval": false
}
```

### ADE Enforcement

```python
# core/mcp_safety.py
class MCPSafetyWrapper:
    def __init__(self, mcp_manager: MCPManager, safety_engine: SafetyEngine):
        self.mcp = mcp_manager
        self.safety = safety_engine
    
    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Call tool with safety enforcement"""
        
        # Get server metadata
        server_name = self.mcp._tool_index[name]
        server_config = self.mcp_config.get_server(server_name)
        
        # Check risk level
        risk_level = server_config.metadata.get("risk", "low")
        device_name = arguments.get("device_name")
        
        if device_name:
            # Physical device action
            device = self.device_registry.get(device_name)
            if device:
                allowed, reason = self.safety.check_device_action(
                    device, f"Call tool {name}"
                )
                if not allowed:
                    return {"error": f"Action denied: {reason}"}
        
        # Execute via MCP
        return await self.mcp.call_tool(name, arguments)
```

---

## Implementation Priority with MCP

### Phase 1 Updated: Core Runtime + MCP Client (Week 1-2)

**Build:**
- [ ] AgentRuntime (unchanged)
- [ ] MCPClient class
- [ ] MCPManager
- [ ] First local MCP server: `shell-commands`
- [ ] First network MCP server: `esp32-bridge`
- [ ] Tool discovery from MCP servers
- [ ] Basic CLI

**Test:**
```bash
# Start ADE with MCP servers
aprils-ade start --config .ade/mcp_config.yaml

# List servers
aprils-ade mcp list

# List tools
aprils-ade mcp tools

# Chat with MCP tools
aprils-ade chat
> Execute: ls -la
[APRIL calls shell-commands MCP server]
> Read temperature from esp-lab
[APRIL calls esp32-bridge MCP server]
```

---

## Example Workflow: Bracket Design with MCP

```bash
aprils-ade chat

User: "Print a bracket 30°"

APRIL:
  1. Plans: Design → Slice → Print
  2. Discovers tools from MCP servers:
     - freecad.create_box (from freecad server)
     - prusa-slicer.slice (from prusa server)
     - octoprint.upload_print (from printer server)
  
  3. Calls freecad.create_box via MCP:
     Tool: create_box
     Server: freecad (local MCP)
     Result: /tmp/bracket.step
  
  4. Calls prusa-slicer.slice via MCP:
     Tool: slice
     Server: prusa-slicer (local MCP)
     Result: /tmp/bracket.gcode
  
  5. Safety check (high risk device):
     Device: 3d-printer
     Risk: HIGH
     Action: Prompt user "Start print?"
  
  6. If approved, calls octoprint.upload_print:
     Tool: upload_print
     Server: printer-bridge (network MCP)
     Result: Print started
  
  7. Project complete, artifacts saved
```

---

## Summary

**Key Architecture Changes:**

1. **ADE → MCP Client Layer** (not direct tool implementation)
2. **MCP Servers** provide all tool capabilities
3. **Local MCP servers** → software integrations
4. **Network MCP servers** → device bridges
5. **Standard protocol** across all integrations
6. **Separation of concerns**: ADE orchestrates, MCP servers integrate

**Benefits:**
- Modular and extensible
- Language agnostic
- Better isolation and security
- Standard tool discovery
- Network flexibility

**Next Step:** Update the main architecture documents to reflect this MCP-centric design, then proceed with Phase 1 implementation of MCP client layer.
