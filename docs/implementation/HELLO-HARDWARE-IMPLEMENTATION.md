# Hello Hardware Implementation Plan

**Minimum viable ADE to control your first physical device (ESP32 S3)**

---

## Philosophy

**Build the minimal foundation that:**
1. Works today for basic devices (telemetry, cameras)
2. Extends tomorrow for complex hardware (robots, machines)
3. Establishes the hardware abstraction pattern

**Core insight:** Every hardware interaction follows the same pattern:

```
Agent → Tool → Device Translator → Protocol → Hardware
   ↑                                              ↓
   ←────────────── Response ───────────────────────
```

---

## Phase 1: Hello Hardware (Week 1-3)

**Goal:** Agent reads telemetry from your ESP32 S3

**Deliverables:**
- ✅ Agent runtime (minimal)
- ✅ Tool framework (extensible)
- ✅ Device registry (hardware abstraction)
- ✅ ESP32 S3 integration (WiFi + BLE ready)
- ✅ Basic safety (ownership verification)
- ✅ CLI interface

**Test:**
```bash
aprils chat
> Read WiFi signal strength from my ESP32
[ESP32 S3] RSSI: -42 dBm, Connected to LabNetwork
```

---

## Architecture

### Layered Design (Hardware-Aware)

```
┌─────────────────────────────────────────────┐
│         User Interface Layer                 │
│         (CLI, future: GUI, API)              │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         Agent Runtime Layer                  │
│  • LLM conversation                           │
│  • Tool selection                             │
│  • Context management                        │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         Tool Framework Layer                 │
│  • Tool registry                             │
│  • Execution interface                       │
│  • Result formatting                         │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         Device Registry Layer (KEY)          │
│  • Device discovery                          │
│  • Protocol abstraction                      │
│  • State management                          │
│  • Health monitoring                         │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         Protocol Layer (Extensible)           │
│  • HTTP client                               │
│  • BLE client (ESP32 S3)                     │
│  • Serial client                             │
│  • WebSocket client (future)                 │
│  • MQTT client (future)                      │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         Safety Layer                         │
│  • Device ownership                          │
│  • Operation validation                      │
│  • Rate limiting                             │
│  • Error recovery                            │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         Physical Hardware                    │
│  ESP32 S3 (WiFi6 + BLE)                      │
│  Cameras, Robots, Machines (future)          │
└─────────────────────────────────────────────┘
```

---

## Directory Structure

```
april_ade/
├── core/
│   ├── __init__.py
│   ├── agent.py              # Agent runtime
│   ├── config.py             # Configuration
│   └── session.py            # Session management
│
├── tools/
│   ├── __init__.py
│   ├── base.py               # Base tool class (extensible)
│   ├── shell.py              # Shell tool
│   └── device_tool.py        # Device control tool
│
├── devices/
│   ├── __init__.py
│   ├── registry.py           # Device registry (THE OS LAYER)
│   ├── base.py               # Abstract device class
│   ├── discovery.py          # Network discovery
│   │
│   ├── esp32/
│   │   ├── __init__.py
│   │   ├── device.py         # ESP32 S3 device class
│   │   ├── wifi_client.py    # WiFi protocol
│   │   └── ble_client.py     # BLE protocol
│   │
│   └── camera/               # Future: Camera support
│       └── placeholder.py
│
├── protocols/
│   ├── __init__.py
│   ├── base.py               # Protocol interface
│   ├── http.py               # HTTP protocol
│   ├── ble.py                # BLE protocol
│   └── serial.py             # Serial protocol (future)
│
├── safety/
│   ├── __init__.py
│   ├── engine.py             # Safety validation
│   └── policies.py           # Safety policies
│
├── cli/
│   ├── __init__.py
│   └── main.py               # CLI entry point
│
└── config/
    ├── __init__.py
    └── loader.py            # Config loader

.ade/
├── devices.json             # Device registry (owned devices)
├── config.yaml              # ADE configuration
└── cache/                   # Device state cache
    └── esp32_s3.json

tests/
├── test_agent.py
├── test_tools.py
├── test_devices.py
└── test_safety.py
```

