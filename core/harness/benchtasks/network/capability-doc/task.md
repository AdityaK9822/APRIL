# Environment capability doc — sense / act / boundary

You are documenting what a deployed APRIL can do against one environment,
strictly from its inventory snapshot: `input/environment.txt`. The inventory is
the authority — if a limb is not in that file, the environment does not have it.
Do not probe anything live.

Write `deliverables/capability.md` with these sections:

1. **Sense** — every limb that observes state: what it is, where it lives
   (machine, endpoint, protocol) as the inventory gives it, what it observes,
   and any freshness caveat the inventory carries.
2. **Act** — every limb that changes state: the state it can set, its transport,
   and whether the change is reversible. Anything the inventory marks risky
   carries that risk into the doc.
3. **Boundary** — what is out of bounds and why, exactly as the inventory states
   it (unowned segments, authorized-but-fragile devices, anything marked
   no-touch). Copy the inventory's wording for boundaries, not your own.
4. **Reliability notes** — per limb, the failure mode the transport implies
   (a stream that drops, a command-line tool that needs the machine awake), and
   what the doc cannot promise.

Every claim must name the inventory line it came from (quote it inline in
backticks). Absence is information: where the inventory is silent about a limb's
freshness, reversibility or ownership, the doc says "not stated by inventory"
in place — it never guesses.

## Deliverable

The deliverable is `deliverables/capability.md` in the workspace: it must exist,
be non-empty, and carry the four sections above with evidence lines. Section
names are part of the request.
