# Deliverable notes — device-write-plan.md

Forced path: `deliverables/device-write-plan.md` (workspace-relative).

The file is the run's product. Content shape:

- One section per proposed change: device id, observed state (with age), desired
  parameters, minimal reversible transition, rationale.
- A verification line per change: which field on which device, over which
  transport, and whether the device can confirm (`confirming: true`) — unverifiable
  writes must be marked as needing a human check.
- A leave-untouched list with reasons.
- A sequencing note for any interacting changes.

The deliverable's field names and section order are part of the request; the
harness must not rename or restyle the artifact.