---

## Core Components

### 1. Device Registry (The Hardware Abstraction)

**Purpose:** The "OS kernel" for hardware - manages all devices, their state, and protocols.

```python
# devices/registry.py

from typing import Dict, List, Optional, Type
from dataclasses import dataclass, field
import json
from pathlib import Path

@dataclass
class DeviceInfo:
    """Device metadata"""
    id: str
    name: str
    device_type: str
    protocols: List[str]
    address: str
    capabilities: List[str]
    metadata: Dict = field(default_factory=dict)
    last_seen: Optional[str] = None
    status: str = "unknown"


class DeviceRegistry:
    """
    Hardware abstraction registry (OS layer)
    
    Responsibilities:
    - Maintain list of known devices
    - Map friendly names to hardware addresses
    - Provide device instances
    - Monitor device health
    - Cache device state
    """
    
    def __init__(self, config_path: Path = None):
        self.devices: Dict[str, DeviceInfo] = {}
        self.config_path = config_path or Path(".ade/devices.json")
        self._device_classes: Dict[str, Type] = {}
        self._load_registry()
        self._register_device_classes()
    
    def register_device(self, device_info: DeviceInfo):
        """Register a device"""
        self.devices[device_info.id] = device_info
        self._save_registry()
    
    def get_device(self, device_id: str):
        """Get device instance by ID or name"""
        info = self.devices.get(device_id)
        if not info:
            # Try to find by name
            for d in self.devices.values():
                if d.name == device_id:
                    info = d
                    break
        
        if not info:
            raise ValueError(f"Device not found: {device_id}")
        
        # Instantiate device class
        device_class = self._device_classes.get(info.device_type)
        if not device_class:
            raise ValueError(f"Unknown device type: {info.device_type}")
        
        return device_class(info)
    
    def list_devices(self) -> List[DeviceInfo]:
        """List all registered devices"""
        return list(self.devices.values())
    
    def discover_devices(self, network_range: str = "192.168.1.0/24") -> List[DeviceInfo]:
        """Discover devices on network"""
        from .discovery import NetworkDiscovery
        discovery = NetworkDiscovery(network_range)
        return discovery.scan()
    
    def _load_registry(self):
        """Load device registry from disk"""
        if self.config_path.exists():
            with open(self.config_path) as f:
                data = json.load(f)
                for device_data in data.get("devices", []):
                    info = DeviceInfo(**device_data)
                    self.devices[info.id] = info
    
    def _save_registry(self):
        """Save device registry to disk"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "devices": [d.__dict__ for d in self.devices.values()]
        }
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _register_device_classes(self):
        """Register available device classes"""
        from .esp32.device import ESP32Device
        self._device_classes["esp32"] = ESP32Device
        # Future: register other device types
        # self._device_classes["camera"] = CameraDevice
        # self._device_classes["robot"] = RobotDevice
```

### 2. Abstract Device Class

**Purpose:** Define the interface that ALL devices must implement.

```python
# devices/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class DeviceResult:
    """Result from device operation"""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseDevice(ABC):
    """
    Abstract base class for all hardware devices
    
    This is the "device driver" interface
    """
    
    def __init__(self, device_info):
        self.info = device_info
        self._connected = False
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to device"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from device"""
        pass
    
    @abstractmethod
    async def read(self, attribute: str) -> DeviceResult:
        """Read attribute from device"""
        pass
    
    @abstractmethod
    async def write(self, attribute: str, value: Any) -> DeviceResult:
        """Write attribute to device"""
        pass
    
    @abstractmethod
    async def execute(self, command: str, params: Dict = None) -> DeviceResult:
        """Execute command on device"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check device health"""
        pass
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    @property
    def capabilities(self) -> list:
        return self.info.capabilities
```

### 3. ESP32 S3 Implementation

**Purpose:** Concrete implementation for your hardware.

