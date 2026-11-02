# OCEAN profile schema

**Status:** stable as of P4 (2026-11-02). This document is the contract for
`profiles/*.json`; `core/harness/personality.py` is the implementation of record and
`core/harness/personality.ts` is the byte-parity reference it was ported from.

**Scale-out rule:** adding a personality is adding **one JSON file** to `profiles/`.
No Python, no registry entry, no branch. A profile is loaded by filename stem, compiled
into the mission's persona block, and (when it carries no unsupported signal) activates
the PSY dimension. The offline self-checks pin this: no file under `core/harness/` names
`ridealong`, and `profiles/ridealong.json` runs a one-task sweep unchanged.

---

## 1. Location and identity

| Item | Rule |
|---|---|
| Directory | `profiles/` at the repository root (override: `personality.PROFILES_DIR`) |
| Filename | `<id>.json`; the `id` **is** the filename stem |
| `id` key | Optional. If present it must equal the stem, otherwise load fails |
| Encoding | UTF-8 JSON object, no trailing commas |
| Namespacing | A profile-backed sweep writes runs under `…-P<id>` and a per-profile library root `library_root/<id>` |

A profile id is a lowercase, path-safe token: it becomes a run-directory segment and a
library directory name. Use `[a-z0-9_-]+`.

## 2. Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | no | Must equal the filename stem when present |
| `name` | string | yes | Display name; compiled as “You are `<name>`.” |
| `ocean` | object | yes | Exactly the five traits below, each number 0–100 |
| `summary` | string | no | One or two sentences; the persona's self-description |
| `role` | string | no | The job the persona does, compiled as a `Role:` line |
| `relationship` | object | no | `friend` + `butler` weights (must sum to 1), optional `address` / `addressWhen` |
| `candorFloor` | number 0–100 | no | Honesty floor; high agreeableness can never push candor below it (default 70) |
| `protocols` | string[] | no | Non-negotiable rules; compiled into the persona block and machine-checked post-selection where decidable |
| `extraRules` | string[] | no | Authored working rules, compiled verbatim |
| `userContext` | string[] | no | **Refused in committed profiles** — personal facts belong in the git-ignored `.ade/etc/persona-user-context.md` override |
| `facets` | object | no | Deferred 30-facet expansion; values 0–100. Presence degrades the profile (§7) |

Unknown top-level keys, unknown `ocean` traits, and unknown `relationship` keys are
refused at load time. A typo must fail loudly rather than silently compile nothing.

### `ocean`

```json
"ocean": {
  "openness": 70,
  "conscientiousness": 90,
  "extraversion": 45,
  "agreeableness": 88,
  "neuroticism": 20
}
```

All five keys are required, each a finite number in `[0, 100]` (booleans are refused).
Bands are half-open on the lower bound except the first:

| Band | Score |
|---|---|
| `veryLow` | `0 … 20` |
| `low` | `21 … 40` |
| `mid` | `41 … 60` |
| `high` | `61 … 80` |
| `veryHigh` | `81 … 100` |

Each trait × band cell has one authored directive in `DIRECTIVES`; the compiled block
quotes the cell that the score falls into. That table is data — extending it does not
touch the compiler.

### `relationship`

```json
"relationship": {
  "friend": 0.7,
  "butler": 0.3,
  "address": "boss",
  "addressWhen": ["greetings", "task completions", "formal handoffs"]
}
```

`friend + butler` must equal `1` within `0.001`. Omissibility is load-bearing: without a
`relationship` block, `butler` defaults to `0.2` for derivation and the compiled block
omits the relationship section entirely.

## 3. Derived parameters

Derivation is **not** stored in the profile; it is recomputed from `ocean` (plus
`relationship.butler` and `candorFloor`). Rounding is JS `Math.round` (half up), not
Python's banker's rounding — this is load-bearing for APRIL (proactivity 66.5 → 67).

| Parameter | Formula | Used by |
|---|---|---|
| `warmth` | `0.7·A + 0.3·E` | Voice line; PSY voice lever |
| `proactivity` | `0.5·O + 0.3·E + 0.2·C` | Threshold rule at ≥ 60; PSY pacing lever |
| `caution` | `0.7·C + 0.3·N` | Threshold rule at ≥ 60; PSY verification lever |
| `structure` | `C` | Threshold rule at ≥ 70; PSY delegation lever |
| `candor` | `max(candorFloor, 100 − 0.4·A + 0.3·C − 0.1·N)` | Honesty line; PSY candor lever |
| `formality` | `15 + 70·butler + 0.1·C` | Voice line |
| `humor` | `0.4·E + 0.3·O + 0.3·(100 − N) − 20` | Voice line |
| `length` | `E ≥ 70 → long`; `E ≤ 35 → short`; else `medium` | Voice line |
| `temperature` | `0.2 + 0.7·O/100` | Runtime sampling (P5 `toRequest()` semantics) |

Threshold rules (compiled into “Working rules” and re-derived by the post-selection
judge):

