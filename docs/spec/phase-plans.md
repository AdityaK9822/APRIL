# APRIL — Standing Phase Plans (P0–P5)

**Provenance:** rendered 2026-10-31 from the master implementation plan (Appendix D of
`~/.opencode/plan`). Live per-item status is tracked in the OpenCode session instruction
entries (`todo.april-master-plan`); this document is the repo-side standing reference —
it records what each phase changes, how it is verified, and what gates it.

**How to read this:**

- Item IDs `P{phase}-{n}` follow the master plan. Each phase ends with an `-acceptance`
  gate that must pass before the next phase starts.
- House rules the gates cite: self-checks run with **no model, no network, no device**;
  `CLAUDE.md` is updated in the same change as behavior; `# ponytail:` comments name
  deliberate ceilings.
- The budget ledger is asserted, never tolerated: if an exactness check fails on a
  fallback path, that is a defect to fix, not a tolerance to grant.
- **One file, deliberately.** The plans stay in a single scroll so cross-phase
  dependencies stay visible (ledger scaling hands P2→P3, substrate hand-off P0→P1,
  spec-first ordering P4/P5). The split axis is **plan vs spec, not phase**: the three
  P4/P5 specs (`ocean-profile-schema.md`, `zcode-substrate.md`,
  `persona-dimension.md`) arrive as separate files because they have their own
  lifecycles. Ceiling: once this doc passes roughly 600 lines, or per-phase execution
  records start living in-repo, it splits into `docs/spec/phase-plans/<phase>.md`
  plus an index.

---

## P0 — Repair and consolidate

**Goal:** make the vendored Harness² engine runnable end to end (one degenerate
task), get it under version control honestly, and reduce the doc set to the
standing plan.

### Evidence (verified 2026-10-31)

- `core/harness/config.py:7-14` — has `VERTEX_*` but **no `BUN`, no `OPENCODE_DIR`**;
  `DEFAULT_PROPOSER_CHANNEL='opencode'` points at the broken channel.
- `proposer.py:277` — `str(config.BUN)` would raise `AttributeError` at runtime;
  `proposer.py:397-401` — `_opencode()` wants `config.OPENCODE_DIR` and an upstream
  `scripts/setup_benchmark.py` that does not exist in this checkout.
- `recursion.py _roll` — calls `adapter.execute()` and records via `ledger.rollout()`,
  but never calls `runmark.mark_complete` (`runmark.py:35`), so `.adapt_complete`
  markers are never written at run sites.
- `execution_manager.py` — `_run_parallel`/`_run_sequential` are degenerate (a loop of
  `_run_one`, no proposer stage); the real recursion lives in
  `recursion.run_parallel/run_sequential/run_mode` (`run_mode` at `recursion.py:569`,
  dispatching `'agg'`/`'seq'`).
- `core/agent.py:32-34` — `AgentRuntime.substrate` returns `None`; `execute()` is a bare
  temp-dir stub with `delivered()=True`; `base_harness()` returns `None`.
- Untracked: `core/harness/`, `core/components/`, `core/substrate/`, `EXPERIENCE.md`,
  `docs/github_instructions/`, `ZCode/`; `runs/` artifacts (summary.json,
  `.adapt_complete`, library/) not yet governed by `.gitignore`.
- `harness2/` — the upstream checkout named in earlier plans — does not exist in this
  tree; the P1 skeleton inputs are designated future-state, not expected to exist.

### Items

**P0-0.1 — `core/harness/config.py` + `proposer.py`**

- Add `BUN = os.environ.get('APRIL_BUN', 'bun')` and
  `OPENCODE_DIR = os.environ.get('APRIL_OPENCODE_DIR', '')` (empty = channel disabled).
- Flip `DEFAULT_PROPOSER_CHANNEL` `'opencode'` → `'claude_cli'` (broken default must not
  be the fallback route).
- In `proposer.py:_opencode()`, guard `not config.OPENCODE_DIR` FIRST, before touching
  `config.BUN`, so failure is `ProposerError('no OpenCode checkout configured…')`,
  never `AttributeError`.
- Do NOT add `scripts/setup_benchmark.py` in P0 — the opencode channel stays off until
  a real checkout exists.

**P0-0.2 — `core/harness/recursion.py`**

