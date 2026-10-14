# APRIL ADE: Architecture Review & Build Plan

**Summary of Agent Development Environment design**

---

## What We Designed

### 📋 **Two Architecture Documents Created:**

1. **[ADE-ARCHITECTURE.md](ADE-ARCHITECTURE.md)** - Complete system design
   - Layered architecture (7 layers)
   - Component responsibilities
   - Data flow: Request → Physical Result
   - Development environment features
   - Extension points
   - Configuration schema

2. **[ADE-IMPLEMENTATION-GUIDE.md](ADE-IMPLEMENTATION-GUIDE.md)** - Concrete code patterns
   - Working code examples for all core components
   - Tool framework with registry pattern
   - Device registry with auto-discovery
   - Safety engine with multi-axis enforcement
   - Project manager with persistence
   - Skill library with hot-reload
   - Testing utilities and mocks
   - Configuration loader

---

## Architecture Highlights

### 🏗️ **Layered Design**

```
User Interfaces (CLI/GUI/Voice/API)
        ↓
Orchestration (Project Manager + Session Runtime)
        ↓
Agent Framework (APRIL + Subagents + Skills)
        ↓
Tool Layer (Shell, Files, Software, Devices, Network)
        ↓
Body Registry (Named Limbs: Cameras, Sensors, Robots, Machines)
        ↓
Safety Engine (Physical Risk + Network Auth + Data Sensitivity)
        ↓
Persistence (Session Memory + Project State + Skill Library)
```

### 🎯 **Key Components**

| Component | Purpose | Status |
|-----------|---------|--------|
| **Agent Runtime** | Execute agent loop with tools | ✅ Designed |
| **Tool Framework** | Register and execute tools | ✅ Designed |
| **Device Registry** | Manage "body" (limbs) | ✅ Designed |
| **Safety Engine** | Enforce 3-axis policies | ✅ Designed |
| **Project Manager** | Track long-lived projects | ✅ Designed |
| **Skill Library** | Domain knowledge repository | ✅ Designed |
| **Testing Utils** | Mocks, integration tests | ✅ Designed |
| **CLI Studio** | Configuration + monitoring tools | 📝 Architecture only |

---

## Implementation Roadmap

### 🚀 **Phase 1: Core Runtime (Week 1-2)**

**Goal:** Get APRIL talking to an LLM and executing basic tools

**Build:**
- [ ] AgentRuntime class (from implementation guide)
- [ ] Basic Tool framework
- [ ] ShellTool
- [ ] FileReadTool, FileWriteTool
- [ ] Tool registry
- [ ] Session memory (ephemeral, dict-based)
- [ ] Minimal CLI: `aprils-ade chat`

**Test:**
```bash
aprils-ade chat
> List files in current directory
[APRIL executes: ls -la]
> Read README.md
[APRIL reads file]
```

**Success criteria:** APRIL can converse and use shell/file tools

---

### 🔧 **Phase 2: Tools & Skills (Week 3-4)**

**Goal:** Establish skill pattern, add first real integration

**Build:**
- [ ] Skill library structure
- [ ] Skill loading from markdown
- [ ] First skill: "shell-commands"
- [ ] File editing tools
- [ ] Process management tools
- [ ] Tool input validation

**Test:**
```bash
aprils-ade skill create shell-commands
aprils-ade test skill shell-commands
```

**Success criteria:** APRIL uses skills to guide tool usage

---

### 📡 **Phase 3: Device Integration (Week 5-6)**

**Goal:** First real device: ESP32 telemetry sensor

**Build:**
- [ ] Device registry manager
- [ ] Device auto-discovery (network scan)
- [ ] Health check loop (async)
- [ ] ESP32 HTTP client tool
- [ ] First skill: "esp32-telemetry"
- [ ] Safety engine (physical risk axis only)

**Test:**
```bash
aprils-ade device scan
aprils-ade device list
aprils-ade device health esp-lab

aprils-ade chat
> Read temperature from esp-lab
[APRIL calls ESP32 tool, returns 22.5°C]
```

**Success criteria:** APRIL reads from real ESP32 sensor

---

### 🛡️ **Phase 4: Safety Engine (Week 7)**

**Goal:** Full 3-axis safety enforcement

**Build:**
- [ ] Physical risk enforcement (low/medium/high/critical)
- [ ] Network authorization (owned/authorized networks)
- [ ] Data sensitivity (privacy levels)
- [ ] User prompts for high-risk actions
- [ ] Safety policy configuration