```python
# devices/esp32/device.py

from ..base import BaseDevice, DeviceResult
from typing import Dict, Any
import asyncio

class ESP32Device(BaseDevice):
    """
    ESP32 S3 device (WiFi6 + BLE)
    
    Capabilities:
    - WiFi telemetry (signal strength, connection status)
    - BLE communication
    - Sensor readings (temperature, humidity, etc.)
    - GPIO control
    """
    
    async def connect(self) -> bool:
        """Connect to ESP32 via WiFi or BLE"""
        # Try WiFi first, fallback to BLE
        if "http" in self.info.protocols:
            # HTTP connection (already connected for REST API)
            if await self.health_check():
                self._connected = True
                return True
        
        # Try BLE if WiFi fails
        if "ble" in self.info.protocols:
            # BLE connection logic
            try:
                from .ble_client import BLEClient
                self.ble_client = BLEClient(self.info.address)
                await self.ble_client.connect()
                self._connected = True
                return True
            except Exception as e:
                self._connected = False
                return False
        
        return False
    
    async def disconnect(self) -> bool:
        """Disconnect from device"""
        self._connected = False
        return True
    
    async def read(self, attribute: str) -> DeviceResult:
        """
        Read attribute from ESP32
        
        Attributes:
        - telemetry (WiFi info, RSSI, etc.)
        - temperature
        - humidity
        - gpio_{N} (GPIO state)
        """
        if not self._connected:
            return DeviceResult(False, None, "Device not connected")
        
        try:
            if attribute == "telemetry":
                return await self._read_telemetry()
            elif attribute == "temperature":
                return await self._read_temperature()
            elif attribute.startswith("gpio_"):
                pin = attribute.split("_")[1]
                return await self._read_gpio(pin)
            else:
                return DeviceResult(False, None, f"Unknown attribute: {attribute}")
        except Exception as e:
            return DeviceResult(False, None, str(e))
    
    async def write(self, attribute: str, value: Any) -> DeviceResult:
        """Write attribute to device"""
        if not self._connected:
            return DeviceResult(False, None, "Device not connected")
        
        try:
            if attribute.startswith("gpio_"):
                pin = attribute.split("_")[1]
                return await self._write_gpio(pin, value)
            else:
                return DeviceResult(False, None, f"Read-only attribute: {attribute}")
        except Exception as e:
            return DeviceResult(False, None, str(e))
    
    async def execute(self, command: str, params: Dict = None) -> DeviceResult:
        """Execute command"""
        # For ESP32, most operations are read/write
        # Execute can be for firmware updates, restarts, etc.
        return DeviceResult(False, None, "No executable commands yet")
    
    async def health_check(self) -> bool:
        """Check if device is reachable"""
        try:
            from .wifi_client import WiFiClient
            client = WiFiClient(self.info.address)
            return await client.ping()
        except:
            return False
    
    # Internal methods
    
    async def _read_telemetry(self) -> DeviceResult:
        """Read WiFi telemetry"""
        from .wifi_client import WiFiClient
        client = WiFiClient(self.info.address)
        data = await client.get("/api/telemetry")
        
        return DeviceResult(
            success=True,
            data=data,
            metadata={"source": "wifi", "device": self.info.name}
        )
    
    async def _read_temperature(self) -> DeviceResult:
        """Read temperature sensor"""
        from .wifi_client import WiFiClient
        client = WiFiClient(self.info.address)
        data = await client.get("/api/sensors/temperature")
        
        return DeviceResult(
            success=True,
            data=data,
            metadata={"unit": "celsius"}
        )
    
    async def _read_gpio(self, pin: str) -> DeviceResult:
        """Read GPIO pin state"""
        from .wifi_client import WiFiClient
        client = WiFiClient(self.info.address)
        data = await client.get(f"/api/gpio/{pin}")
        
        return DeviceResult(
            success=True,
            data=data
        )
    
    async def _write_gpio(self, pin: str, value: int) -> DeviceResult:
        """Write GPIO pin state"""
        from .wifi_client import WiFiClient
        client = WiFiClient(self.info.address)
        data = await client.post(f"/api/gpio/{pin}", {"value": value})
        
        return DeviceResult(
            success=True,
            data=data
        )
```

