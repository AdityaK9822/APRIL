# APRIL ADE Architecture

**Agent Development Environment for an embodied AI system**

---

## Overview

The ADE is the development, testing, and operational environment for APRIL. It provides the infrastructure to build, configure, test, deploy, and monitor the agent system and its interactions with the physical world.

**Core principle:** The ADE must itself be an APRIL agent - everything APRIL can do, the ADE can observe, test, and debug. The development environment is not separate from the runtime; it wraps it.

---

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACES                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  CLI     │  │  GUI     │  │  Voice   │  │  API     │   │
│  │  Studio  │  │  Monitor │  │  Control │  │  Client  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                       │
│                                                              │
│    ┌─────────────────────────────────────────────────┐      │
│    │            PROJECT MANAGER                        │      │
│    │  • Goal decomposition  • State transitions       │      │
│    │  • Artifact tracking  • Device reservations      │      │
│    └─────────────────────────────────────────────────┘      │
│                            │                                 │
│                            ▼                                 │
│    ┌─────────────────────────────────────────────────┐      │
│    │            SESSION RUNTIME                        │      │
│    │  • Conversation context  • Agent execution loop   │      │
│    │  • Message history     • Subagent dispatch       │      │
│    └─────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    AGENT FRAMEWORK                           │
│                                                              │
│    ┌──────────────┐      ┌──────────────┐                  │
│    │  CORE AGENT  │◄────►│ SUBAGENTS    │                  │
│    │  (APRIL)     │      │              │                  │
│    │              │      │ • Vision     │                  │
│    │ • Converses  │      │ • Fabrication│                  │
│    │ • Plans      │      │ • Network    │                  │
│    │ • Dispatches │      │ • Robotics   │                  │
│    │ • Reviews    │      │ • etc.       │                  │
│    └──────────────┘      └──────────────┘                  │
│            │                      │                         │
│            ▼                      ▼                         │
│    ┌──────────────────────────────────────────────┐         │
│    │          SKILL LIBRARY                        │         │
│    │  • Domain knowledge  • Tool usage patterns    │         │
│    │  • Safety constraints  • Quality standards   │         │
│    └──────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    TOOL LAYER                                │
│                                                              │
│    ┌─────────────────────────────────────────────────┐      │
│    │            TOOL FRAMEWORK                         │      │
│    │  • Tool registry  • Execution wrappers           │      │
│    │  • Input/output  • Error handling                │      │
│    └─────────────────────────────────────────────────┘      │
│                            │                                 │
│    ┌─────────┬─────────────┼──────────────┬────────────┐    │
│    ▼         ▼             ▼              ▼            ▼    │
│ ┌──────┐ ┌──────┐   ┌──────────┐   ┌───────┐   ┌────────┐  │
│ │SHELL │ │FILES │   │SOFTWARE  │   │DEVICE │   │NETWORK │  │
│ │      │ │      │   │APPS      │   │DRIVERS│   │TOOLS   │  │
│ │exec  │ │read/ │   │          │   │       │   │        │  │
│ │cmd   │ │write │   │• CAD     │   │• ESP  │   │• wifi  │  │
│ │      │ │      │   │• EDA     │   │• cam  │   │• audit │  │
│ │      │ │      │   │• Slicer  │   │• MCU  │   │• scan  │  │
│ └──────┘ └──────┘   └──────────┘   └───────┘   └────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    BODY REGISTRY                            │
│                                                              │
│    ┌─────────────────────────────────────────────────┐      │
│    │        DEVICE REGISTRY                            │      │
│    │  • Named limbs  • Capabilities  • Liveness       │      │
│    │  • Risk levels  • Reachability  • Metadata       │      │
│    └─────────────────────────────────────────────────┘      │
│                                                              │
│    Limb domains:                                            │
│    ┌─────────────┬─────────────┬─────────────────────┐      │
│    │ Vision      │ Sensing     │ Home/Appliances      │      │
│    │ Cameras     │ ECG/EEG     │ Lights, AC, Plugs   │      │
│    ├─────────────┼─────────────┼─────────────────────┤      │
│    │ Robotics    │ Network     │ Fabrication         │      │
│    │ Arms, MCU   │ Wifi audit  │ Printer, CNC        │      │
│    └─────────────┴─────────────┴─────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    SAFETY ENGINE                            │
│                                                              │
│    Three axes of enforcement:                               │
│                                                              │
│    ┌──────────────┐  ┌───────────────┐  ┌──────────────┐   │
│    │  PHYSICAL    │  │   NETWORK     │  │    DATA      │   │
│    │  RISK        │  │   AUTH        │  │  SENSITIVITY  │   │
│    │              │  │               │  │              │   │
│    │ Per-device   │  │ Hard line:    │  │ Reads carry  │   │
│    │ risk levels  │  │ own networks  │  │ weight even  │   │
│    │ → more checks│  │ or explicit   │  │ when nothing │   │
│    │ before act   │  │ authorization  │  │ moves        │   │
│    └──────────────┘  └───────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    PERSISTENCE LAYER                        │
│                                                              │
│    ┌──────────────┐  ┌───────────────┐  ┌──────────────┐   │
│    │  SESSION     │  │   PROJECT     │  │   SKILL      │   │
│    │  MEMORY      │  │   STATE       │  │   LIBRARY    │   │
│    │              │  │               │  │              │   │
│    │ Conversation │  │ Goal, plan    │  │ Skills,      │   │
│    │ history,     │  │ artifacts,    │  │ integrations,│   │
│    │ context      │  │ devices       │  │ metadata     │   │
│    └──────────────┘  └───────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### 1. Orchestration Layer

