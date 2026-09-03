# APRIL

**An assistant with a body.**

Devices are its limbs — the computer it runs on, the design software on that
computer, and the machines it can reach: 3D printers, CNC machines, ESP32
boards, IoT devices.

You ask for a thing. APRIL designs it, fabricates it, and tells you when to come
and get it.

The intelligence is an LLM; the point is that it is *attached to something*. An
assistant that can only answer is a chatbot. APRIL is meant to design a PCB in
real EDA software, mill and solder it on the CNC, print its enclosure, flash the
board, and hand you a finished object.

---

## The three pillars

APRIL acts through three channels. A real project crosses all three, which is
why none of them is optional.

**The machine** — the computer APRIL runs on. Shell, files, processes, system
state. The substrate everything else runs on top of.

**The software** — the applications that *design* things, driven through their
APIs, CLIs, or scripting interfaces: EDA tools, CAD, slicers. This is where a
thing exists before it is real. Half of any build happens here.

**The devices** — the machines that make things physical. This is where APRIL
stops being software.

Design happens in the software, fabrication on the devices, orchestration on the
machine.

## The body

APRIL knows what it is currently attached to. Each device is a named limb that
carries what it is, what it can do, whether it's reachable right now, and how
dangerous it is.

APRIL plans against the body it actually has, not a hardcoded list. A plan that
needs the CNC while the CNC is offline is a plan APRIL should know is impossible
before it starts.

## Skills and integrations

Every capability APRIL gains is a deliberate piece of engineering, not a generic
passthrough. Adding a tool means an **integration** — code that speaks that
tool's actual language, whether that's an API, a CLI, a serial protocol, or
gcode — and a **skill**, the domain knowledge that teaches an agent to use that
tool *well*, so it produces good output rather than merely valid output.

Capability therefore arrives one tool at a time, and each one should be genuinely
good before the next is started. Growth is measured in integrations, not
features.

## Safety

Full system access is a deliberate feature. But a bad shell command and a bad CNC
command are not the same kind of mistake — one you undo, the other ruins a
workpiece, breaks a machine, or starts a fire. So the policy splits: the machine,
the software, and reading anything run free; anything that moves, heats, cuts, or
flashes is governed by a risk level the device itself declares.

Run it on a machine you control, a network you trust, and next to a workshop you
can reach the power switch in.

## Privacy

Local models run the work they can handle; larger or cloud models are used when
the work genuinely needs them. Keeping your work on your machine is a value here,
not an afterthought — the default is local, going off-box is a decision, and
there is no telemetry.

---

## Status

**In design. Nothing is built yet.**

There is no harness, no tool set, no subagents, no device registry, and no
persistence. This repository currently contains the plan and the configuration
surface, and the code is being written from scratch against it.

An earlier generation — a macOS app with voice and vision — was removed
deliberately. It was built before the harness underneath it existed. It comes
back when that is no longer true.

## Roadmap

Two tracks, built in parallel.

**Intelligence** — hold a conversation, then act through tools, then the
integration and skill pattern proven on one real tool, then subagents, then
session memory.

**Body** — one device read reliably, then a registry of devices as named limbs
with capability and liveness, then the risk policy, then the first actuation: a
physical device doing something small, cheap and reversible because APRIL decided
it should.

They converge at three proof points, in order:

1. **Read the body.** APRIL reliably sees and reports the live state of every
   connected device.
2. **One machine, one object.** *"Print me a bracket that holds this board at
   30°"* — APRIL drives CAD to model it, slices it, sends it to the printer, and
   tells you when to collect it. One software tool, one device, no human step in
   the middle. If this works, the idea works.
3. **The full build.** Design a PCB in EDA software, mill and solder it on the
   CNC, print the enclosure, flash the board.

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
a decision — but that is a preference about *where* the work runs, not a
commitment to a particular model.