### 4. WiFi Protocol Client

```python
# devices/esp32/wifi_client.py

import aiohttp
import asyncio
from typing import Dict, Any

class WiFiClient:
    """
    HTTP client for ESP32 WiFi API
    """
    
    def __init__(self, address: str, timeout: int = 5):
        self.base_url = f"http://{address}"
        self.timeout = timeout
        self._session = None
    
    async def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session
    
    async def get(self, endpoint: str) -> Dict[str, Any]:
        """GET request"""
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()
    
    async def post(self, endpoint: str, data: Dict) -> Dict[str, Any]:
        """POST request"""
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        
        async with session.post(url, json=data) as response:
            response.raise_for_status()
            return await response.json()
    
    async def ping(self) -> bool:
        """Check if device is reachable"""
        try:
            await self.get("/")
            return True
        except:
            return False
    
    async def close(self):
        """Close session"""
        if self._session:
            await self._session.close()
```

### 5. BLE Protocol Client (for ESP32 S3)

```python
# devices/esp32/ble_client.py

import asyncio
from typing import Optional

try:
    from bleak import BleakClient, BleakScanner
    BLE_AVAILABLE = True
except ImportError:
    BLE_AVAILABLE = False


class BLEClient:
    """
    BLE client for ESP32 S3
    
    Note: Requires 'bleak' library: pip install bleak
    """
    
    def __init__(self, address: str):
        if not BLE_AVAILABLE:
            raise ImportError("BLE requires 'bleak' library")
        
        self.address = address
        self._client: Optional[BleakClient] = None
    
    async def connect(self):
        """Connect to BLE device"""
        self._client = BleakClient(self.address)
        await self._client.connect()
    
    async def disconnect(self):
        """Disconnect"""
        if self._client:
            await self._client.disconnect()
    
    async def read_characteristic(self, uuid: str) -> bytes:
        """Read BLE characteristic"""
        if not self._client:
            raise RuntimeError("Not connected")
        
        return await self._client.read_gatt_char(uuid)
    
    async def write_characteristic(self, uuid: str, data: bytes):
        """Write BLE characteristic"""
        if not self._client:
            raise RuntimeError("Not connected")
        
        await self._client.write_gatt_char(uuid, data)
    
    @staticmethod
    async def scan(timeout: int = 5):
        """Scan for BLE devices"""
        devices = await BleakScanner.discover(timeout=timeout)
        return devices
```

### 6. Tool Framework

```python
# tools/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTool(ABC):
    """
    Abstract base class for all tools
    
    Tools are the interface between agent and capabilities
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description"""
        pass
    
    @abstractmethod
    def schema(self) -> dict:
        """OpenAI function schema"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute tool"""
        pass


# tools/device_tool.py

from .base import BaseTool
from ..devices.registry import DeviceRegistry

class DeviceTool(BaseTool):
    """Tool for interacting with devices"""
    
    def __init__(self, registry: DeviceRegistry):
        self.registry = registry
    
    @property
    def name(self) -> str:
        return "device_operation"
    
    @property
    def description(self) -> str:
        return "Read from, write to, or control a hardware device"
    
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device": {
                            "type": "string",
                            "description": "Device ID or name (e.g., 'esp-lab')"
                        },
                        "operation": {
                            "type": "string",
                            "enum": ["read", "write", "execute"],
                            "description": "Operation type"
                        },
                        "attribute": {
                            "type": "string",
                            "description": "Attribute to read/write (e.g., 'telemetry', 'temperature')"
                        },
                        "value": {
                            "type": "any",
                            "description": "Value to write (for write operations)"
                        }
                    },
                    "required": ["device", "operation"]
                }
            }
        }
    
    async def execute(self, device: str, operation: str, attribute: str = None, value = None) -> dict:
        """Execute device operation"""
        try:
            # Get device instance
            dev = self.registry.get_device(device)
            
            # Connect if needed
            if not dev.is_connected:
                await dev.connect()
            
            # Execute operation
            if operation == "read":
                result = await dev.read(attribute)
            elif operation == "write":
                result = await dev.write(attribute, value)
            elif operation == "execute":
                result = await dev.execute(attribute, {"value": value} if value else {})
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
            
            return {
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "metadata": result.metadata
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
```