**Project Manager**
- **Goal decomposition**: Parse user intent into structured plan
- **Artifact tracking**: Files, models, gerbers, gcode, firmware produced
- **State machine**: `pending → running → blocked → failed → done`
- **Device reservations**: Claim devices for project duration
- **Persistence**: Survive restart, resume work

**Session Runtime**
- **Execution loop**: Agent → analyze → tool call → observe → iterate
- **Subagent dispatch**: Route tasks to specialized agents
- **Context window**: Conversation history + ephemeral state
- **Cancellation**: Graceful Ctrl-C handling

### 2. Agent Framework

**Core Agent (APRIL)**
- **Converses**: Natural language interface
- **Plans**: Decompose goals into tasks
- **Dispatches**: Route to subagents with skills
- **Reviews**: Inspect subagent output before it takes effect
- **Model routing**: Choose reasoning/code/vision models per task

**Subagents**
- **Specialized**: One domain per subagent
- **Skill-equipped**: Pull relevant skills from library
- **Model-specific**: Declare model needs (reasoning vs vision vs code)
- **Isolated**: Own execution context, report back results

**Skill Library**
- **Domain knowledge**: How to use a tool well
- **Tool patterns**: Valid input/output schemas
- **Safety constraints**: What not to do with this tool
- **Quality standards**: How to recognize good output

### 3. Tool Layer

**Tool Framework**
- **Registration**: Dynamic tool loading
- **Wrappers**: Execution with logging, timeout, error capture
- **Validation**: Input schema checking
- **Output parsing**: Structured results or error objects

**Tool Categories**

**Machine Tools** (Pillar 1)
- Shell command execution
- Filesystem read/write
- Process management
- System state queries

**Software Tools** (Pillar 2)
- CAD application control (FreeCAD, Fusion 360)
- EDA tools (KiCad, Altium)
- Slicers (Cura, PrusaSlicer)
- Vision models (object detection, description)
- Network tools (nmap, wireshark, aircrack-ng)

**Device Tools** (Pillar 3)
- ESP32 communication (HTTP, MQTT, serial)
- Camera streaming (RTSP, HTTP)
- Appliance control (WiFi plugs, HomeKit)
- Robot drivers (ROS, custom protocols)
- Machine control (Gcode, CNC protocols)

### 4. Body Registry

**Device Model**
```python
class Device:
    name: str              # e.g., "camera-gate", "cnc-main"
    domain: Domain         # vision, sensing, home, robotics, network, fabrication
    capabilities: list     # what it can do
    risk_level: Risk      # low, medium, high, critical
    status: Status        # online, offline, busy, faulted
    endpoint: Endpoint    # how to reach it
    metadata: dict        # make, model, firmware, last_seen
```