| Parameter | Threshold | Rule |
|---|---|---|
| `proactivity` | ≥ 60 | Anticipate the next step briefly; do not start unrequested work |
| `caution` | ≥ 60 | Confirm before irreversible, costly, or outward-facing actions |
| `structure` | ≥ 70 | Follow stated formats exactly; never change requirements silently |

## 4. What a profile compiles to

`compile_persona(profile)` (the TS `buildSystemPrompt`) emits an ordered block:

1. Identity — `You are <name>. <summary>` and an optional `Role:` line.
2. `## Personality (OCEAN)` — five trait directives, one per band cell.
3. `## Relationship with the user` — only when the profile declares one.
4. `## Voice` — derived warmth/formality/humor/length plus the no-filler rule.
5. `## Honesty` — derived candor plus the “say it once” rule.
6. `## Protocols (non-negotiable)` — authored protocols, numbered, plus the override line.
7. `## Working rules` — `extraRules` followed by any triggered threshold rules.
8. `## About the user` — only from a local `userContext` override (never committed).

In the harness this compiled block fills `HarnessPrompts.persona_guidance`. It is
**constraint**, not a learned axis: the blind selector never sees it, and trait
directives never enter the INV/DOM lanes. `psy_mechanism(profile)` separately fills
`psy_levers` from `derive()` parameters only; the PSY lane learns *how* to express the
derived levers and never re-derives traits.

## 5. Validation

`validate(persona)` returns a list of human-readable problems; `profile_from_path`
raises `ValueError` with them joined. Rules:

- All five traits present, finite, `0 ≤ v ≤ 100`.
- `relationship.friend + relationship.butler == 1` (±0.001) when present.
- `candorFloor` in `[0, 100]` when present.
- Every facet value finite and in `[0, 100]`.
- No unknown keys (§2).
- No `userContext` in a committed profile (`allow_user_context=False` is the default).

## 6. Transfer gate (library retrieval)

`similarity(a, b)` is cosine over the `ocean/100` vector. The library ranks lessons for
the active profile by this score and applies `SIMILARITY_FLOOR = 0.95`: a lesson from a
sufficiently similar persona loads normally; a below-floor lesson loads only when it is
marked `transferable: true`. Lessons distilled purely from PSY edits are marked
`transferable: false`, because they encode one persona's expression of a lever.

Committed profiles at the floor (values are stable, pinned by self-checks):

| Pair | Cosine | Loads without `transferable` |
|---|---|---|
| april ↔ ridealong | 0.9787 | yes |
| user ↔ ridealong | 0.9777 | yes |
| april ↔ user | 0.9667 | yes |
| april ↔ verifier | 0.9111 | no |

## 7. Degradation contract (out-of-band vectors)

The band tables cover exactly the five OCEAN traits. A profile that carries signal
outside that grid — today, `facets` — is still **loadable** and still runs; it degrades
instead of failing or lying:

- `compile_persona` emits the authored c1 text only: identity, role, relationship,
  protocols, `extraRules`. The OCEAN directive block, derived Voice/Honesty lines, and
  threshold rules are withheld, replaced by a one-line “express the traits above through
  behavior” note.
- `psy_mechanism` returns `""`, so `active_dims` stays `("INV", "DOM")` and the ledger
  keeps `R = 4k`, `P = 3k`. Learning over levers that the compiler cannot express would
  be a silent mismatch.
- The ceiling is marked in code with `# ponytail:` naming the deferred 30-facet
  expansion (`personality.out_of_band`).

Tested-band vectors — every profile whose vector is five OCEAN traits — compile with no
code changes. Facets and future extra dimensions are the documented edge.

## 8. Adding a profile

1. Drop `profiles/<id>.json` (copy the minimal shape below; `id` optional).
2. Run `python3 -m core.agent` — the offline self-checks load every committed profile,
   validate it, and check the facet/userContext gates.
3. Optionally exercise it: `run_sweep_zcode(..., profiles=("<id>",))` writes
   `…-P<id>` runs and a separate `library_root/<id>`.

```json
{
  "name": "Ridealong",
  "summary": "A calm, friendly observer who explains the work as it happens.",
  "ocean": {
    "openness": 60,
    "conscientiousness": 55,
    "extraversion": 50,
    "agreeableness": 85,
    "neuroticism": 15
  },
  "extraRules": ["Narrate what you are about to do in one short line."]
}
```

## 9. Reference profiles

| id | O C E A N | Notes |
|---|---|---|
| `april` | 70 90 45 88 20 | Full preset: relationship, candor floor, seven protocols; the TS parity target |
| `user` | 85 64 55 88 44 | Ocean-only (the pattern that proves defaults work) |
| `verifier` | 35 95 45 55 60 | High structure/caution, high candor floor |
| `ridealong` | 60 55 50 85 15 | P4 scale-out proof: low N, high A, mid E; one file, zero code |

Deferred and deliberately absent: 30-facet Big Five expansion (§7), and a
nearest-profile backfill for legacy library lessons.
