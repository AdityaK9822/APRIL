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
| `facets` | object | no | Facet-grain vector: the 30 standard names from §7, values 0–100. Mutually exclusive with `ocean`; aggregates to OCEAN at load (§7) |

Unknown top-level keys, unknown `ocean` traits, unknown facet names, and unknown
`relationship` keys are refused at load time, and `ocean` and `facets` are mutually
exclusive (§7). A typo must fail loudly rather than silently compile nothing.

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

- All five `ocean` traits present, finite, `0 ≤ v ≤ 100` (a `facets`-grain profile
  resolves `ocean` at load; §7).
- `relationship.friend + relationship.butler == 1` (±0.001) when present.
- `candorFloor` in `[0, 100]` when present.
- Every facet name in the standard 30, every facet value finite and in `[0, 100]`,
  and `ocean`/`facets` mutually exclusive (§7).
- When the vector compiles, the rendered `## Facet directives` section must fit the
  harness ceiling `FACET_DIRECTIVE_CAP` (§7): an over-cap render is a validate error —
  the table is trimmed, never the render truncated.
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

## 7. Facet vectors and the degradation contract

The band tables cover exactly the five OCEAN traits at domain grain. A profile may
also describe itself at the standard 30-facet Big Five grain: `ocean` and `facets`
are mutually exclusive (both describe the same vector, so a contradiction between
them could never be detected — a profile carrying both keys is refused at load, not
merged).

### The 30 facets

Standard NEO-PI-R names, grouped by domain (`FACET_MAP` in
`core/harness/personality.py`). A facet name outside this set is refused at load:

- **Openness**: fantasy, aesthetics, feelings, actions, ideas, values
- **Conscientiousness**: competence, order, dutifulness, achievement_striving,
  self_discipline, deliberation
- **Extraversion**: warmth, gregariousness, assertiveness, activity,
  excitement_seeking, positive_emotions
- **Agreeableness**: trust, straightforwardness, altruism, compliance, modesty,
  tender_mindedness
- **Neuroticism**: anxiety, angry_hostility, depression, self_consciousness,
  impulsiveness, vulnerability

### Aggregation (facet grain → domain grain)

Facet values aggregate to domain scores **before** the untouched kernel,
`personality.ts`, stays the verbatim reference; the bun cross-check keeps pinning
ocean-grain profiles only. # ponytail: the TS archive remains the pre-P6
verbatim text — aggregation is a loader-layer rule here.

- A domain's score is the rounded mean of its **present** facets — `_round`, the
  same JS `Math.round` half-up rule the derived parameters use. A domain that sits
  exactly on a `.5` mean rounds up, and the kernel-purity pin below depends on it.
- Domain scores are placed into the profile's loaded `ocean` vector, so every
  existing mechanism — band directives, derived Voice/Honesty, the PSY lane
  (`psy_mechanism`, `derive()`), ledger arithmetic (`n_dims`), cosine retrieval —
  works unchanged.
- **Full coverage** = at least one facet in each of O, C, E, A, N. Facets may be
  missing *inside* a covered domain (the mean of the present ones still lands).
- **Partial coverage** keeps the loadable vector defined by filling each missing
  domain with the neutral midpoint 50. The fill never reaches compiled text, because
  partial coverage degrades (below); it only keeps temperature math and the transfer
  gate shape-valid. An ocean+facets profile can never exist, so `ocean` is never
  polluted at source.

Kernel purity: a facet profile whose per-domain facet means equal an ocean profile's
five scores produces the **identical** `## Personality (OCEAN)` section text and
identical derived parameters — pinned in `personality.demo()` against
`profiles/ridealong.json` through `.5` means on every domain.

### Compiled shape

A facet vector that compiles renders two facet sections, both **registry-ordered**
(`FACET_MAP` order — JSON key order never leaks into compiled text; duplicate facet
pairs keep the first value):

- `## Facet directives` — behavior, one line per facet whose band is outside `mid`
  (`- name (band): clause`), rendered **above** the data block and only in the
  non-degraded branch. Bands share the domain table's `bandOf` edges; **`mid` emits
  nothing** — the domain directive already owns moderate behavior, and a facet line
  there would only duplicate it and spend persona budget. Example: a vector at 50
  everywhere with `fantasy: 90`, `anxiety: 10` gains exactly two lines
  (`- fantasy (veryHigh): …`, `- anxiety (veryLow): …`). Clauses come from the
  harness-owned `FACET_CONDITIONS` table (all 30 facets × the four extreme bands);
  a missing entry for a rendered band raises — silence would be truncation.
- `## Facets` — the data block, unchanged: one line per facet
  (`- name value (domain)`), inventory, never rules.

Ocean-grain profiles render no facet section at all. The section carries its own
loud ceiling: the rendered directives must fit `FACET_DIRECTIVE_CAP` (3000 chars,
enforced in `validate()` — the table is trimmed, never the render truncated), and
the shipped table's worst case (all 30 facets outside `mid`) renders well under it,
so the "full coverage compiles" contract above cannot break on table growth without
a loud refusal. # ponytail: the cap is a self-judged boundary against this section
becoming a second system prompt; the TS mirror of the table is P7-2, so the bun
cross-check keeps pinning ocean-grain profiles only.

### Degradation (partial facet coverage)

A facet vector that does **not** cover all five domains still **loads and runs**, but
degrades instead of inventing trait directives from domains with no facet evidence:

- `compile_persona` emits the authored c1 text only: identity, role, relationship,
  protocols, `extraRules` — plus the `## Facets` data section. The OCEAN directive
  block, the `## Facet directives` section, derived Voice/Honesty lines, and
  threshold rules are withheld, replaced by a one-line "express the traits above
  through behavior" note.
- `out_of_band()` names the missing domains as the reason.
- `psy_mechanism` returns `""`, so `active_dims` stays `("INV", "DOM")` and the ledger
  keeps `R = 4k`, `P = 3k`. Learning over levers that the compiler cannot express
  would be a silent mismatch.

A many-facet profile approaches the mission persona cap (`tree.PERSONA_CLAUSE_CAP`)
faster than a five-line ocean vector; the P2 cap contract governs unchanged
(cap violation → retry → authored fallback). # ponytail: the real ceiling is the
runtime token budget — revisit when one exists.

Tested-band vectors — every profile whose vector is five OCEAN traits or
full-coverage facets — compile with no code changes. Partial facet coverage and
future extra dimensions are the documented edge.

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

A facet-grain profile swaps `ocean` for `facets` (§7): same file weight, same loader,
zero code — its per-facet directives compile from the harness-owned table, so nothing
is authored per profile. The scale-out contract holds at both grains.

## 9. Reference profiles

| id | O C E A N | Notes |
|---|---|---|
| `april` | 70 90 45 88 20 | Full preset: relationship, candor floor, seven protocols; the TS parity target |
| `user` | 85 64 55 88 44 | Ocean-only (the pattern that proves defaults work) |
| `verifier` | 35 95 45 55 60 | High structure/caution, high candor floor |
| `ridealong` | 60 55 50 85 15 | P4 scale-out proof: low N, high A, mid E; one file, zero code |

Deferred and deliberately absent: a nearest-profile backfill for legacy library
lessons. (Per-facet band directives — `FACET_CONDITIONS`, §7 — landed in P7-1.)
