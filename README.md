# APRIL

**An assistant with a body — and the body is the networked physical world.**

```
   you ──▶  APRIL ──▶  the networked physical world
            (LLM)
              │
              ├──▶  SEE      cameras + a vision model
              ├──▶  SENSE    ECG · EEG · telemetry
              ├──▶  ACT      lights · AC · robot arms
              ├──▶  NETWORK  discovery · authorized wifi audits
              ├──▶  BUILD    CAD → CNC → 3D print → flash
              ├──▶  …        new limbs slot in the same way
              └──▶  TUI      Textual terminal interface (modern, async)
```

APRIL's limbs are the machines it can reach over the network: the computer it
runs on, the software on that computer, and everything wired into the same
network — cameras, sensors, appliances, microcontrollers, robots, and the
fabrication machines that build new hardware. Wifi is how it reaches most of them
today.

The intelligence is an LLM; the point is that it is *attached to something*. An
assistant that can only answer is a chatbot. APRIL **senses** the world, **acts**
on it, and **works the network itself** — and it can take a request all the way
to a physical result.

---

## What it can do

APRIL's body is not a fixed set of gadgets — it is **whatever is reachable on the
network right now.** The limbs fall into a handful of domains. This list is
illustrative, not exhaustive — the whole point is that new domains slot in the
same way.

| Domain | What APRIL does | Reached via |
|---|---|---|
| **Vision / surveillance** | See through cameras; a vision model describes and reasons over the feed | IP cameras |
| **Sensing / medical** | Read ECG, EEG, and other sensors; environmental telemetry | ESP + sensors |
| **Home / appliances** | Control wifi appliances — lights, AC, switches, plugs | wifi appliances |
| **Robotics / custom MCU** | Drive robot arms and other microcontrollers built for a job | ESP / other MCU |
| **Network / security** | Wifi auditing, device discovery, raw packet work — *authorized testing only* | wifi radio |
| **Industrial / warehouse** | Replace batch and manual control loops with a reasoning agent | networked PLCs/MCUs |
| **Fabrication** | Design in software, then print, mill, solder, and flash | 3D printer, CNC, EDA |