**Registry Operations**
- **Discovery**: Auto-detect devices on network
- **Liveness**: Heartbeat checks, status updates
- **Capability queries**: "What can see right now?"
- **Reservation**: Claim device for project

### 5. Safety Engine

**Physical Risk Enforcement**
```python
class PhysicalSafety:
    # Per-device risk levels
    LOW       = auto-approve      # LED blink, file read
    MEDIUM    = log + proceed     # WiFi plug toggle
    HIGH      = prompt user       # Robot arm move, 3D print start
    CRITICAL  = require + confirm # CNC spindle, laser cutter
```

**Network Authorization**
```python
class NetworkSafety:
    # Hard line enforcement
    OWNED_NETWORKS      = Set[Network]  # configured in .env
    AUTHORIZED_NETWORKS = Set[Network]  # explicit allowlist
    
    def check_network_action(target: Network):
        if target not in OWNED_NETWORKS | AUTHORIZED_NETWORKS:
            raise UnauthorizedNetworkError(target)
```

**Data Sensitivity**
```python
class DataSafety:
    # Reading is not always harmless
    SENSITIVE_LIMBS = {
        "camera-home":    PrivacyLevel.HOME,
        "ecg-medical":    PrivacyLevel.MEDICAL,
        " microphone-room": PrivacyLevel.PRIVATE,
    }
    
    # Data stays on machine
    LOCAL_ONLY = True  # no cloud upload
    ENCRYPT_AT_REST = True
```

### 6. Persistence Layer

**Session Memory** (ephemeral)
- Conversation turns
- Tool call history
- Reasoning traces
- Cancellation status

**Project State** (durable)
- Goal statement
- Plan (steps, subagents, devices)
- Artifacts (files, models, configs)
- Timeline (events, milestones, failures)

**Skill Library** (versioned)
- Skill definitions (markdown + metadata)
- Integration code
- Test suites
- Version history

---

## Data Flow: Request to Physical Result

```
User Request: "Print a bracket that holds this board at 30°"
         │
         ▼
┌─────────────────────────────────────┐
│ 1. PROJECT MANAGER                   │
│    • Create project                  │
│    • Parse goal                      │
│    • Check device availability       │
│      (3D printer online?)            │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 2. APRIL (CORE AGENT)                │
│    • Decompose into tasks:           │
│      - Design in CAD                 │
│      - Validate model                │
│      - Slice for printer             │
│      - Execute print                 │
│    • Assign subagents                │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 3. SUBAGENT: CAD Designer            │
│    • Load skill: "bracket-design"    │
│    • Tool: FreeCAD API               │
│    • Generate 3D model              │
│    • Return: bracket.step file       │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 4. APRIL REVIEW                      │
│    • Inspect model geometry           │
│    • Verify angle specification       │
│    • Approve or request changes       │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 5. SUBAGENT: Slicer                  │
│    • Load skill: "fdm-slicing"       │
│    • Tool: PrusaSlicer CLI           │
│    • Generate gcode                  │
│    • Return: bracket.gcode           │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 6. SAFETY ENGINE                      │
│    • Device: 3D printer               │
│    • Risk: HIGH                       │
│    • Action: Prompt user "Start print?"│
│    • Confirmation required            │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 7. SUBAGENT: Printer Controller      │
│    • Load skill: "fdm-printing"      │
│    • Tool: OctoPrint API              │
│    • Upload gcode                     │
│    • Start print job                  │
│    • Monitor progress                 │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 8. PROJECT MANAGER                    │
│    • Update project status: done      │
│    • Store artifact: bracket.step     │
│    • Release device reservation        │
│    • Notify user: "Ready to collect"  │
└─────────────────────────────────────┘
```

---

## Development Environment Features

### 1. Agent Studio (CLI + GUI)

**Agent Configurator**
```bash
aprils-ade config agent april \
  --model mistral-large \
  --subagent vision:llava \
  --subagent code:codellama \
  --context-window 128k
```

**Skill Editor**
```bash
aprils-ade skill create esp32-telemetry \
  --domain sensing \
  --tools esp-http-client \
  --risk low \
  --template skill.md
```

**Device Registry CLI**
```bash
aprils-ade device register camera-gate \
  --domain vision \
  --endpoint rtsp://192.168.1.100:554 \
  --capability "see,pan,tilt" \
  --risk medium

aprils-ade device list
aprils-ade device status camera-gate
```