- In `_roll()`, after the exists check:
  `if exists: runmark.mark_complete(rd, run_id=run_id, harness_dir=hdir)`.
- Mark only rollouts whose `execute()` returned normally with a real run dir — never
  the exception path (a marker on a dead dir would fake reusability). Guard: `exists` only.
- Safe under `_roll_many` concurrency: per-rollout directories, atomic `os.replace`,
  `runmark.fingerprint(harness_dir)` guards config mixing (`is_complete`,
  `runmark.py:62-73`).

**P0-0.3 — `core/harness/execution_manager.py`**

- Delete degenerate `_run_parallel`/`_run_sequential` (they double as false "recursion"
  while bypassing `recursion.run_mode` entirely).
- Delegate to the real drivers via `asyncio.to_thread`
  (`recursion.py:343-358` run_parallel / `:452-464` run_sequential; `run_mode` selects).
- Prefer `schedule.run_task` as the single driver if the plumbing maps — one write path
  rule; settle the seam (`schedule.run_task` vs direct `recursion.run_mode`) in build
  with a small diff.
- Base rollouts come from one shared helper (`schedule._roll_bases` semantics: k bases,
  `ledger.rollout` recorded once each).
- Preserve `run_task` mode aliases (`'both'` → both modes gathered). After this change
  there is **exactly one** path from `run_task` to `adapter.execute()`.

**P0-0.4 — `core/agent.py`**

- `substrate` → a real `SurfaceSpec` built in `core/substrate/` (dir exists, empty),
  parametrizing APRIL's own editable file surface; fields follow `tree.py:40-61`.
- `base_harness()` → a minimal 3-file template tree at `core/harness/basetree/april/`
  (`systemprompt.md`, `guardrails.md`, `tool_guidance.md`) that survives
  `tree.validate` + `ComponentRegistry.validate_all`.
- `execute(task_id, harness_dir, run_id)`: create the run dir under the runs root,
  write `trajectory.txt`, place a deliverable under `deliverables/` — driven by
  `APRIL_EXECUTOR`: `'dry'` (default; no LLM, structural — what makes the gate runnable
  offline) vs `'live'` (P1, handed to the zcode substrate).

**P0-0.5 — git + CLAUDE.md**

- Track: `core/harness`, `core/components`, `core/substrate`, `EXPERIENCE.md`,
  `docs/github_instructions`.
- `.gitignore`: `runs/`, `*.adapt_complete` tmp artifacts (run state is runtime data,
  not repo content), plus `build/`, `*.egg-info/`, `.vscode/`.
- Stage explicit paths only — pre-existing user modifications are not part of this
  change (no blanket `add -A`).
- CLAUDE.md (same commit): replace the stale "There is no harness" claim; note Harness²
  is vendored Google Apache-2.0 method code installed locally; versions: prompts
  `VERSION='harness2-1'`, runmark `VERSION=1`.

**P0-0.6 — consolidation (executed by the commit that introduced this file)**

- Remove the 22 superseded implementation documents (list at bottom), preserved in
  git history.
- Paste `docs/spec/phase-plans.md` (this file) as the standing plan.
- CLAUDE.md: the doc-structure note + the standing principle "the ADE must itself be
  an APRIL agent"; future specs live in `docs/spec/`.

### Acceptance

1. `python -c 'import core.harness.config as c; c.BUN, c.OPENCODE_DIR'` imports clean;
   the opencode channel fails as `ProposerError`, not `AttributeError`.
2. `Harness(AgentRuntime(AgentConfig.from_env())).run_task('smoke-0001', k=1)` with
   `APRIL_EXECUTOR=dry` completes: per-rollout run dir contains `trajectory.txt` +
   `deliverables/`; `.adapt_complete` written with harness fingerprint `!= 'absent'`.
3. `summary.json` exists with mode blocks + ledger identity intact (R/P arithmetic
   holds even when proposal stages error-fallback).
4. Offline self-checks (no model, no network, no device) pass.
5. `git -C ZCode status --porcelain` empty (ZCode stays untouched).
6. Repo doc set == KEEP list + this file; git history preserves removed docs.

### Risks

- Flipping `DEFAULT_PROPOSER_CHANNEL`: any external caller hardwiring `'opencode'`
  breaks loudly — that is desired; note in the commit message.