**Test:**
```bash
aprils-ade config safety \
  --owned-network 192.168.1.0/24

aprils-ade chat
> Scan wifi networks
[SAFETY: Authorized networks only]
> Audit my network
[SAFETY: Own network, proceed]
```

**Success criteria:** Safety engine blocks unauthorized actions

---

### 🗂️ **Phase 5: Project Persistence (Week 8-9)**

**Goal:** Projects survive restarts

**Build:**
- [ ] Project manager
- [ ] State persistence (JSON)
- [ ] Artifact storage
- [ ] Device reservations
- [ ] Resume after restart
- [ ] Project status tracking

**Test:**
```bash
aprils-ade project create "Print bracket"
aprils-ade project list
aprils-ade project resume <id>
```

**Success criteria:** Multi-step projects persist across sessions

---

### 🤖 **Phase 6: Subagents (Week 10-11)**

**Goal:** Dispatch to specialized agents

**Build:**
- [ ] Subagent dispatch framework
- [ ] Model routing (reasoning vs vision vs code)
- [ ] Vision subagent (camera integration)
- [ ] First camera tool
- [ ] Skill: "camera-control"

**Test:**
```bash
aprils-ade chat
> What's happening at the gate?
[APRIL dispatches to vision subagent]
[Subagent calls camera tool, describes scene]
```

**Success criteria:** APRIL dispatches tasks to subagents

---

### 🖥️ **Phase 7: ADE Tooling (Week 12)**

**Goal:** Developer experience

**Build:**
- [ ] CLI studio tools
- [ ] Real-time monitoring
- [ ] Execution traces
- [ ] Device health dashboard
- [ ] Testing sandbox
- [ ] Mock device library

**Test:**
```bash
aprils-ade monitor
aprils-ade test scenario "Read temperature"
aprils-ade simulate device esp-mock
```

**Success criteria:** Complete development environment

---

## Directory Structure

```
/Users/aditya/Coding/April/Open_INT/
├── CLAUDE.md                          # ✅ APRIL vision doc
├── docs/
│   ├── ADE-ARCHITECTURE.md            # ✅ Architecture design
│   ├── ADE-IMPLEMENTATION-GUIDE.md    # ✅ Code patterns
│   └── ADE-ROADMAP.md                 # ✅ This file
│
├── aprils_ade/                        # 📦 ADE package
│   ├── core/
│   │   ├── agent_runtime.py           # ❌ Build in Phase 1
│   │   ├── tool_framework.py          # ❌ Build in Phase 1
│   │   ├── device_registry.py         # ❌ Build in Phase 3
│   │   ├── safety_engine.py           # ❌ Build in Phase 3
│   │   ├── project_manager.py         # ❌ Build in Phase 5
│   │   └── skill_library.py           # ❌ Build in Phase 2
│   │
│   ├── tools/
│   │   ├── machine/
│   │   │   ├── shell.py               # ❌ Build in Phase 1
│   │   │   ├── file_io.py             # ❌ Build in Phase 1
│   │   │   └── process.py             # ❌ Build in Phase 2
│   │   │
│   │   ├── devices/
│   │   │   ├── esp32_http.py          # ❌ Build in Phase 3
│   │   │   └── camera.py              # ❌ Build in Phase 6
│   │   │
│   │   └── network/
│   │       └── wifi_scanner.py        # ❌ Build in Phase 4
│   │
│   ├── skills/
│   │   ├── shell-commands/            # ❌ Build in Phase 2
│   │   │   ├── metadata.yaml
│   │   │   └── instructions.md
│   │   │
│   │   ├── esp32-telemetry/           # ❌ Build in Phase 3
│   │   │   ├── metadata.yaml
│   │   │   └── instructions.md
│   │   │
│   │   └── camera-control/            # ❌ Build in Phase 6
│   │       ├── metadata.yaml
│   │       └── instructions.md
│   │
│   ├── testing/
│   │   ├── mock_devices.py            # ❌ Build in Phase 7
│   │   └── scenario_runner.py         # ❌ Build in Phase 7
│   │
│   └── cli/
│       ├── __init__.py
│       ├── main.py                    # ❌ Build in Phase 1
│       └── commands/
│           ├── chat.py                # ❌ Build in Phase 1
│           ├── config.py              # ❌ Build in Phase 4
│           ├── device.py              # ❌ Build in Phase 3
│           ├── skill.py               # ❌ Build in Phase 2
│           ├── project.py             # ❌ Build in Phase 5
│           └── monitor.py             # ❌ Build in Phase 7
│
├── .ade/                              # ADE runtime directory
│   ├── config.yaml                    # ✅ Architecture defines schema
│   ├── devices/                       # Device definitions
│   ├── skills/                        # Skill library
│   ├── projects/                      # Project state
│   └── artifacts/                     # Generated files
│
├── requirements.txt                   # ✅ Exists (openai)
└── .env.example                       # ✅ Exists

✅ = Done
❌ = To build
📦 = Package to create
```

