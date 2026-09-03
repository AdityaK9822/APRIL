# APRIL

**An assistant with a body.** Devices are its limbs — the computer it runs on,
the design software on that computer, and the machines it can reach: 3D
printers, CNC machines, ESP32 boards, IoT devices.

You ask for a thing. APRIL designs it, fabricates it, and tells you when to come
and get it.

The intelligence is an LLM; the point is that it is *attached to something*. An
assistant that can only answer is a chatbot. APRIL is meant to design a PCB in
real EDA software, mill and solder it on the CNC, print its enclosure, flash the
board, and hand you a finished object.

Local models run the work they can handle; larger or cloud models are used when
the work genuinely needs them. **Keeping your work on your machine is a value
here, not an afterthought** — the default is local, going off-box is a decision,
and there is no telemetry.

---

## Maintenance — read this first

**This file is the single source of truth for APRIL's idea, scope, and roadmap.
There are no other project docs.**

It describes **what APRIL is and what it should do** — deliberately not how. File
layout, module boundaries, protocols, and code structure are settled when each
file is written, not here.

Whenever a change alters behaviour, the tool set, the config surface, or the
plan, update this file **in the same change**:

1. Correct any section the change invalidated.
2. Move the roadmap item to **Done** with a date, or add a new deferred item.
3. Leave `# ponytail:` comments in code for deliberate corner cuts, naming the
   ceiling — the point at which the shortcut stops working.

A change that ships without updating this file is not finished.

---

## Goal

An assistant that can take a real-world project from a sentence to a physical
object — reasoning about the goal, driving the software that designs it, and
running the machines that make it, without you touching any of them.

The near-term goal is narrower and concrete: one machine, one object, no human
step in the middle.

---

## The three pillars

APRIL acts through three channels. A real project crosses all three, which is
why none of them is optional.

**1. The machine** — the computer APRIL runs on. Shell, files, processes, system
state. This is the substrate everything else runs on top of, and the reason full
system access exists.

**2. The software** — the applications that *design* things, driven through
their APIs, CLIs, or scripting interfaces: EDA tools, CAD, slicers. This is
where a thing exists before it is real. Half of any build happens here.

**3. The devices** — the machines that make things physical: 3D printers, CNC
machines, ESP32 boards, IoT devices, whatever gets added next. This is where
APRIL stops being software.

Design happens in pillar 2, fabrication in pillar 3, orchestration in pillar 1.

---

## Skills and integrations — the unit of work

Every capability APRIL gains is a deliberate piece of engineering, not a generic
passthrough. Adding a tool means two things:

- an **integration** — the code that speaks that tool's actual language, whether
  that's an API, a CLI, a serial protocol, or gcode;
- a **skill** — the instructions and domain knowledge that teach an agent to use
  that tool *well*, so it produces good output rather than merely valid output.

Skills live in a **skill library** that subagents draw from. A subagent picks up
the skills for the job in front of it.

This is where most of the effort in APRIL goes, and pretending otherwise makes
the roadmap dishonest. Growth is measured in integrations, not features. The
consequence is that capability arrives one tool at a time — and each one should
be genuinely good before the next is started.

---

## APRIL and its subagents

**APRIL is the core agent.** It talks to you, understands the goal, plans the
work, breaks it into tasks, and dispatches those tasks to subagents it controls.
It is the only thing that holds the whole picture.

**Subagents do the specialised work.** Each one owns a domain, pulls the
relevant skills from the library, and reports back. APRIL reviews what comes
back before it takes effect — for software that is quality control, and for a
machine that is about to move, it is the last check before something physical
happens.

**Models:** subagents run on APRIL's reasoning model by default. A subagent
declares its own model only when its work genuinely requires different
capability — vision, code generation. A model enters the system when a subagent
needs it, not before. Starting from reasoning is deliberate: APRIL's own job —
converse, plan, decompose, dispatch, review — is a reasoning job, and a roster
of specialised models collected in advance is an inventory, not an architecture.

---

## The body — devices as limbs

APRIL knows what it is currently attached to. Each device is a named limb that
carries:

- **what it is** — 3D printer, CNC, ESP32, sensor node;
- **what it can do** — print, mill, sense, actuate, flash;
- **whether it's here** — online, offline, busy, faulted;
- **how dangerous it is** — see the safety policy below.

APRIL plans against the body it actually has right now, not a hardcoded list. A
plan that needs the CNC while the CNC is offline is a plan APRIL should know is
impossible before it starts.

Today the only real device is an **AXIOM ESP32-S3 telemetry board**, read over
HTTP — sensor data, GPIO, wifi, bluetooth, system state. It is the first limb,
not the intended limit.

---

## Safety stance

Full system access is a **deliberate feature**. There is no sandbox and no
allowlist on command execution — that principle does not change.

But a bad shell command and a bad CNC command are not the same kind of mistake.
One you undo; the other ruins a workpiece, breaks a machine, or starts a fire.
So the policy splits:

**Light** — the machine, the software, and reading anything. Runs free, no
prompt. Guards here are opt-in and off by default.

**Heavy** — anything physical that moves, heats, cuts, or flashes. **Each device
declares its own risk level**, and that level determines what it takes to act:
an ESP32 blinking an LED and a spindle at 18,000 rpm should not share a policy.
The higher the risk, the more the plan is checked — by APRIL, or by you — before
the machine moves.

Run it on a machine you control, a network you trust, and next to a workshop you
can reach the power switch in.

---

## Projects — the unit of ambition

"Build a PCB and a case for it" is hours or days of work, across several
machines, with steps that fail and get retried. That does not fit in a
conversation.

A **project** is the long-lived thing APRIL tracks:

- **goal** — what you asked for;
- **plan** — the steps to get there, and which subagent owns each;
- **state** — done, running, blocked, failed;
- **artifacts** — the files it produced: models, gerbers, gcode, firmware;
- **devices** — what it is using, and for how long.

A project outlives the request, the session, and the process. You should be able
to walk away and come back.

**Not built yet.** The near-term step is session memory — enough context to hold
multi-step work together within a conversation. Durable projects come after, and
the design above is written down now so that what gets built first doesn't make
it impossible later.

---

## Running

Runs on the system `python3` with **no venv**. The only hard dependency is
`openai`.

```bash
cp .env.example .env      # then point it at your model
```

That is the whole setup. The terminal front door is what gets built first;
everything else lands later.

## Configuration

APRIL talks to any **OpenAI-compatible endpoint** — a local runtime or a cloud
provider. Which model runs it is your decision, set in `.env`; nothing else in
APRIL changes when you switch.

| Variable | Meaning |
|---|---|
| `OPENAI_API_KEY` | API key for the endpoint (a placeholder for most local runtimes) |
| `OPENAI_API_BASE_URL` | The endpoint |
| `OPENAI_MODEL` | The reasoning model APRIL runs on |

No model is named here on purpose. Local is the preferred default and going
off-box is a decision — but that is a preference about *where* the work runs,
not a commitment to a particular model.

The device registry, subagents, and safety policy will define their own
configuration as they are built; those knobs get documented here when they
exist.

---

## House style

- **Laziest solution that works.** Keep the file count small; no new file without
  a real reason. Stdlib before dependencies. One line before fifty.
- **Don't neuter command execution.** Full system access is a deliberate feature.
  Guards on the machine and software side are opt-in, off by default. Physical
  devices are the exception, and the risk policy above says why.
- **Stdlib-only for system access:** `os`, `platform`, `subprocess`. A new pip
  dependency needs a one-line justification in the commit message and an entry in
  `requirements.txt`.
- **Preserve the terminal echo** of every command run — the user must see what
  executed.
- **`# ponytail:` comments** mark a deliberate corner cut and **name its ceiling**
  — the condition under which the shortcut stops working.

### Testing

No framework. If you add non-trivial logic (a parser, a branch, a loop), leave one
runnable check — an `assert`-based `demo()` under an `if __name__ == "__main__"`
guard. Trivial changes need no test.

The self-checks must pass with **no model, no network, and no device attached**.

---

## Roadmap

Two tracks, built in parallel, converging at the first real build.