### 2. Testing & Debugging

**Tool Sandbox**
```bash
aprils-ade test tool octoprint \
  --mock-device \
  --input test.gcode \
  --trace
```

**Device Simulator**
```python
# Mock ESP32 for development
ade.testing.simulate_device(
    name="esp-test",
    domain="sensing",
    capabilities=["read_temperature", "read_humidity"],
    mock_responses={
        "/temperature": "22.5°C",
        "/humidity": "45%"
    }
)
```

**Scenario Runner**
```python
# Integration test: bracket design-to-print
ade.testing.run_scenario(
    request="print bracket 30°",
    mock_devices=["3d-printer", "cnc"],
    verify_artifacts=["bracket.step", "bracket.gcode"],
    timeout=300
)
```

### 3. Monitoring & Debugging

**Real-time Agent Monitor**
```bash
aprils-ade monitor april

┌─ APRIL Session #42 ─────────────────────────┐
│ Status: running                               │
│ Project: "print bracket"                      │
│ Active subagent: CAD Designer                 │
│ Tool: FreeCAD.API.Fusion.MakeBottle          │
│ Last msg: "Generating revolution..."         │
│ Tokens used: 12,450                          │
│ Runtime: 2m 34s                               │
└──────────────────────────────────────────────┘
```

**Execution Trace**
```python
ade.monitor.trace(project_id)

[
    {
        "timestamp": "2026-09-27T10:23:45Z",
        "agent": "APRIL",
        "action": "dispatch",
        "subagent": "CAD Designer",
        "reasoning": "First step: design the bracket geometry"
    },
    {
        "timestamp": "2026-09-27T10:24:12Z",
        "agent": "CAD Designer",
        "action": "tool_call",
        "tool": "freecad.newDocument",
        "input": {"name": "bracket"},
        "output": {"doc_id": "bracket_001"}
    },
    # ... full execution history
]
```

**Device Health Dashboard**
```bash
aprils-ade devices status

┌─ BODY REGISTRY ─────────────────────────────┐
│ Device          │ Status │ Risk │ Last seen│
├─────────────────┼────────┼──────┼──────────┤
│ camera-gate     │ online │ med  │ 2s ago  │
│ esp-lab         │ online │ low  │ 5s ago  │
│ printer-3d      │ online │ high │ 1s ago  │
│ cnc-main        │ offline│ crit │ 2h ago  │
│ robot-arm       │ busy   │ high │ 0s ago  │
└──────────────────────────────────────────────┘
```

---

## Extension Points

### 1. Adding New Tools

```python
# tools/network/wifi_scanner.py
from april.tool_framework import Tool, ToolMetadata

class WifiScanner(Tool):
    metadata = ToolMetadata(
        name="wifi_scanner",
        domain="network",
        risk_level="medium",
        description="Scan for wifi networks (authorized networks only)"
    )
    
    def execute(self, interface: str = "wlan0") -> dict:
        # Validate network authorization
        self.safety.check_network_authorization()
        
        # Run scan
        result = subprocess.run(
            ["iwlist", interface, "scan"],
            capture_output=True, text=True
        )
        
        return self.parse_results(result.stdout)
```

**Registration:**
```bash
aprils-ade tool register wifi_scanner \
  --path tools/network/wifi_scanner.py \
  --enable
```

### 2. Adding New Skills

```markdown
<!-- skills/network/wifi-audit.md -->
# WiFi Network Audit Skill

## Purpose
Perform a security audit of a wifi network you own.

## Authorization Required
- Network must be in OWNED_NETWORKS or AUTHORIZED_NETWORKS
- User must confirm audit intent

## Tools Used
- `wifi_scanner`: Detect networks
- `nmap`: Port scan devices
- `aircrack-ng`: Test encryption (authorization required)

## Workflow
1. **Discovery**: Scan for all connected devices
2. **Vulnerability scan**: Check open ports, weak encryption
3. **Report**: Generate findings in markdown

## Safety Constraints
- Never run on networks you don't own
- Never exploit vulnerabilities, only detect
- Never capture traffic without consent

## Success Criteria
- All devices listed
- Open ports documented
- Recommendations provided
```