---

## Technology Stack

### **Core Dependencies**
```python
# requirements.txt
openai>=1.0.0          # Already listed
pyyaml>=6.0            # Config files
requests>=2.31.0       # HTTP client
flask>=3.0.0           # Mock devices (dev only)
```

### **Stdlib-Only Components**
- Agent runtime (asyncio)
- Device registry (ipaddress, asyncio)
- Safety engine (ipaddress)
- Tool framework (subprocess, json, pathlib)
- Project manager (json, pathlib, datetime)

### **Optional/Future**
- `langchain` - If tool orchestration gets complex
- `fastapi` - If we add web GUI
- `rich` - Better CLI UX
- `pydantic` - Stronger validation

---

## Decision Points

### 🤔 **Questions to Decide:**

1. **CLI Framework:**
   - Option A: Simple argparse (minimal)
   - Option B: Click (better UX)
   - Option C: Rich (beautiful TUI)
   
   **Recommendation:** Start with argparse, upgrade to Click/Rich in Phase 7

2. **Configuration:**
   - Option A: YAML only (current design)
   - Option B: TOML (more Pythonic)
   - Option C: Python files (maximum flexibility)
   
   **Recommendation:** YAML (as designed)

3. **Async Runtime:**
   - Option A: Pure asyncio (as designed)
   - Option B: Trio (cleaner API)
   
   **Recommendation:** asyncio (stdlib)

4. **Testing Framework:**
   - Option A: unittest (stdlib)
   - Option B: pytest (better DX)
   
   **Recommendation:** pytest (worth the dep)

5. **Package Distribution:**
   - Option A: pip install -e . (development)
   - Option B: Publish to PyPI
   - Option C: Homebrew formula
   
   **Recommendation:** Start with (A), consider (B) later

---

## Next Actions

### 🎯 **Immediate Next Steps:**

1. **Review Architecture**
   - Read [ADE-ARCHITECTURE.md](ADE-ARCHITECTURE.md)
   - Read [ADE-IMPLEMENTATION-GUIDE.md](ADE-IMPLEMENTATION-GUIDE.md)
   - Validate against your APRIL vision

2. **Clarify Questions**
   - CLI framework preference?
   - Any components to prioritize?
   - Adjust timeline?

3. **Start Phase 1**
   - Create `aprils_ade/` package structure
   - Implement AgentRuntime
   - Implement Tool framework
   - Build ShellTool + FileTools
   - Create basic CLI `aprils-ade chat`

4. **Build Incrementally**
   - Each phase builds on previous
   - Test after each phase
   - Adjust based on learnings

---

## Success Metrics

### ✅ **Phase 1 Success:**
- APRIL holds conversation
- Executes shell commands
- Reads/writes files
- Session context preserved

### ✅ **Phase 3 Success:**
- ESP32 device registered
- Telemetry read successfully
- Safety engine active
- Device health monitored

### ✅ **Phase 6 Success:**
- Vision subagent dispatches
- Camera integration works
- Multi-step project completes
- Artifacts persisted

### ✅ **Phase 7 Success:**
- Complete development environment
- All tools testable
- Mock devices work
- Real-time monitoring functional

---

## Resources Created

1. **Architecture Document** - Complete system design (7,000 words)
2. **Implementation Guide** - Concrete code patterns (6,000 words)
3. **This Roadmap** - Action plan with phases and metrics

**Total design documentation: ~15,000 words**

---

## How to Proceed

1. **Review the docs** - Ensure architecture matches vision
2. **Choose framework options** - CLI, async, testing choices
3. **Start Phase 1** - Build minimal working runtime
4. **Iterate** - Test, learn, adjust
5. **Progress through phases** - Each builds on previous

**The architecture is complete and ready to implement. The implementation guide provides working code patterns for each component. The roadmap gives you a clear path from zero to a working ADE in 12 weeks.**

---

**Ready to start building? Let's begin Phase 1! 🚀**
