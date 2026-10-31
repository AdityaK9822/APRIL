# Device control — read/write over the home-lab network

You are operating APRIL on a home lab segment. The device registry for this work
space is `input/devices.json`. Nothing in this task actuates anything: devices
are reachable, but this run's product is a plan a human executes check-by-check.

Read the registry fully before proposing anything. Device entries carry: id,
class, transport, whether the device can CONFIRM a change (`confirming`), risk
level, and the last observed state with its age.

Produce a controlled write plan as your deliverable:

1. For each device you propose to change: current state (as observed, with age),
   the exact desired parameters, the smallest reversible transition that gets
   there, and why that device needs the change.
2. For each proposed change name the observation that would verify it took hold —
   which field on which device, read back over which transport. If a device
   cannot confirm its own change (`confirming: false`), say so explicitly: that
   write is unverifiable by APRIL and needs a human check.
3. Name every device you deliberately leave untouched and why.
4. If two proposed changes interact (e.g. power draw on one circuit), sequence
   them and say what to watch between them.

## Deliverable

Write the deliverable to `deliverables/device-write-plan.md` in the workspace.
The file must exist, be non-empty, and contain a section per proposed change
when the run ends. A described-but-unperformed observation is worthless: state
what is observed, what is planned, and keep them clearly separate.
