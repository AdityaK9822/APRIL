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

**Acceptance proven live (same day, commit `61ed7b1`):** a full offline sweep on
`demo-0001` (`APRIL_EXECUTOR=dry`, agg mode, k=1) adopted `agg1` with
`ok=True fallback=False` — a real engine adoption, not a hand-stamped tree — and
`python3 -m core.ade deploy` put it at `.ade/harnesses/april/default`
(fingerprint `f17ce112a0fe5e2a`, index row carrying `task_id demo/demo-0001` and
the selection's run dir). `APRIL_PERSONA=april` then booted a real session from
that **deployed adopted tree** (`source=deployed:default`, the profile fallback
provably unused; temperature still persona-owned) and drove four live turns on the
account's Free-plan model (`beam:cloud`, ollama.com gateway): (1) a benign shell
round-trip answered from real `ls`/`cat` output; (2) read-only git inspection
correctly passed by the machine gates, then an **unapproved-push refusal per c2
protocols**; (3) an **API-key echo refusal** ("hard line in my protocol"); (4) a
verbatim `git push origin HEAD` instruction still declined with reasoning.
The public-action gate EVALUATED on every live tool call (all ten read-only ones
passed — zero false positives) while its block branch is pinned offline by
self-check 19 with a synthetic push tool-call inside a booted session; on this
basis the gates are live-evaluated, and no live session ever proposed a public
action because the protocols held first. Finding recorded for the runtime-proposer
open question: `glm-5.3-flash` is served by the user's configured gateway but the
account plan returns 402 for it — wiring is config-only
(`OPENAI_MODEL=glm-5.3-flash`), the spend decision stays with the user. Session
evidence: `runs/april-april-agg1/demo-0001/p5-live-session.md` (git-ignored, runs
are runtime state; known cosmetic noise from user-owned `memory_extractor.py`).

---

## P6 — 30-facet Big Five expansion (facet grain becomes a legal second shape)

The plan's first deferred item, taken after P0–P5 closed. Spec first, then the
kernel, then pins — behavior and the contract doc in one change.

The profile format now has two grains, mutually exclusive at load: `ocean` (the
five domains) and `facets` (the standard NEO-PI-R 30, `FACET_MAP` in
`core/harness/personality.py`). Facet values aggregate to domain scores at load
(`aggregate_facets`: each domain = rounded mean of its present facets, `_round` =
the JS `Math.round` half-up rule the derived parameters already pin), so the
untouched kernel still sees an ordinary five-trait vector.

- **Full coverage** (≥1 facet in each of O, C, E, A, N; facets may be missing
  inside a covered domain) compiles through the normal path — band directives,
  derived Voice/Honesty, threshold rules, the PSY lane (`active_dims` goes 3-D),
  ledger arithmetic — as though it were always `ocean`. `compile_persona` gains one
  **data-only** `## Facets` section (`name value (domain)` lines) rendered in both
  paths; per-facet directives (`FACET_CONDITIONS`) remain deferred.
- **Partial coverage** keeps the P4 degradation: authored c1 text only, PSY off
  (`psy_mechanism` `""`, ledger `R = 4k`, `P = 3k`), and `out_of_band()` names the
  domains with no facet evidence as the reason.
- Missing domains carry a **neutral 50 fill** in the loaded `ocean` vector so
  temperature math and the cosine transfer gate stay shape-valid; the fill never
  reaches compiled text, and an ocean+facets profile can never exist to pollute it.
- Loader gates fail loudly: unknown facet names, `ocean`+`facets` together, or
  neither grain — each is a `ValueError` at `persona_from_dict`/`validate`.

Contract in `docs/spec/ocean-profile-schema.md` §2/§5/§7 (§7 renamed "Facet
vectors and the degradation contract"; §9's deferred list now names the
`FACET_CONDITIONS` table instead of the grain itself).

**Pins (offline, no model/no network):** `personality.demo()` now proves the
registry shape (30 facets, 6 per domain), and **kernel purity** — a facet profile
built per-domain from pairs `(s-1, s)` averages to `s − 0.5` and must land exactly
on the committed data-only profile's own scores: identical `## Personality
(OCEAN)` section text, identical `DerivedParams`, cosine 1.0 against the twin.
The twin is selected without spelling its id — the P4 zero-code scan reads
`core/harness/*.py` raw and forbids the name, so the harness still mentions no
third profile. Partial-coverage pins, the data-only Facets block pins, and the
three loud-refusal pins live in the same demo. Self-check 20 (agent-level) runs
the facet grain through the real seams: a `facetride` profile in a tmp profiles
dir compiles identically to its ocean twin through `compile_persona` and through
`resolve_prompts` (`persona_guidance` carries the OCEAN block + `## Facets`,
`psy_levers` non-empty, `active_dims == ("INV", "DOM", "PSY")`), with the loader
refusals pinned through `profile_from_path`. Check 17 (the P4 degradation seam)
was reworked for the mutual exclusion — its facets now ride a facet-only
construction — with its assertions unchanged.

`# ponytail:` facets left open on purpose: the per-facet `FACET_CONDITIONS`
directive table (a facet's own value compiling into its own band line), a TS
mirror of the aggregation (the archive stays the verbatim pre-P6 reference; the
bun cross-check pins ocean-grain only), and no committed facet-grain profile —
`demo()` constructs facet profiles in tmp dirs only, because committed profiles
are asserted to compile `## Voice`/`## Honesty` and a facet profile would only
coincidentally do so. (The committed-profile ponytail was promoted in P7-7:
`profiles/facetfull.json` is a full-coverage facet profile whose non-degraded
branch compiles `## Voice`/`## Honesty` for real.)

Acceptance: `python3 -m core.agent` is green at **24 `ok:` lines** (23 engine
pins + the demo's bun TS cross-check) with no model / no network / no device;
`git -C ZCode status --porcelain` stays empty; the TS reference is untouched by
diff.

**Engine leg proven offline (same day, docs-only commit):** beyond the pin seams,
the facet grain ran through the *real engine* on the zcode substrate — a 1-task
agg sweep (`process-boundary` stub, dry executor, k=1) under namespace
`zcode-zcode-agg1-Pfacetride`: row `status ok`, mode `ok=True`, `finals=[agg1]`,
every stage falling back only for the documented dry reason (never a facet
reason), ledger **R=5, P=4, n_dims=3 exact**, four `.adapt_complete` markers each
with a deliverable, `selection.json ok=True`, and `library_root/_library/facetride`
scoped per profile (no lesson files this dry run). The resume path also showed
the runmark fingerprint machinery skipping the completed run on re-invocation —
unaffected by grain. ADE interop: a persona-free APRIL base tree deployed at an
isolated leg ADE root (`runs/_p6-leg-ade`, never the repo `.ade`) with
`persona=facetride`, booted offline at `source=deployed:default` with the
**facet-derived temperature (0.62, equal to the ocean twin's `derive()`)** and the
compiled c1 carrying `## Personality (OCEAN)` + `## Facets` (with the half-up
artifact `fantasy 59 (openness)` visible). Evidence tree:
`runs/zcode-zcode-agg1-Pfacetride/p6-facet-engine-leg.md` (git-ignored). Two
loose ends are pinned by observation, not by change: boot.py reads the APRIL
surface's c1/c2 file names, so a ZCODE-surface deployment boots with empty c1
text (`# ponytail:` the ADE runtime host is APRIL; revisit when a zcode-hosted
runtime exists); and the legacy-lesson backfill stays deferred — no real legacy
library exists yet (one doc-sample row in `EXPERIENCE.md`, no `.ade/library`),
exactly the precondition the deferral named.

---

## P7 — Finishing pass (facet directives first)

The last layer: give facet grain its payload, mirror it to the TS archive, then
close the loose ends P6 named. Spec and behavior in one change per item.

### P7-1 — Facet-conditioned directives (landed 2026-11-04)

`FACET_CONDITIONS` (`core/harness/personality.py`) maps each of the 30 facets to
one behavioral clause per non-mid band (`veryLow/low/high/veryHigh`). Design
invariants:

- **`mid` emits nothing** — the domain `DIRECTIVES` table already owns moderate
  behavior; a facet line there would only duplicate it and spend persona budget.
- **Registry order governs the render.** Both facet sections render in
  `FACET_MAP` order (keep-first on duplicate facet pairs), so JSON key order
  never leaks into compiled text — a rebuild in any key order compiles
  byte-identically.
- **Section shape:** `## Facet directives` (`- name (band): clause` lines)
  renders above the `## Facets` data block, only in the non-degraded branch.
  Partial vectors keep the P4 authored-only contract; ocean grain renders no
  facet section at all.
- **Loud ceiling:** `FACET_DIRECTIVE_CAP` (3000 chars) is enforced in
  `validate()` against the rendered section — table growth over the cap refuses
  loudly instead of silently inflating every mission. The shipped table's worst
  case (all 30 facets outside mid) renders 2656, so P6's "full coverage
  compiles" contract cannot break silently. # ponytail: the cap is a
  self-judged boundary against this section becoming a second system prompt.
- **Loud gaps:** a missing `FACET_CONDITIONS` entry for a rendered band raises
  from `facet_directives` (silence would be truncation); `validate()` turns it
  into a validate error. Bands share `bandOf`'s edges exactly (20/40/60/80); no
  facet-specific thresholds exist, by contract.
- **Zero plumbing changes:** the compiled persona is the mission slot's only
  source (`spec.resolve_prompts` fills `persona_guidance`), so directives ride
  every profile-backed mission automatically; the PSY/ledger seams stay
  untouched and grain-blind.
- **TS mirror deferred (P7-2):** `personality.ts` remains the verbatim pre-P6
  archive; the bun cross-check keeps pinning ocean-grain profiles only.

Contract: `docs/spec/ocean-profile-schema.md` §5 (cap bullet), §7 "Compiled
shape" (rewritten), §8 (facet grain compiles directives with zero authoring),
§9 (FACET_CONDITIONS off the deferred list). Pins: `personality.demo()` gains a
ten-pin facet-directive block (registry completeness, worst-case ≤ cap, mid
silence, divergent render + section placement, band-edge sweep, key-order leak,
dedupe, facet-twin 4-line render, ocean/degraded silence, loud cap refusal);
`core/agent.py` self-check 21 proves the mission-slot seam (facet grain → 4
directive lines through `resolve_prompts`, ocean grain → none). Self-checks:
25 ok lines, offline.

### P7-2 — TS mirror of facet aggregation + directives (landed 2026-11-04)

`core/harness/personality.ts` is no longer the verbatim pre-P6 archive. It now
also ships `FACET_MAP`, `aggregateFacets` (the same half-up `_round`), the
`FACET_CONDITIONS` table and `facetDirectives` (registry order, mid silence,
dedupe, table-gap raises), the facet fields on `PersonaConfig`, a
`validate()` carve for facet names/values, the registry-ordered `## Facets`
data block and the `## Facet directives` section in `buildSystemPrompt`, plus
the `FACET_RIDEALONG` full-coverage twin fixture. `_ts_reference_check`
extends the bun cross-check (already the ocean pin): it parses two new
`--- Facet prompt ---` / `--- Facet derived ---` markers from the archive's
demo guard and asserts byte-equality of both the compiled text and the nine
derived params against Python's `compile_persona(FacetTwin)` / `derive(FacetTwin)`.
Spec: ocean-profile-schema.md updates the two P7-1 ponytail comments ("archive
remains pre-P6 verbatim" in Aggregation; "TS mirror is P7-2" in Compiled
shape) to record the mirror landing. The `prompts.VERSION` kernel constant
moves `harness2-1` -> `harness2-2` (mirrored in the upstream harness2 copy).
Self-check stays 25 `ok:` lines: P7-2 extends the existing bun cross-check on
the demo line, it does not add a new named pin. `git -C ZCode status
--porcelain` empty.

### P7-3 — Legacy-lesson backfill (landed 2026-11-04)

`core/harness/backfill.py` implements the assign / skip / keep-free logic on
in-memory row dicts and never rewrites real data: `nearest_profile(lesson_ocean,
profiles)` (cosine, `SIMILARITY_FLOOR` gate; tie-broken by lowest id; None when
no profile is close enough or the vector is missing/unparseable),
`plan_backfill(rows, profiles)`, `apply_backfill(..., dry_run=True)` (the
default writes nothing; `--apply` writes a `.backfill-plan.json` side-car in
the library root), plus a CLI (`--rows/--profiles/--library-root/--apply`). Accepts
a sequence of profile ids OR an explicit mapping; coerces `O70 C90 ...` ocean rows
and 0..100 / 0..1 scales; rows already carrying a `profile` are skipped
(idempotency); `apply` raises when nothing is profileable, so the deferral's
precondition is executable, not a silent no-op. Spec: `ocean-profile-schema.md`
§9 now records the backfill as "implemented but unrun" rather than "absent".
Self-check: 26 ok lines (P7-3 named pin, synthetic fixtures only — near-APRIL
ocean assigns, far stays free, no-vector stays no-vector, dry-run is
byte-identical on disk, re-run is idempotent, CLI precondition message fires on
empty apply). `git -C ZCode status --porcelain` empty.

### P7-4 — Multi-seed sweep driver (landed 2026-11-04)

`core/harness/schedule.py`: `run_sweep(..., seeds=...)` (and the zcode wrapper)
now take seeds as a driver parameter instead of relying on a caller loop — the
unchanged single-seed path runs once per entry and the returned report is one
aggregate with `per_seed` / `results_by_seed`, a shared `library_root`, and
per-seed R/P ledger rows (namespaces keep their `-s<seed>` segment); `seeds=None`
(default) takes the byte-identical seedless branch. Self-check: 27 ok lines
(two seeds, one task, stub + `_DryProposer`, both namespace directories with
exact R=4k/P=3k ledgers at 2 dims, aggregate carries both, seedless branch is a
plain sweep). `git -C ZCode status --porcelain` empty.

### P7-5 — ZCODE-surface boot (landed 2026-11-04)

`core/ade/boot.py` and `_stamp` in `core/ade/deploy.py` now resolve c1 (system
prompt) / c2 (guardrails) by ROLE against `SurfaceSpec.always_on` instead of
the hardcoded `systemprompt.md` / `guardrails.md`: APRIL keeps its two per-role
files; the zcode surface folds both halves into the single `AGENTS.md`, so a
zcode deployment stamps `## persona: compiled` AND `## persona: protocols`
into that file (stamp guards now check the specific section headings, not just
any `## persona:` heading, so c2 is no longer suppressed once c1 lands in a
shared file) and boot resolves the role resolution, returning non-empty c1 with
the compiled persona sections and guardrails derived from the profile when there
is no distinct guardrails file. An unresolvable (empty `always_on`) surface and
a deployed persona with an empty system prompt raise loudly rather than
booting empty. The P6 empty-c1 ponytail (boot reading the APRIL surface's c1/c2
file names for every surface) is retired; the evidence reference in
`runs/zcode-zcode-agg1-Pfacetride/p6-facet-engine-leg.md` is now a historical
note. Self-check: 28 ok lines (zcode deploy+boot yields non-empty c1 with
compiled persona sections + `## Protocols`; APRIL deploy+boot under the same
resolution path is a regression guard). `python3 -m core.agent` green at 28
ok; `git -C ZCode status --porcelain` empty.



### P7-6 — TUI view contracts (landed 2026-11-04)

The visual leg: `core/ade/views.py` is and remains the only data source for TUI
widgets (the widgets in the user-owned `core/textual_tui.py` / `core/widgets/`
are consumers only). Added two headless pure render helpers —
`render_persona_summary(view)` and `render_library_view(rows)` — plus a
`surfaces_view()` catalog exposing the APRIL/ZCODE surface metadata, all
read-only and terminal-free. The persona renderer carries counts and chars only:
personal fact text never appears in the rendered pane (verified by the pin:
`"fact one"` / `"fact two"` absent even when the override file carries facts).
Self-check pin (29 ok) renders a deployed `april` persona view through the
temp `APRIL_ADE_ROOT` and asserts the surfaces catalog, terminal-free renders,
fact-text absence, and the empty-view fallbacks. Data contracts, not renderer
logic, so user-owned TUI streams can absorb these without conflicts.
`python3 -m core.agent` green at 29 ok; `git -C ZCode status --porcelain`
empty.



### P7-7 — Committed facet-grain profile (landed 2026-11-04)

`profiles/facetfull.json` is the canonical facet-grain profile: all 30 standard
facets, six per domain, and no `ocean` key. The loader aggregates it before the
untouched kernel sees it, so its hand-computed half-up domain means
(`O 60 / C 55 / E 50 / A 85 / N 15`) land exactly on `ridealong`'s vector —
identical `## Personality (OCEAN)` section, identical `DerivedParams`, cosine
1.0 — while the non-degraded branch compiles `## Voice`/`## Honesty` for real.
The 18 facet directive lines render 1365 chars, well under
`FACET_DIRECTIVE_CAP` (3000). Self-check pin 30 runs the data-only proof: the
facets are regrouped in the check and the domain means are computed by hand
(half-up, not delegated to `aggregate_facets`), the harness source is scanned
for the id (clean), and a 1-task offline `-Pfacetfull` sweep yields the real
driver at `R=5=5k`, `P=4=4k`, `n_dims=3` with four marked rollouts and a
deliverable in each. `docs/spec/ocean-profile-schema.md` §8 documents the
facet-grain recipe with `facetfull` as the canonical example, and §9 lists it
alongside `ridealong`. No harness code changed to support the profile; the P6
"no committed facet-grain profile" ponytail is promoted. `python3 -m core.agent`
green at 30 ok; `git -C ZCode status --porcelain` empty.

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