### 7. Safety Engine

```python
# safety/engine.py

from typing import Dict, Any
from ..devices.registry import DeviceRegistry

class SafetyEngine:
    """
    Validate operations before execution
    
    For Hello Hardware, basic safety:
    - Is device registered/owned?
    - Is operation allowed?
    - Rate limiting
    """
    
    def __init__(self, registry: DeviceRegistry):
        self.registry = registry
        self.rate_limits: Dict[str, int] = {}
        self.max_requests_per_minute = 60
    
    def validate(self, device_id: str, operation: str, params: Dict) -> tuple[bool, str]:
        """
        Validate operation
        
        Returns: (is_safe, reason)
        """
        
        # Check device exists
        try:
            device = self.registry.devices.get(device_id)
            if not device:
                # Try to find by name
                for d in self.registry.devices.values():
                    if d.name == device_id:
                        device = d
                        break
            
            if not device:
                return False, f"Unknown device: {device_id}"
        except:
            return False, f"Device not found: {device_id}"
        
        # Check capability
        if operation == "read":
            if "read" not in device.capabilities and "*" not in device.capabilities:
                return False, f"Device does not support read"
        
        if operation == "write":
            if "write" not in device.capabilities and "*" not in device.capabilities:
                return False, f"Device does not support write"
        
        # Rate limiting
        import time
        current_time = time.time()
        key = f"{device_id}:{operation}"
        
        if key in self.rate_limits:
            if current_time - self.rate_limits[key] < 60 / self.max_requests_per_minute:
                return False, "Rate limit exceeded"
        
        self.rate_limits[key] = current_time
        
        return True, "OK"
```

---

## Configuration

### `.ade/config.yaml`

```yaml
# ADE Configuration

agent:
  model: "mistral-large"
  api_base: "http://localhost:11434/v1"
  context_window: 128000
  temperature: 0.7

devices:
  auto_discover: true
  discovery_range: "192.168.1.0/24"
  health_check_interval: 60  # seconds

safety:
  max_requests_per_minute: 60
  owned_networks:
    - "192.168.1.0/24"
  
logging:
  level: "INFO"
  file: ".ade/logs/ade.log"
```

### `.ade/devices.json` (auto-generated)

```json
{
  "devices": [
    {
      "id": "esp-s3-001",
      "name": "esp-lab",
      "device_type": "esp32",
      "protocols": ["http", "ble"],
      "address": "192.168.1.42",
      "capabilities": ["read", "write", "telemetry", "gpio"],
      "metadata": {
        "model": "ESP32-S3",
        "wifi6": true,
        "ble": true
      },
      "last_seen": "2026-10-02T10:00:00Z",
      "status": "online"
    }
  ]
}
```

---

## Implementation Steps

### Week 1: Foundation (Days 1-7)

#### Day 1: Setup
- [ ] Create directory structure
- [ ] Initialize package: `april_ade/`
- [ ] Create requirements.txt
- [ ] Setup .ade/ config directory

#### Day 2: Core Runtime
- [ ] Implement `AgentConfig`
- [ ] Implement `AgentRuntime` (minimal, no subagents yet)
- [ ] Implement basic tool execution
- [ ] Test LLM connection

#### Day 3: Tool Framework
- [ ] Implement `BaseTool` class
- [ ] Implement `ShellTool` (for testing)
- [ ] Implement tool registry
- [ ] Write tool tests

#### Day 4: Device Registry
- [ ] Implement `DeviceRegistry`
- [ ] Implement `DeviceInfo` dataclass
- [ ] Implement registry loading/saving
- [ ] Test registry operations