### Track A — intelligence

- [ ] **Talk.** APRIL connects to the LLM and holds a conversation in the
      terminal. No tools, no agency. This is the floor.
- [ ] **Act.** Tools, and a loop that lets APRIL call one, observe the result,
      and iterate until the request is done.
- [ ] **Skills.** The integration + skill pattern, proven end to end on one real
      tool. Establishes what adding a capability actually costs.
- [ ] **Subagents.** APRIL plans, dispatches to a subagent, reviews what comes
      back. Skills pulled from the library per task.
- [ ] **Memory.** Session context, so multi-step work holds together.

### Track B — body

- [ ] **One limb.** The ESP32 board, read reliably over HTTP.
- [ ] **The registry.** Devices as named limbs with capabilities, liveness, and a
      declared risk level. APRIL can report the live state of everything attached.
- [ ] **Risk policy.** Light for machine and software, per-device for anything
      physical.
- [ ] **First actuation.** A physical device does something because APRIL decided
      it should — small, cheap, reversible.

### Where they meet — the proof points, in order

1. **Read the body.** APRIL reliably sees and reports the live state of every
   connected device. Unglamorous; it's what the registry has to prove.
2. **One machine, one object.** "Print me a bracket that holds this board at 30°"
   — APRIL drives CAD to model it, slices it, sends it to the printer, and tells
   you when to collect it. One software tool, one device, no human step in the
   middle. If this works, the idea works.
3. **The full build.** Design a PCB in EDA software, mill and solder it on the
   CNC, print the enclosure, flash the board. The vision, proven.

### Later

- [ ] Durable projects: plan, state, artifacts, and device reservations that
      survive a restart.
- [ ] More limbs: 3D printer, CNC, other ESP roles, IoT devices.
- [ ] More integrations: EDA, CAD, slicers, MCP servers, plugins.
- [ ] ESP: OTA firmware flashing and a serial/USB transport as alternatives to
      HTTP.
- [ ] Model routing inside APRIL — reasoning, code, and vision models chosen per
      task as subagents come to need them.
- [ ] A backend API, so other frontends and systems can call in.
- [ ] The interface layer: a proper app, voice, and vision. Removed once because
      it was built before the harness underneath it existed; it comes back when
      that is no longer true.
- [ ] Auth and per-request confirmation for any non-local caller.
- [ ] Handle Ctrl-C gracefully instead of a traceback.

### Considered, not doing (yet)

- **A single "brain" containing every model** — image, vision, coding, reasoning
  models assembled up front. Nothing emerges from co-locating models; you still
  need the routing, and you'd have paid for every integration before anything
  calls it. Models arrive when a subagent needs one.
- **Sandboxing or an allowlist on the machine** — conflicts with the full-access
  design goal. Physical devices are handled by the risk policy instead.
- **Cloud-first operation** — local is the default; going off-box is a decision.

### Done

- **2026-09-03** — Redesigned around the real idea: an assistant with a body.
  Devices are limbs, not integrations; the three pillars (machine, software,
  devices) replace a single shell tool; APRIL becomes the core agent that plans
  and dispatches to skill-carrying subagents; safety splits into a light policy
  for software and a per-device risk policy for physical machines; projects and
  the two-track roadmap added. The separate upstream **MoE router** was dropped —
  model routing belongs inside APRIL, and starts with reasoning only.
- **2026-09-03** — Reset to scope. The three empty source files were dropped and
  this document stripped back to what APRIL is and should do; implementation
  detail is decided per file, as each is written.
- **2026-09-02** — Collapsed to a single generation. The original macOS app
  (AppKit window, voice, vision) was removed outright along with `parked/`, and
  the five documentation files (`README`, `AGENTS`, `docs/CONTEXT`,
  `docs/ARCHITECTURE`, `docs/ROADMAP`) were merged into this one file.

---

## What's NOT here

Nothing in this document is built yet. There is no harness, no tool set, no
subagents, no device registry, no persistence, and no interface beyond a
terminal that doesn't exist yet either.

The app, voice, and vision are **deferred, not abandoned** — they return once
there is something underneath them worth interfacing with.
