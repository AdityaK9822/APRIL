# APRIL

**An assistant with a body.**

```
    "build me a bracket"
           │
           ▼
    ┌──────────────┐
    │   APRIL      │  ◄─ LLM intelligence
    └──────────────┘
           │
    ┌──────┴──────┬──────────┐
    ▼             ▼          ▼
 design      fabricate    orchestrate
 (software)  (devices)    (machine)
    │             │          │
    ▼             ▼          ▼
  PCB         CNC mills    You get it
 models       3D prints   when ready
 (real)       (real)
    │             │
    └─────┬───────┘
          ▼
    [finished bracket]
```

Devices are its limbs — the computer it runs on, the design software on that
computer, and the machines it can reach: 3D printers, CNC machines, ESP32
boards, IoT devices.

The intelligence is an LLM; the point is that it is *attached to something*. An
assistant that can only answer is a chatbot. APRIL is meant to design a PCB in
real EDA software, mill and solder it on the CNC, print its enclosure, flash the
board, and hand you a finished object.

---

## The three pillars

APRIL acts through three channels. A real project crosses all three, which is
why none of them is optional.

```
    ┌────────────────────────────────────┐
    │         APRIL's Intelligence        │
    └────────────────────────────────────┘
            │           │           │
          ┌─┴───┐     ┌─┴───┐     ┌─┴────┐
          │     │     │     │     │      │
        ┌─▼─┐ ┌─▼─┐ ┌─▼─┐ ┌─▼─┐ ┌─▼─┐ ┌─▼─┐
        │   │ │   │ │   │ │   │ │   │ │   │
        │ M │ │ M │ │ S │ │ S │ │ D │ │ D │
        │ A │ │ A │ │ O │ │ O │ │ E │ │ E │
        │ C │ │ C │ │ F │ │ F │ │ V │ │ V │
        │   │ │   │ │   │ │   │ │   │ │   │
        └───┘ └───┘ └───┘ └───┘ └───┘ └───┘
          │        │        │        │
        Shell   KiCad   3D Printer
        Files    CAD    CNC Machine
```

**The machine** — the computer APRIL runs on. Shell, files, processes, system
state. The substrate everything else runs on top of.

**The software** — the applications that *design* things, driven through their
APIs, CLIs, or scripting interfaces: EDA tools, CAD, slicers. This is where a
thing exists before it is real. Half of any build happens here.

**The devices** — the machines that make things physical. This is where APRIL
stops being software.

Design happens in the software → fabrication on the devices → orchestration on the
machine.

## The body

APRIL knows what it is currently attached to. Each device is a named limb that
carries what it is, what it can do, whether it's reachable right now, and how
dangerous it is.

```
                    APRIL (core)
                        │
          ┌─────────────┬┴┬─────────────┐
          │             │             │
       ┌──▼──┐      ┌───▼───┐      ┌──▼──┐
       │ ESP │      │3D Prnt│      │ CNC │
       │ 32  │      │       │      │     │
       │online│     │busy   │      │dead │
       └──────┘     └───────┘      └─────┘
       (arm LED)    (printing)    (offline)

   APRIL plans around what's here
   and what's possible right now.
```

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
workpiece, breaks a machine, or starts a fire. So the policy splits:

```
┌────────────────────────────────────────────┐
│              APRIL's Actions               │
└────────────────────────────────────────────┘
          ▲                        ▲
          │                        │
    [LIGHT POLICY]        [HEAVY POLICY]
          │                        │
    ┌─────┴──────┐          ┌──────┴─────┐
    │            │          │            │
  Machine    Software     Device Risk   Device Risk
  (shell)    (read CAD)      Level A      Level B
   │          │              │            │
   ▼          ▼              ▼            ▼
  runs       runs          confirm?     stop signal?
  free       free          review       manual arm?
             no guards     then run
             opt-in only
```

The machine, the software, and reading anything run free. Anything that moves,
heats, cuts, or flashes is governed by a risk level the device itself declares.

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

Two tracks, built in parallel and converging at proof points.

```
INTELLIGENCE                      BODY
─────────────                      ────

Talk ───────┐                  ┌─ One limb
            │                  │
Act ────────┤                  ├─ Registry
            │                  │
Skills ─────┤  ┌───────────────┤  Risk policy
            │  │               │
Subagents ──┤  │ ┌─────────────┤  First actuation
            │  │ │             │
Memory ─────┘  │ │  ╔═════════════╗
               │ │  ║ Proof Point ║
               └─╫─ ║ Read body   ║
                 │  ║ State live  ║
                 │  ╚═════════════╝
                 │
                 │  ╔═════════════════════════════╗
                 ├─ ║ Proof Point 2: One machine, ║
                 │  ║ one object. Design → print  ║
                 │  ║ (CAD + 3D printer)          ║
                 │  ╚═════════════════════════════╝
                 │
                 │  ╔════════════════════════════╗
                 └─ ║ Proof Point 3: Full build  ║
                    ║ PCB in EDA, mill/solder    ║
                    ║ on CNC, print case, flash  ║
                    ╚════════════════════════════╝

           [everything below is deferred]

         MoE, voice, vision, apps, backend API
```

**Intelligence track:**
- Hold a conversation
- Act through tools
- The integration + skill pattern proven on one real tool
- Subagents
- Session memory

**Body track:**
- One device read reliably
- A registry of devices as named limbs with capability and liveness
- The risk policy
- The first actuation: a physical device doing something small, cheap and reversible because APRIL decided it should

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
