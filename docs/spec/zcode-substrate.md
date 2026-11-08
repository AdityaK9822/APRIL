# the zcode substrate — spec

**Status:** landed in P1 (2026-11-01, commit `1143293`); authored here as the substrate's
standing contract. Implementation of record: `core/substrate/zcode.py` +
`core/harness/zcode_adapter.py`. Facts are pinned to ZCode's own docs
(`ZCode/apps/zcode-cli/docs/`), not to guesses about the product.

## 1. Invariants

1. **Zero source changes to the ZCode checkout.** APRIL only writes workspace files and
   seeds memory into an isolated data root. The self-checks run
   `git -C ZCode status --porcelain` and assert it is empty.
2. **The adapter stays at the process boundary.** ZCode is never built, configured, or
   edited by APRIL; integration is a documented CLI invocation per rollout.
3. **Delivery is forced, not interpreted.** A run ends without the task's deliverable
   file = not delivered (kept as failure evidence; never counted as success).

## 2. The surface (honoring zcode's merge order)

ZCode's instruction block merges `~/.zcode/AGENTS.md` (user-owned, not ours) then the
workspace `AGENTS.md` (project-owned, editable). The surface is therefore:

| File | Role |
|---|---|
| `AGENTS.md` | **c1/c2/c4 share the ONE always-on file**. Cap: 60 000 chars — `# ponytail:` zcode books no documented cap; the number exists so always-on prose cannot silently become the whole context |
| `.agents/skills/<name>/SKILL.md` | c7 skills, loaded on demand; frontmatter `name` **must equal** the directory name (docs 08) |
| `.zcode/agents/<name>.md` | c5 sub-agents, dispatched through the model-visible `Agent` tool by `subagent_type` |
| `.zcode/config.json` | c2 hooks lever: a run-config whose `hooks.enabled` + `hooks.events` block is schema-validated against the v2 event list |
| `.zcode/plugins/<name>/.zcode-plugin/plugin.json` | c8 option: a local plugin loads from its manifest only |
| `MEMORY.md` | c3 variant: the memory **seed** — materialized by the adapter into the isolated memory store (zcode never reads it from the workspace) |

Hook contract (from `packages/contracts/src/hooks/index.ts`), reproduced as
`ZCODE_HOOK_EVENTS`: `SessionStart, UserPromptSubmit, PreToolUse, PermissionRequest,
PostToolUse, PostToolUseFailure, Stop`. Hook types on the surface: `process`, `command`.
Workspace hooks stay **untrusted** in zcode until the launcher grants trust — P1 ships
schema validation, not trust wiring.

## 3. Validation gates (`tree.validate`)

A proposal's tree must pass, or it is discarded (retry once, then fall back — the
standard `STAGE_ATTEMPTS=2` machinery):

- frontmatter `name`/`description` on every `SKILL.md`; a trigger line naming the skill
  present in `AGENTS.md`;
- sub-agent `subagent_type` referenced correctly; reserved script names enforced;
- `MEMORY.md` within the 40 000-char ceiling (# ponytail: memory is injected by the Main
  Memory prompt);
- hooks JSON: nested shape (`hooks.enabled` + `hooks.events`), events on the v2 list,
  every entry a list, each hook `type ∈ {process, command}`, non-empty `command`,
  optional `args` a list of strings, optional `timeoutMs` numeric;
- plugin manifest fields when the plugin dir is used;
- compiled `scripts/*.py` must be `snake_case`-clean and `compile()`-clean;
- optional CLI gate: `zcode doctor --json` when a CLI is configured.

The gate matrix in the offline self-checks exercises eight representative failures, all
rejected with the expected message.

## 4. The batch recipe (verbatim, from zcode docs `13-automation.md`)

```
zcode --prompt <p> --cwd <workdir> --mode yolo \
    --disallowed-tools "AskUserQuestion EnterPlanMode ExitPlanMode" \
    --output-format stream-json --no-color
```

Per-sample isolation: `ZCODE_DATA_BASE_DIR=<runHome>` plus `HOME`/`USERPROFILE`
repointed at `runHome`, and a one-shot environment whitelist (only `PATH`,
`SYSTEMROOT`, `WINDIR`, `COMSPEC`, `PATHEXT`, `TEMP`, `TMP`, `TMPDIR` pass through).
Workspace and runHome are rebuilt per attempt, so a timed-out rollout never leaks state
into the next attempt.

Retry semantics copy the claude channel shape: `ATTEMPTS` with a fixed backoff
(`RETRY_BACKOFF_S`) and a per-attempt wall timeout. `--resume` is deliberately **not**
used — a timed-out rollout is not a session worth continuing, it is evidence to keep
and replace.

## 5. Memory seeding

The c3 seed materializes workspace `MEMORY.md` into
`<ZCODE_DATA_BASE_DIR>/.zcode/cli/memories/projects/<slug>-<key>/memory/`, using
zcode's own key: `sha256(resolved workspace path)[:16]` and a lowercased sanitized slug
(replicated from `packages/core/src/memory/project-root.ts`;
`# ponytail:` re-verify against that file on any ZCode update or the seed silently
reaches the wrong store).

## 6. Tasks and the offline path

Authored mini-tasks live in `core/harness/benchtasks/<domain>/<name>/` — `task.md` (the
prompt, exactly as given to the CLI), `slots.json` (prompt slots + the **forced
deliverable path**), `fixtures/*` (staged into the workspace as `input/`),
`deliverable.md` (authoring notes). First wave: `device-control/read-write`,
`mcp/wiring`, `network/capability-doc` — three tasks, forced deliverables, no grader
vocabulary in any slot.

Offline (no model, no network, no device) the adapter can be pointed at
`core/harness/zcode_cli_stub.py` via `APRIL_ZCODE_BIN`: the stub mimics the CLI's
contract and writes the forced deliverable, letting the full loop, ledger, and
selection self-checks run.

## 7. Acceptance facts (pinned by `python3 -m core.agent`)

- ledger exactness on full tasks at every dimension count;
- `git -C ZCode status --porcelain` empty — the checkout is byte-for-byte untouched;
- the eight-gate matrix rejects as designed; authored tasks carry no grader words.