#### Day 5: Device Abstraction
- [ ] Implement `BaseDevice` class
- [ ] Define device interface
- [ ] Write device tests
- [ ] Test mock devices

#### Day 6-7: Integration
- [ ] Integrate all components
- [ ] Write integration tests
- [ ] Test agent → tool → registry flow
- [ ] Debug and fix

---

### Week 2: ESP32 Integration (Days 8-14)

#### Day 8: WiFi Client
- [ ] Implement `WiFiClient`
- [ ] Implement HTTP GET/POST
- [ ] Implement ping/health check
- [ ] Test with mock server

#### Day 9: ESP32 Device
- [ ] Implement `ESP32Device`
- [ ] Implement connect/disconnect
- [ ] Implement read operations
- [ ] Test device logic

#### Day 10: Device Tool
- [ ] Implement `DeviceTool`
- [ ] Register tool with agent
- [ ] Test device operations from agent
- [ ] Debug tool execution

#### Day 11: BLE Client (Optional)
- [ ] Install `bleak` library
- [ ] Implement `BLEClient`
- [ ] Test BLE scanning
- [ ] Test BLE connection

#### Day 12: Safety Engine
- [ ] Implement `SafetyEngine`
- [ ] Add device ownership check
- [ ] Add rate limiting
- [ ] Test safety validation

#### Day 13: Discovery
- [ ] Implement network discovery
- [ ] Scan for ESP32 devices
- [ ] Auto-register discovered devices
- [ ] Test discovery

#### Day 14: Integration Test
- [ ] End-to-end test: Agent reads from ESP32
- [ ] Fix bugs
- [ ] Polish code
- [ ] Document API

---

### Week 3: Hello Hardware Milestone (Days 15-21)

#### Day 15: CLI Interface
- [ ] Implement `AprilCLI`
- [ ] Rich terminal output
- [ ] Command history
- [ ] Error handling

#### Day 16: Configuration
- [ ] Implement YAML config loading
- [ ] Implement .env loading
- [ ] Test config management
- [ ] Document config options

#### Day 17: Your ESP32 Setup
- [ ] Flash your ESP32 S3 with firmware
- [ ] Configure WiFi credentials
- [ ] Test HTTP API endpoints
- [ ] Register device in ADE

#### Day 18: Testing
- [ ] **THE BIG TEST: Agent reads from your physical ESP32**
- [ ] Test WiFi telemetry
- [ ] Test temperature/sensors
- [ ] Test GPIO (if applicable)

#### Day 19: Polish
- [ ] Add logging
- [ ] Improve error messages
- [ ] Add retry logic
- [ ] Optimize performance

#### Day 20: Documentation
- [ ] Write README
- [ ] Document device API
- [ ] Write troubleshooting guide
- [ ] Add examples

#### Day 21: Demo
- [ ] Record demo of Hello Hardware
- [ ] Take screenshots
- [ ] Write blog/documentation
- [ ] Celebrate 🎉

---

## ESP32 Firmware Requirements

Your ESP32 S3 needs to run a minimal HTTP server that exposes:

### Endpoints:

```
GET /                          # Health check
GET /api/telemetry             # WiFi telemetry
GET /api/sensors/temperature   # Temperature
GET /api/sensors/humidity      # Humidity
GET /api/gpio/{pin}            # GPIO state
POST /api/gpio/{pin}           # Set GPIO state
```

### Example Telemetry Response:

```json
{
  "wifi": {
    "ssid": "LabNetwork",
    "rssi": -42,
    "channel": 6,
    "ip": "192.168.1.42"
  },
  "uptime": 3600,
  "free_heap": 120000
}
```

---

## Success Criteria

### Hello Hardware is complete when:

**Functional:**
- [ ] Agent can read telemetry from your physical ESP32 S3
- [ ] Agent understands device operations
- [ ] Safety validation works
- [ ] Device registry persists across restarts

**Technical:**
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Manual test successful
- [ ] Code documented