- Ledger exactness must survive proposal-stage fallback; if `assert_identity()` fails
  on the fallback path, that is a `recursion.py` defect to fix in P0, not a tolerance
  to grant.
- Marking dead rollouts would fake reusability — guard with `exists` only.
- Two write paths if delegation half-lands — enforce the one-path rule.

### Commits

- Commit 1: P0-0.1…P0-0.5 code repairs + CLAUDE.md maintenance (behavior + doc in one
  change, per the CLAUDE.md rule).
- Commit 2: P0-0.6 consolidation (`git rm` + this file's landing + CLAUDE.md doc note).

---

## P1 — ZCode substrate + authored mini-tasks

**Goal:** make ZCode (the TS monorepo under `ZCode/`, kept byte-for-byte unchanged)
the first execution substrate for benchmark rollouts.

**Evidence (verified 2026-10-31):**

- Batch recipe, from ZCode's own docs (`ZCode/apps/zcode-cli/docs/usage/13-automation.md`):
  `zcode --prompt <p> --cwd <workdir> --mode yolo --output-format stream-json --no-color`
  with per-sample `ZCODE_DATA_BASE_DIR=<runHome>` isolation; deliverable = forced output
  file.
- Harness-side surface: `tree.py:40-61` SurfaceSpec fields; `prompts.py` slot tables +
  `HARNESS_PROMPT_BAD_WORDS`; `april_spec.py` BenchPrompts slots; `schedule.run_task` /
  `_roll_bases` semantics; `ledger.assert_identity` exactness.
- `ZCode/` is present but untracked; integration is process-boundary only — no ZCode
  source change, ever.

**Items:**

- **P1-1.1** `tree.py`: `SurfaceSpec('zcode')` — `.agents/skills/<name>/SKILL.md`,
  workspace `AGENTS.md`, `.zcode/agents/*.md`, hooks-event schema config, plugin
  manifest (c8 option), `MEMORY.md` (c3 variant); omitted-is-inherited contract kept.
- **P1-1.2** `prompts.py`: `_SURFACE_ZCODE` table in ZCode's exact vocabulary (skill
  tool on-demand, `task` tool subagents, hook event names, plugin manifest fields).
- **P1-1.3** `tree.py:validate`: ZCode gates — skill frontmatter `name`/`description`;
  per-skill trigger line present in `AGENTS.md`; hooks JSON vs v2 event list; plugin
  manifest required fields; snake_case scripts `py_compile`; optional
  `zcode doctor --json`.
- **P1-1.4** `zcode_adapter.py` (new): `BenchmarkAdapter` — materialize tree → spawn
  the CLI recipe with isolated `ZCODE_DATA_BASE_DIR`; forced-deliverable-file
  convention; timeout/retry semantics copied from the claude channel; add
  `APRIL_ZCODE_BIN` (default `'zcode'`) to `config.py`.
- **P1-1.5** `core/harness/benchtasks/` (new): authored mini-tasks — device-control
  read/write, MCP wiring, capability doc — as `task.md` + deliverable notes; wired
  through `april_spec.py` BenchPrompts slots; no grader vocabulary in slots.
- **P1-1.6** `schedule.py`: first full `run_sweep(substrate='zcode')`, proposer on
  `claude_cli`.

**Acceptance:** ledger exactness on ≥1 full task; `git -C ZCode status --porcelain`
clean; the forced-deliverable contract holds end to end.

**Risks:** the adapter must stay at the process boundary (no coupled build, config, or
source changes on the ZCode side); deliverable parsing depends entirely on the forced
output file; ZCode CLI availability is a fresh config surface (`APRIL_ZCODE_BIN`).

---

## P2 — Personality kernel (constraint mode)

**Goal:** fold the OCEAN personality engine in as a hard constraint kernel: profiles
are data, persona clauses compile into missions, and validation caps always-on
persona text.

**Items:**

- **P2-2.1** Commit `core/harness/personality.ts` — the reference implementation,
  archived verbatim in the master plan (Appendix A).
