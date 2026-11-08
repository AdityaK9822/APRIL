# the persona dimension — spec

**Status:** authored 2026-11-03 (P5-5.1, before the P5 code lands). The profile format
itself is specified in `docs/spec/ocean-profile-schema.md`; this document covers what
P5 builds on top of it: the **ADE deployment**, the **runtime persona boot**, and the
**TUI data views**. Implementation sits in `core/ade/` (new) plus two small seams in
`core/config.py` and `core/agent.py`.

## 1. The dimension in one paragraph

A persona is data: a profile JSON compiles into a constraint block (c1) whose derived
parameters also drive a learnable third proposal dimension (PSY) when a run is
profile-backed, and are machine-checked post-selection by a deterministic checklist.
P5's job is the last leg: run the engine with a persona attached to the runtime
itself, and make adopted harnesses deployable and bootable — the ADE's deployment
target is output of the ADE's own agent runs, not hand-crafted config.

## 2. ADE layout (`.ade/`, git-ignored)

```
.ade/
  harnesses/
    index.json                     # deployment ledger, one row per deploy
    <persona>/
      <domain>/                    # ONE deployed tree per (persona, domain)
        systemprompt.md            # c1  — always-on persona/procedure
        guardrails.md              # c2  — non-negotiable rules (permission layer)
        tool_guidance.md           # c4
        (…any other surface files the adopted tree carries)
  etc/
    persona-user-context.md        # personal facts (local override, never committed)
```

- The root is `.ade/` at the repository root; `APRIL_ADE_ROOT` overrides it (the
  offline self-checks point it at a temp dir; nothing here commits).
- The deployed tree is a **tree on a `SurfaceSpec`** — for APRIL's own runtime that is
  the `april` surface (`systemprompt.md`, `guardrails.md`, `tool_guidance.md`). Trees
  adopted on other surfaces are not deployable to APRIL's runtime until a substrate
  mapping exists (`# ponytail:` one mapping per surface, data-driven when a second
  substrate needs a runtime).
- `index.json` is a list of rows, newest last; the loader reads the **latest** row for
  a `(persona, domain)`. Row contract:

```json
{
  "persona": "april",
  "domain": "default",
  "date": "2026-11-03T…Z",
  "task_id": "demo/demo-0001",
  "run_dir": "runs/…/<task>",
  "score": null,
  "fingerprint": "fp-…"
}
```

- `score` is whatever post-selection scoring produced (`null` when none);
  `fingerprint` is `runmark.fingerprint` of the deployed tree (tamper evidence for the
  boot: a tree that changed after deployment is refused).

## 3. Deployment contract (`core/ade`)

- `deploy(harness, surface, persona, domain, task_id, run_dir, score)` validates the
  source tree against the surface (`tree.validate` + `ComponentRegistry.validate_all`
  when a registry applies), then copies it into
  `.ade/harnesses/<persona>/<domain>/` and appends the index row. Invalid source ⇒
  refuse, never sanitize.
- **Persona stamping.** When the adopted tree does not already carry the persona
  (persona-free selection), `deploy(persona=…)` appends the compiled persona to
  `systemprompt.md` under a `## persona:` section and the profile protocols to
  `guardrails.md` under the same tag. Both obey the
  `tree.PERSONA_CLAUSE_CAP` (1600 chars each) — a deployment that cannot say what it
  says inside the cap refuses to lie about it.
- **The ADE must itself be an APRIL agent.** Every operation is invocable through
  APRIL's own tool surface — a plain callable **and** a CLI (`python3 -m core.ade`),
  so the agent can drive deployment with its shell tool exactly as a human would.
  There is no UI-only path.

## 4. Runtime boot (`APRIL_PERSONA=<id>`)

Boot order (all offline-capable; nothing here needs the model until a session runs):

1. `AgentConfig.from_env()` reads `APRIL_PERSONA` into `AgentConfig.persona` (default
   `""` ⇒ no boot; every existing behavior stays byte-identical).
2. `core.ade.boot(persona, domain)` resolves a source, in order:
   (a) the deployed tree `.ade/harnesses/<persona>/<domain>/` (latest index row,
   fingerprint-verified);
   (b) otherwise the committed `profiles/<id>.json`, compiled — with an explicit,
   loud error when the id is unknown.
3. c1 → the system message: for a deployed tree, the `systemprompt.md` text; for the
   fallback, `compile_persona(profile)`. If the git-ignored
   `.ade/etc/persona-user-context.md` exists, its `## APRIL userContext` block renders
   as `## About the user` — local facts join the persona at boot, never in the repo.
4. c2 → the **permission layer**: `guardrails.md` (or the profile's protocols) loads
   into an `ActionGuard` that wraps shell execution in `AgentRuntime`:
   - machine gate, deterministic: a public action (`git push`, `curl -X POST`, `npm
     publish`, … — the same patterns the post-selection checklist uses,
     `judge.public_action_hits`) requires an approval marker in the same command
     string; a secrets pattern (`sk-…` tokens, hardcoded tokens) is refused outright;
   - everything else the persona declares is **attested**: recorded with the action
     log, never pretended to be verified at runtime;
   - non-shell tools pass through unchanged (`# ponytail:` the gate is shell-only
     until runtime tools gain write shaped calls).
5. `derive(profile).temperature` **overrides** `AgentConfig.temperature` — the
   `toRequest()` semantics (system prompt + temperature land together from one
   source). The runtime logs the persona, its source, and the temperature at boot.
6. Idempotence & failure: booting twice re-inserts nothing (the guard, system
   message, and temperature are set once); an unknown persona id raises loudly at
   boot instead of silently running unpersonified.

## 5. TUI data views (`core/ade.views`)

Pure JSON builders; a widget only renders what these produce — no TUI logic in the
ADE, no ADE logic in the TUI.

- `selection_view(task_dir)` — `selection.json` as recorded by the blind selector
  (persona never appears in it).
- `adoption_view(task_dir)` — `reflection/<mode><k>/adoption.json`, the chosen label +
  why + candidate identity map.
- `library_view(library_root)` — per persona: per domain INDEX rows for each
  `harnesses/<entry>` (profile, ocean vector, transferable, cue) — what the
  `/library` pane should list.
- `persona_view(persona, ade_root, …)` — the boot summary (persona, source, deployed
  fingerprint, system-prompt size, temperature, machine gate rules) plus its persona
  namespaced runs and library rows.

Rendering is wired into the TUI when the widget work stabilizes; the JSON contracts
above are the stable seam (`# ponytail:` widgets land with the user's TUI work).