### 3. Adding New Devices

```python
# devices/esp_robot_arm.py
from april.device_registry import Device, Domain, Risk

class RobotArm(Device):
    name = "robot-arm-main"
    domain = Domain.ROBOTICS
    risk_level = Risk.HIGH
    endpoint = "http://192.168.1.150"
    
    capabilities = [
        "move_to_position",
        "gripper_open",
        "gripper_close",
        "get_position"
    ]
    
    def health_check(self) -> bool:
        response = requests.get(f"{self.endpoint}/health")
        return response.status_code == 200
```

---

## Configuration

### ADE Configuration (`.ade/config.yaml`)

```yaml
# Core agent configuration
agent:
  name: APRIL
  model: mistral-large
  context_window: 128000
  temperature: 0.7
  
# Subagent definitions
subagents:
  - name: vision
    model: llava
    skills: [camera-control, object-detection]
    
  - name: fabrication
    model: codellama
    skills: [cad-design, 3d-printing, cnc-milling]
    
  - name: network
    model: mistral-medium
    skills: [wifi-audit, device-discovery]

# Device registry paths
devices:
  registry_path: .ade/devices
  auto_discover: true
  scan_interval: 30  # seconds
  
# Skill library
skills:
  library_path: .ade/skills
  hot_reload: true
  
# Safety configuration
safety:
  owned_networks:
    - 192.168.1.0/24
    - 10.0.0.0/8
  authorized_networks_path: .ade/authorized_networks.txt
  
  risk_thresholds:
    low: auto
    medium: log
    high: prompt
    critical: require_confirm
    
# Persistence
persistence:
  projects_path: .ade/projects
  sessions_path: .ade/sessions
  artifacts_path: .ade/artifacts
  
# Model providers
providers:
  local:
    base_url: http://localhost:11434
    api_key: ollama
    
  cloud:
    base_url: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}
```

### Environment Variables (`.env`)

```bash
# Required
OPENAI_API_KEY=your-key-here
OPENAI_API_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=mistral-large

# Optional
ADE_LOG_LEVEL=INFO
ADE_CONFIG_PATH=.ade/config.yaml
ADE_SAFE_MODE=false
```

---

## Implementation Priorities

### Phase 1: Core Runtime (Week 1-2)
- [ ] Minimal agent loop (talk + tool call)
- [ ] Basic tool framework
- [ ] Session memory (ephemeral)
- [ ] Safety engine (stub)

### Phase 2: Tools & Skills (Week 3-4)
- [ ] Shell tool (command execution)
- [ ] File tool (read/write)
- [ ] Skill library structure
- [ ] First skill: "shell-command"

### Phase 3: Device Integration (Week 5-6)
- [ ] Device registry
- [ ] ESP32 HTTP client tool
- [ ] First device: ESP32 telemetry
- [ ] Safety enforcement (physical risk)

### Phase 4: Projects & Persistence (Week 7-8)
- [ ] Project manager
- [ ] Artifact storage
- [ ] Durable state
- [ ] Resume after restart

### Phase 5: Subagents (Week 9-10)
- [ ] Subagent dispatch
- [ ] Model routing
- [ ] Vision subagent
- [ ] First camera integration

### Phase 6: Monitoring & ADE Tooling (Week 11-12)
- [ ] CLI studio tools
- [ ] Execution traces
- [ ] Device dashboard
- [ ] Testing sandbox

---

## Key Design Principles

1. **Laziest solution that works** - Minimal dependencies, stdlib-first
2. **Full system access** - No sandbox on execution, safety on physical devices
3. **The ADE is an agent** - Everything observable via agent tools
4. **Local-first** - Data stays on machine, cloud optional
5. **Hot-reload** - Edit skills without restart
6. **Test before physical** - Mock devices, simulate before acting
7. **Trace everything** - Every tool call, reasoning step, device action logged

---

## Next Steps

1. **Review this architecture** - Does this match APRIL's vision?
2. **Prioritize components** - Which layer to build first?
3. **Define interfaces** - Exact API contracts between layers
4. **Build minimal prototype** - Core agent + one tool + one device
5. **Iterate** - Add components based on real usage

---

**This architecture provides a complete development environment for building, testing, and operating APRIL as an embodied AI system.**