- **P2-2.2** Port to `core/harness/personality.py` with full `PersonaConfig` fidelity:
  `validate`, `bandOf`, `clamp`, `adjust`, `derive`, `compile_persona` (=
  `buildSystemPrompt`), `similarity` (cosine over `ocean/100`); assert-based
  cross-check vs the TS reference (the APRIL preset renders all sections).
- **P2-2.3** Land `profiles/`: `april.json` (the APRIL preset, **minus `userContext`**),
  `user.json` (**sanitized**: the provenance comment moves to the local override), and
  one contrast profile (`verifier.json`, e.g. O35/C95/E45/A55/N60, `candorFloor` 85);
  `userContext` → git-ignored `.ade/etc/persona-user-context.md`.
- **P2-2.4** `spec.py`: new `HarnessPrompts` slots `psy_levers` + `persona_guidance`,
  extended through the slot bad-word filter.
- **P2-2.5** `prompts.py`: compiled persona block appended to `propose`/`aggregate`/
  `compose_round` missions **only when a profile is active**; derived rules injected
  via `derive()` thresholds (proactivity≥60, caution≥60, structure≥70).
- **P2-2.6** `tree.py:validate`: `PERSONA_CLAUSE_CAP` on always-on persona text; long
  persona prose becomes an on-demand `skills/<name>/SKILL.md`.
- **P2-2.7** `ledger.py`: `expected_rollouts(k, ‖dims‖)` / `expected_sessions(k,
  ‖dims‖)` — INV/DOM arithmetic unchanged this phase; exactness assert kept.
- **P2-2.8** `library.py`: lessons carry `{ocean, profile_id}` metadata; regenerate
  `INDEX.md`; `EXPERIENCE.md` schema gains a Persona column (header at line 14).
- **P2-2.9** `personality.py` `demo()`: assert-based self-checks — non-empty condition
  sets for all profiles, cap enforcement fires, cosine ordering correct; no model/no
  network; strip Appendix A from the master plan file.

**Acceptance:** every proposal mission carries compiled persona clauses; a
cap-violating tree is rejected → 1 retry → fallback (`STAGE_ATTEMPTS=2` unmodified);
ledger identity intact with ‖dims‖=2 formulas.

**Risks:** privacy — committed profiles carry no `userContext` and no `USER_PROFILE`
provenance (personal facts live in the git-ignored local override); retry/fallback
must not loosen the cap; blind selection must not see persona data.

---

## P3 — PSY dimension (personality as a learnable third axis)

**Goal:** promote personality from constraint to a third learnable dimension alongside
INV/DOM — proposals evolve *how components express behavior*, judged post-selection.

**Items:**

- **P3-3.1** `prompts.py`: `_PSY_TEMPLATE` owns behavioral mechanism only (tone,
  pacing, delegation style, verification temperament); consumes `derive()` params, not
  raw traits; cannot touch INV/DOM lanes.
- **P3-3.2** `recursion.py run_parallel`: k INV + k DOM + k PSY stages; workers =
  `min(‖dims‖, PHASE_WIDTH)`; aggregates see all 3k candidates and decide trait
  attribution.
- **P3-3.3** `ledger.py`: R → `(2+‖dims‖)·k` = 5k, P → 4k; `assert_identity` stays
  exactness-exact (docstring formula comments updated too).
- **P3-3.4** `judge.py` + adapter `score()`: trait adherence judged **post-selection
  only** — deterministic checklist from `protocols`/`extraRules` (includes the two new
  protocol checks: no unapproved public actions; no secrets stored/echoed/logged) +
  optional LLM judge behind `JudgeBoundary`.
- **P3-3.5** `selection.py` `reflect_adoption`/`_distil`: edit rows gain trait
  attribution; distilled lessons record the ocean vector + `transferable` flag.
- **P3-3.6** `library.py load_context`: rank entries by OCEAN cosine vs the active
  profile; below-threshold entries load only if `transferable: true`.
- **P3-3.7** `schedule.py`: `ns()` gains a persona segment `[-P<persona>]`;
  `run_sweep(profiles × tasks × seeds)`; `_resume` fingerprint unchanged.

**Standing invariant (5-part):** ID:candor-formal | sched: PSY=INT | temperature:
`0.2 + 0.7·O/100` on the active profile | banlist: panes | adversary: trap.

