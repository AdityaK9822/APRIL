# APRIL

**An assistant with a body — and the body is the networked physical world.**

```
        "what's at the door?"     "turn the AC off"
        "audit my wifi"           "print me a bracket"
                       \             /
                        ▼           ▼
                  ┌───────────────────────┐
                  │        APRIL          │  ◄─ LLM intelligence
                  │  plan · dispatch ·    │
                  │      review           │
                  └───────────────────────┘
                            │
        ┌──────────┬────────┼────────┬──────────┐
        ▼          ▼        ▼        ▼          ▼
      SEE        SENSE     ACT     NETWORK    BUILD
     camera      ECG/EEG   lights   wifi      CAD → CNC
     + vision    sensors   robots   audit     → 3D print
        │          │        │        │          │
        └──────────┴────────┴────────┴──────────┘
                            ▼
                  the physical world,
                  reached over the network
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

## The three pillars

APRIL acts through three channels. A real project crosses all three, which is why
none of them is optional.

```
    ┌───────────────────────────────────────────────┐
    │                   APRIL                        │
    └───────────────────────────────────────────────┘
        │                  │                   │
   ┌────▼────┐       ┌─────▼──────┐      ┌─────▼──────┐
   │ MACHINE │       │  SOFTWARE  │      │  DEVICES   │
   │         │       │            │      │            │
   │ shell   │       │ design/EDA │      │ cameras    │
   │ files   │       │ vision     │      │ sensors    │
   │ system  │       │ network    │      │ appliances │
   │ state   │       │ tooling    │      │ robots/MCU │
   │         │       │            │      │ printers   │
   └─────────┘       └────────────┘      └────────────┘
   orchestrate        reason/design      sense & act
        │                  │                   │
        └──────── network: the connective tissue ────────┘
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
                       APRIL (core)
                            │
        ┌──────────┬────────┼────────┬──────────┐
        ▼          ▼        ▼        ▼          ▼
     ┌─────┐   ┌──────┐  ┌─────┐  ┌──────┐  ┌──────┐
     │ cam │   │sensor│  │ AC  │  │robot │  │ CNC  │
     │online│  │online│  │ off │  │ idle │  │offline│
     └─────┘   └──────┘  └─────┘  └──────┘  └──────┘
       see      sense     act     actuate    build

   APRIL plans around what's here and what's
   possible right now — not a hardcoded list.
```

A plan that needs the CNC while the CNC is offline is a plan APRIL should know is
impossible before it starts.

## Safety

Full system access is deliberate. But a wide body means more than one kind of
mistake, so the policy has three axes:

```
  PHYSICAL RISK          NETWORK AUTH           DATA SENSITIVITY
  (per device)           (the hard line)        (reads aren't free)
        │                      │                       │
  moves/heats/cuts?      your network or        a home camera?
  device declares        one you're             an ECG?
  its risk level;        authorized to test.    sensing carries
  higher = more          not opt-in, not        weight even when
  checks first.          negotiable.            it moves nothing.
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

**In design. Nothing is built yet.**

There is no harness, no tool set, no subagents, no device registry, and no
persistence. This repository currently holds the plan and the configuration
surface; the code is being written from scratch against it.

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