**The Test:**
```bash
aprils chat
> What's the WiFi signal strength on my ESP32?
[Calling device_operation(device='esp-lab', operation='read', attribute='telemetry')]
[ESP32 S3] RSSI: -42 dBm, Connected to LabNetwork
Signal strength is -42 dBm, which is excellent (closer to 0 is better)
```

---

## Extensibility for Future Hardware

### Adding New Devices:

1. **Create device class** (inherits from `BaseDevice`):
   ```python
   # devices/camera/device.py
   class CameraDevice(BaseDevice):
       async def read(self, attribute: str):
           if attribute == "snapshot":
               return await self._capture_image()
           # ...
   ```

2. **Register in registry**:
   ```python
   registry._device_classes["camera"] = CameraDevice
   ```

3. **Add protocol clients** (if needed):
   ```python
   # protocols/rtsp.py
   class RTSPClient:
       # ...
   ```

4. **Agent can now use it**:
   ```bash
   > Take a photo from camera-gate
   [device_operation(device='camera-gate', operation='read', attribute='snapshot')]
   ```

### Adding Complex Protocols:

For robots, machines, industrial hardware:

```python
# protocols/modbus.py
class ModbusClient:
    """Industrial Modbus protocol"""
    # ...

# protocols/can_bus.py  
class CANBusClient:
    """CAN bus for automotive/robotics"""
    # ...

# protocols/ethercat.py
class EtherCATClient:
    """Industrial Ethernet"""
    # ...
```

---

## Test Plan

### Unit Tests:
- [ ] Device registry operations
- [ ] Device abstraction
- [ ] Tool execution
- [ ] Safety validation

### Integration Tests:
- [ ] Agent → Tool → Device flow
- [ ] WiFi client operations
- [ ] BLE client operations (if implemented)

### Manual Tests:
- [ ] Agent reads from ESP32
- [ ] Agent writes to ESP32 (GPIO)
- [ ] Device discovery
- [ ] Error recovery

---

## Dependencies

```txt
# requirements.txt

# Core
openai>=1.0.0
python-dotenv>=1.0.0
pyyaml>=6.0
aiohttp>=3.9.0
asyncio>=3.4.3

# CLI
prompt-toolkit>=3.0.0
rich>=13.0.0

# BLE (optional)
bleak>=0.21.0

# Testing
pytest>=7.0.0
pytest-asyncio>=0.21.0
```

---

## Timeline

```
Week 1: Foundation
├─ Day 1:   Setup
├─ Day 2:   Runtime
├─ Day 3:   Tools
├─ Day 4:   Registry
├─ Day 5:   Devices
└─ Day 6-7: Integration

Week 2: ESP32
├─ Day 8:   WiFi Client
├─ Day 9:   ESP32 Device
├─ Day 10:  Device Tool
├─ Day 11:  BLE Client
├─ Day 12:  Safety
├─ Day 13:  Discovery
└─ Day 14:  Integration

Week 3: Hello Hardware
├─ Day 15:  CLI
├─ Day 16:  Config
├─ Day 17:  Setup ESP32
├─ Day 18:  THE TEST 🎯
├─ Day 19:  Polish
├─ Day 20:  Docs
└─ Day 21:  Demo
```

---

## What This Enables

### After Hello Hardware, you can:

1. **Add cameras** (same pattern)
2. **Add robots** (inherit BaseDevice, add protocols)
3. **Add machines** (Modbus, EtherCAT, etc.)
4. **Build skills** (domain knowledge for specific hardware)
5. **Add subagents** (specialized AI for complex hardware)
6. **Scale to production** (monitoring, persistence, optimization)

---

## Next Actions

1. **Review this plan** - Does the architecture make sense?
2. **Setup ESP32 firmware** - What endpoints does it need?
3. **Start Week 1** - Begin with foundation
4. **Test early** - Get to Hello Hardware ASAP
5. **Iterate** - Add features based on real usage

---

**Ready to build Hello Hardware? 🚀**