**Acceptance:** ≥1 task · k≥2 · dims {INV,DOM,PSY} · ≥2 personas → exactly 5k rollouts
per task; blind selection personalized nowhere; per-persona libraries;
`ComponentRegistry.diff` separates PSY-sourced edits.

**Implementation notes (2026-11-02):** PSY is gated on `psy_levers`, which only
`resolve_prompts` fills from an active profile, so persona-free runs keep the
2-dimension R=4k/P=3k arithmetic. `Ledger.n_dims` is validated (2 or 3) and is
the single source for `assert_identity` and the summary. The deterministic judge
has exactly two machine checks (unapproved public action with an approval
marker; secrets hygiene); every other protocol/extra/threshold rule is recorded
`attested` with `ok=None`. Retrieval uses `SIMILARITY_FLOOR = 0.95`; a PSY-only
lesson is `transferable: false`. `run_sweep(profiles=...)` fans out profiles and
per-profile library roots; a multi-seed run remains a caller loop over
`seed=` (the namespace already carries `-s<seed>`). Offline pins: a k=2 APRIL
run proving R=10=5k, P=8=4k, eight markers; a two-profile sweep proving
`-P<persona>` namespaces and separate library roots.

---

## P4 — Scale-out contract

**Goal:** prove the persona axis scales by data, not code.

**Items:**

- **P4-4.1** Demonstrate the contract: a third profile lands as **one JSON file**
  (e.g. `ridealong`: low N, high A, mid E) and runs a 1-task sweep with zero code
  edits.
- **P4-4.2** Document the schema: `docs/spec/ocean-profile-schema.md` — authored here,
  when the profile format has stabilized.
- **P4-4.3** Out-of-band vectors degrade to pure c1 guidance; mark the fallback with a
  `# ponytail:` comment naming the ceiling.
- **Deferred (not now):** 30-facet Big Five expansion; legacy-lesson nearest-profile
  backfill script.

**Implementation notes (2026-11-03):** `load_profiles` globs `profiles/*.json` (id =
filename stem), so the third persona, `profiles/ridealong.json` (low N, high A, mid E),
landed as data with no registry and no harness source naming it; the offline pin scans
`core/harness/**/*.py` for the id. Its 1-task sweep runs as
`zcode-zcode-agg1-Pridealong` with R=5=5k, P=4=4k, four markers and
`library_root/ridealong`. `docs/spec/ocean-profile-schema.md` is the format contract
(fields, band edges, derivation formulas, validation, transfer gate, add-a-profile
recipe). Out-of-band vectors are today `facets` (the deferred 30-facet expansion): they
load and run, but `personality.out_of_band` names the ceiling (with the `# ponytail:`
note), `compile_persona` emits authored c1 text only — no OCEAN directives, Voice/
Honesty lines, or threshold rules — and `psy_mechanism` returns `""`, so
`prompts.active_dims` stays `("INV","DOM")` and the ledger keeps R=4k/P=3k. Unknown
top-level, `ocean` and `relationship` keys are refused at load time so a typo cannot
silently compile nothing. Offline pins: the ridealong sweep, the facet degradation
through `resolve_prompts`, and the schema doc's required sections.

---

## P5 — ADE deployment + runtime persona

**Goal:** adopted trees become live runtime configuration — the ADE itself runs as an
APRIL agent.

**Items:**

- **P5-5.1** Spec-first docs (before dependent code): `docs/spec/zcode-substrate.md`,
  `docs/spec/persona-dimension.md` (P4-4.2 covers the schema doc).
- **P5-5.2** `core/ade/` (new): deploy adopted trees to
  `.ade/harnesses/<persona>/<domain>/` + index (persona, domain, date, score);
  adoption runs through APRIL's own tools — the ADE is itself an APRIL agent.
- **P5-5.3** Runtime boot: `APRIL_PERSONA=<id>` → adopted c1 persona into the system
  prompt, c2 `guardrails.md` into the permission layer, `derive().temperature` into
  sampling (`toRequest()` semantics).
- **P5-5.4** TUI: surface `selection.json` / `adoption.json` / `/library` lesson rows
  per persona.

**Acceptance:** an adopted APRIL tree drives a live session with the APRIL persona;
guardrail protocols (incl. the public-action gate) evaluate at runtime.