**Nothing here is built yet** — this is the scope, not a feature list. See
[Status](#status).

### The ESP32 — the archetypal limb

The ESP32 is not a fixed appliance; it is a **programmable wifi bridge to the
physical world.** Flashed one way it is a sensor node; flashed another it
actuates GPIO, drives hardware, speaks to other microcontrollers, or acts as a
radio for network work. It is the cheapest, most general way to grow a new limb —
which is why it comes first. (Today's transport is wifi / IP; other radios come
when a project needs them.)

---

## What you could build with it

The point of a body is what you can do with it. Each of these is one request →
one plan → real devices, crossing the pillars end to end. **None is built yet** —
this is what the body is *for*, and the shape of the projects APRIL is being built
to run.

**👁  See — cameras + a vision model**
> *"Who's at the gate?"* — APRIL pulls the camera feed, a vision subagent
> describes what's in frame, and answers. Point it at a room, a doorway, a
> workbench: it has eyes wherever there's a lens on the network.

**🩺  Sense — sensors and instruments**
> *"Log my ECG for the next hour and flag anything odd."* — APRIL reads an
> ESP-connected ECG/EEG or environmental sensor and keeps the trace on your
> machine. A reasoning agent over live medical or lab telemetry.

**💡  Act — appliances and actuators**
> *"It's too warm in here."* — APRIL reads the room and switches the AC; dims a
> light; flips a plug. Home automation where the logic is an LLM, not a rigid
> rule, so "make it cosy" is a command it can actually reason about.

**🦾  Robotics — custom microcontrollers**
> *"Sweep the left shelf."* — APRIL drives a robot arm built on an ESP32 or
> similar MCU. Any hardware you can flash and reach becomes a limb it can
> command, with the skill for that rig loaded from the library.

**📡  Network — authorized security work**
> *"Audit my home network."* — APRIL discovers what's connected, probes it at the
> packet level, and hands back a clean report of weak spots. **Only on networks
> you own or are authorized to test** — a workshop tool, not a weapon.

**🏭  Industrial — reasoning over a control loop**
> Replace a warehouse's fixed batch schedule or a manual control loop with an
> agent that reasons about the line in real time and adjusts as conditions
> change.

**🛠  Build — a sentence to a finished object** *(the flagship)*
> *"Print me a bracket that holds this board at 30°."* — APRIL models it in CAD,
> slices it, runs the printer, and tells you when to collect it. Pushed all the
> way: **design a PCB in EDA → mill and solder it on the CNC → print the
> enclosure → flash the firmware** — one request, a working device in your hand.

---

## The three pillars

APRIL acts through three channels. A real project crosses all three, which is why
none of them is optional.

```
   one request crosses all three:

   ┌─ 1 · THE MACHINE    orchestrate
   │     the computer it runs on — shell, files, system
   │     state. the substrate; the reason for full access.
   │
   ├─ 2 · THE SOFTWARE   reason & design
   │     the apps it drives — design tools (EDA, CAD,
   │     slicers), vision models, network/security tooling.
   │
   └─ 3 · THE DEVICES    sense & act
         everything physical on the network — cameras,
         sensors, appliances, robots, MCUs, machines.

   the network is the connective tissue between them.
```

**The machine** — the computer APRIL runs on. The substrate, and the reason full
system access exists.

**The software** — the applications APRIL drives: design tools (EDA, CAD,
slicers), vision models that turn a camera frame into meaning, and network /
security tooling that turns a radio into an audit.

**The devices** — everything physical on the network. This is where APRIL stops
being software.

The **network** is how the machine reaches most devices — and, in the security
domain, a thing APRIL acts on directly.

## The body

APRIL knows what it is currently attached to. Each device is a named limb that
carries what it is, what it can do, whether it's reachable, and how dangerous it
is.

```
   APRIL (core) — the body it has right now:

      ├──  camera        online    ·  ready to see
      ├──  ECG sensor    online    ·  ready to sense
      ├──  smart light   off       ·  ready to act
      ├──  robot arm     idle      ·  ready to actuate
      └──  CNC mill      offline   ·  can't be used in a plan

   APRIL plans around what's here and reachable right now —
   never a hardcoded list.
```

A plan that needs the CNC while the CNC is offline is a plan APRIL should know is
impossible before it starts.

## Safety

Full system access is deliberate. But a wide body means more than one kind of
mistake, so the policy has three axes:

```
   three axes of risk:

   ┌─ PHYSICAL   moves, heats, cuts, flashes?
   │             each device declares its own risk level;
   │             higher risk → more checks before it acts.
   │
   ├─ NETWORK    auditing and packet work are scoped to
   │             networks you own or may test. a hard line.
   │
   └─ DATA       a home camera, an ECG — sensing carries
                 weight even when it moves nothing.
   │
   everything else — machine, software, ordinary reads —
   runs light: free, no prompt.
```

Everything else — the machine, the software, ordinary reads — runs light: free,
no prompt. Run APRIL on a machine you control, a network you're authorized to
touch, and next to a workshop you can reach the power switch in.

## Privacy

Local models run the work they can handle; larger or cloud models are used when
the work genuinely needs them. Keeping your work on your machine is a value here,
not an afterthought — the default is local, going off-box is a decision, and
there is no telemetry.

---

## Status

**In development. Core systems being built.**

The harness is in place — a module-based structure with async agent runtime,
database, and tooling. The Textual TUI is ready for testing with event bus,
streaming, and IPC.

### What's Available

- ✅ Textual TUI - Modern terminal interface
- ✅ Agent Runtime - Async conversation engine
- ✅ Event Bus - Decoupled agent-UI-logger communication
- ✅ Streaming - Token-by-token message delivery
- ✅ IPC - Separate logger process via Unix socket/TCP
- ✅ Memory Database - SQLite with connection pooling
- ✅ Tools Framework - Extensible tool system
- ✅ Structured Logging - Backend logger with IPC bridge

### Pending

- ❌ Device Registry - Dynamic endpoint management
- ❌ Subagents - Specialized agent instances
- ❌ Device Discovery - Network scanning
- ❌ Plan Execution - Task orchestration

An earlier generation — a macOS app with voice and vision — was removed
deliberately. It was built before the harness underneath it existed. It comes
back when that is no longer true.

## Roadmap

Two tracks, built in parallel:

- **Intelligence** — hold a conversation, then act through tools, then the
  integration + skill pattern proven on one real tool, then subagents, then
  session memory.
- **Body** — one limb read reliably, then a registry of devices as named limbs
  with capability and liveness, then the risk policy, then the first actuation.

They converge on **a proof in each mode of the body** — each small, cheap, and
end to end rather than one grand demo:

```
  0. READ    live state of every connected device
  1. SEE     a camera feed a vision model describes
  2. ACT     one wifi appliance toggled on request
  3. NETWORK a wifi audit of a network you own
  4. BUILD   "print me a bracket at 30°" — CAD → slice → print
```

The north star past these is **the full build** — design a PCB in EDA, mill and
solder on the CNC, print the enclosure, flash the board — but that's the horizon,
not the first thing to prove.

## Running

Runs on the system `python3` with no venv. The only hard dependency is `openai`.

```bash
cp .env.example .env      # then point it at your model
```

APRIL talks to any **OpenAI-compatible endpoint** — a local runtime or a cloud
provider. Which model runs it is your decision:

| Variable | Meaning |
|---|---|
| `OPENAI_API_KEY` | API key for the endpoint (a placeholder for most local runtimes) |
| `OPENAI_API_BASE_URL` | The endpoint |
| `OPENAI_MODEL` | The reasoning model APRIL runs on |

No model is named on purpose. Local is the preferred default and going off-box is
a decision — a preference about *where* the work runs, not a commitment to a
particular model.

---

## Usage

### Basic

```bash
python main.py
```

This opens the TUI and a separate logger tab.

### Single Pane Mode (no separate logger tab)

```bash
python main.py --single-pane
```

All output (including logs) shows in the same terminal window.

### Without Agent (TUI-only mode)

```bash
python main.py --no-agent
```

Run the TUI without connecting to an LLM. Useful for testing the interface.

### Debug Logging

```bash
python main.py --log-level DEBUG
```

Show detailed logs including LLM requests, tool calls, and memory operations.

### CLI Flags

| Flag | Description |
|------|-------------|
| `-m, --model MODEL` | Override model from config |
| `--log-level LEVEL` | Backend logger level (DEBUG/INFO/WARNING/ERROR) |
| `--log-file FILE` | Path to backend log file |
| `--max-iterations N` | Maximum tool call iterations (default: 100) |
| `--show-logs` | Show log panel in TUI (default: hidden) |
| `--no-agent` | Run TUI without agent |
| `-s, --single-pane` | Run in single pane mode |
| `-n, --no-spawn` | Don't spawn new terminals |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Alt+Enter` | Add newline (multiline input) |
| `Ctrl+C` | Cancel current generation |
| `Ctrl+L` | Toggle log panel |
| `Ctrl+S` | Show stats |
| `Ctrl+Q` or `Esc` | Quit |
| `/help` | Show slash commands |

### Slash Commands

Type `/command` in the input field:

| Command | Description |
|---------|-------------|
| `/clear` | Clear conversation |
| `/quit` | Exit application |
| `/help` | Show help |

---

## IPC Protocol

The logger connects to the TUI via Unix socket (macOS/Linux) or TCP (Windows).

### Event Format

Each line is a JSON object:

```json
{
  "type": "message.delta|tool_call.start|tool_call.output|tool_call.done|log|error|status",
  "payload": { ... },
  "timestamp": "2024-01-01T00:00:00.000000",
  "id": "abc12345"
}
```

### Log Levels

- `DEBUG` - Detailed debugging info (dimmed in display)
- `INFO` - Normal operational messages
- `WARNING` - Warning messages (yellow)
- `ERROR` - Error messages (red)

### Sensitive Data Redaction

API keys, tokens, and secrets are automatically redacted in logs. Output patterns
like `api_key=...` or `token=...` are replaced with `***REDACTED***`.

---

## Project Structure

```
Open_INT/
├── main.py              # Entry point with launcher
├── launcher.py          # Spawns TUI + logger tabs
├── core/
│   ├── __init__.py      # Module exports
│   ├── agent.py         # Core agent runtime
│   ├── events.py        # Event bus and event types
│   ├── ipc_server.py    # IPC server for logger
│   ├── ipc_logger.py    # Logger subprocess
│   ├── textual_tui.py   # Main Textual app
│   ├── config.py        # Configuration
│   ├── session.py       # Session management
│   ├── database.py      # SQLite memory DB
│   ├── logger.py        # Structured logging
│   ├── backend_logger.py # Backend logger bridge
│   └── widgets/         # Textual widgets
│       ├── status.py
│       ├── messages.py
│       ├── input.py
│       ├── logs.py
│       └── stats.py
├── tools/
│   ├── __init__.py
│   └── shell.py
└── tests/
    ├── test_core.py
    ├── test_memory.py
    └── test_tui.py
```

---

## Known Limitations

1. **Markdown rendering** - Basic support (code, bold, italic, links). Not full CommonMark.
2. **Long output truncation** - Tool output > 5000 chars truncated with marker.
3. **Session persistence** - Memory DB only. No CLI save/load yet.
4. **Platform support** - tmux detach detection is a known issue.
5. **Multi-user** - Not supported. Single session per process.

---

## Testing

```bash
# Run widget tests
python test_textual_tui.py

# Run core tests (requires pytest)
python -m pytest tests/ -v
```

---

## License

MIT