**Implementation notes (2026-11-03):** the specs landed first
(`docs/spec/zcode-substrate.md`, `docs/spec/persona-dimension.md`), then the code:
`core/ade/` (`deploy.py`, `boot.py`, `views.py`, `__main__.py`). Deployment validates
on `APRIL_SURFACE` and refuses — never sanitizes — an invalid source; a persona-free
adopted tree is stamped with the compiled c1 block (`## persona: compiled` on
`systemprompt.md`) and the profile protocols (`## persona: protocols` on
`guardrails.md`), while proposer-authored `## persona:` sections are left untouched.
The deployment persona ceiling is `ADE_PERSONA_CAP = 6000` chars, distinct from the
engine's proposal cap (`tree.PERSONA_CLAUSE_CAP = 1600` — proposals are per-run
always-on cost; a deployed persona IS the runtime system prompt and cannot become an
on-demand skill; `# ponytail:` the real ceiling is the runtime token budget — revisit
when one exists). Every deploy appends an `index.json` row fingerprinted by
`runmark.fingerprint`; `load_deployed` refuses a tree whose bytes changed after
deployment (redeploy is a decision, never a silent fallback). Runtime boot:
`AgentConfig.from_env` reads `APRIL_PERSONA`; `AgentRuntime.__init__` applies it once
— c1 at the head of the session context (exactly once), c2 into the action guard,
`derive().temperature` over the configured temperature — resolution order is deployed
tree (fingerprint-verified) then committed profile, and an unknown id fails loudly
before any request. The permission layer shares the post-selection checklist's
machine gates verbatim through the new public seam `judge.public_action_hits /
approved_marker / secret_hits`: an unapproved public action becomes a
`[persona-guard] …` tool result (never executed; the marker text re-entry is
instructed in the block reason), secrets are refused outright, non-shell tools pass
through. Local user facts join at boot only from the git-ignored
`<ADE root>/etc/persona-user-context.md` (`## APRIL userContext` block) and never
leave as text — `persona_view` reports a count. The ADE stays agent-driveable:
plain callables and `python3 -m core.ade {deploy,boot,view}`. TUI widgets remain
deferred; `core/ade/views.py` ships the stable JSON contracts. Offline pin
(self-check 19) covers deploy→tamper-refusal→boot→guard→runtime→view plus the
`from_env` pin; the status-emit crash into user-owned `core/events.py`
(`StatusEvent.event_type`) is swallowed at the boot seam with a `# ponytail:` note.

---

## Superseded documents (removed 2026-10-31, preserved in git history)

- Root: `IMPLEMENTATION.md`
- ADE drafts: `docs/ADE-ARCHITECTURE.md`, `docs/ADE-IMPLEMENTATION-GUIDE.md`,
  `docs/ADE-MCP-ARCHITECTURE.md`, `docs/ADE-ROADMAP.md`, `docs/ADE-ZCODE-FEATURES.md`
- APRIL-OS drafts: `docs/APRIL-OS-ARCHITECTURE.md`, `docs/APRIL-OS-IMPLEMENTATION.md`,
  `docs/APRIL-OS-UI-ARCHITECTURE.md`
- Implementation walkthroughs: `docs/implementation/01-CORE-IMPLEMENTATION.md`,
  `docs/implementation/02-SUBAGENT-IMPLEMENTATION.md`,
  `docs/implementation/HELLO-HARDWARE-IMPLEMENTATION.md`,
  `docs/implementation/MASTER-IMPLEMENTATION-ROADMAP.md`
- Fix-log / summary / TUI plans: `docs/COMPLETE-IMPLEMENTATION.md`,
  `docs/FIXES-AND-UPDATES.md`, `docs/IMPLEMENTATION-IMPROVEMENTS.md`,
  `docs/IMPLEMENTATION-SUMMARY.md`, `docs/MEMORY-IMPLEMENTATION.md`,
  `docs/TEXTUAL-TUI.md`, `docs/TUI-CLI-ARCHITECTURE.md`,
  `docs/TUI-END-TO-END-PLAN.md`, `docs/TUI-ENHANCEMENTS.md`

Recover any of them with `git log --diff-filter=D -- docs/` (and the root file via
`git log --diff-filter=D -- IMPLEMENTATION.md`).
