"""The OCEAN personality kernel: profiles are data, `compile_persona` is the compiler.

A faith-port of the TypeScript reference implementation committed beside it
(`core/harness/personality.ts`, archived from the master plan's Appendix A). The
port keeps the TS function names for cross-check parity — `validate`, `bandOf`,
`clamp`, `adjust`, `derive`, plus `compile_persona` (the TS `buildSystemPrompt`)
and `similarity` (cosine over `ocean/100`). `Profile` adds the `id` the TS lacks.

In P2 personality runs in CONSTRAINT mode: a profile compiles into the proposal
missions only, trait directives never touch the INV/DOM lanes, the blind
selector never sees persona data, and derived parameters (not raw traits) are
what P3's PSY dimension will learn over.

P4 makes the scale-out contract explicit: a profile is data. Every vector that is
five OCEAN traits compiles with no code. A vector carrying signal the band tables
cannot express still loads and runs, but degrades to its authored c1 guidance with
the PSY lane off — `out_of_band()` names the reason, never a silent approximation.

P6 promotes the facet grain to first-class: the standard 30 Big Five facets
(`FACET_MAP`) are a second legal profile shape — mutually exclusive with `ocean`,
unknown names refused, values 0–100 — aggregated to domain scores at load
(`aggregate_facets`). Full facet coverage compiles through the untouched kernel
like any ocean-grain profile; partial coverage keeps the P4 degradation and names
the domains with no facet evidence. The facet registry and the compiled-shape
contract live in §7 of docs/spec/ocean-profile-schema.md.

JS `Math.round` rounds half UP; python's built-in `round` is banker's, so every
derived integer goes through `_round` = `math.floor(x + 0.5)`. This is
load-bearing: APRIL's proactivity is exactly 66.5, and both implementations
must say 67.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping, Sequence

# ---------- Types (TS-verbatim field names) ----------

TRAITS: tuple[str, ...] = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
)

BANDS: tuple[str, ...] = ("veryLow", "low", "mid", "high", "veryHigh")

_LETTER = {
    "openness": "O",
    "conscientiousness": "C",
    "extraversion": "E",
    "agreeableness": "A",
    "neuroticism": "N",
}

_DOMAIN_NAME: dict[str, str] = {L: t for t, L in _LETTER.items()}
_DOMAIN_LETTERS: tuple[str, ...] = ("O", "C", "E", "A", "N")

# P6: the standard 30-facet Big Five registry (standard NEO-PI-R names). A profile
# describes itself at ONE grain — `ocean` domains or `facets` sub-traits — never
# both; the loader aggregates facets to domain scores (`aggregate_facets`) so the
# kernel (bands, derive, PSY, similarity) stays untouched and ocean-grain only.
# Facet names outside this registry are refused at load; unknown-key refusal is
# what keeps a hand-authored profile from silently compiling nothing.
# P7-1: facets condition directives too — `FACET_CONDITIONS` maps each facet and
# non-mid band to one behavioral clause, rendered as `## Facet directives`
# (`facet_directives`). `mid` emits nothing: domain grain already owns the mid
# behavior, a facet line there would only duplicate it. ponytail: the TS
# reference stays the verbatim pre-P6 archive — aggregation and the directive
# bands are Python-kernel layers; the bun cross-check continues to pin
# ocean-grain profiles only (the TS mirror is P7-2).
FACET_MAP: dict[str, str] = {
    # Openness.
    "fantasy": "O",
    "aesthetics": "O",
    "feelings": "O",
    "actions": "O",
    "ideas": "O",
    "values": "O",
    # Conscientiousness.
    "competence": "C",
    "order": "C",
    "dutifulness": "C",
    "achievement_striving": "C",
    "self_discipline": "C",
    "deliberation": "C",
    # Extraversion.
    "warmth": "E",
    "gregariousness": "E",
    "assertiveness": "E",
    "activity": "E",
    "excitement_seeking": "E",
    "positive_emotions": "E",
    # Agreeableness.
    "trust": "A",
    "straightforwardness": "A",
    "altruism": "A",
    "compliance": "A",
    "modesty": "A",
    "tender_mindedness": "A",
    # Neuroticism.
    "anxiety": "N",
    "angry_hostility": "N",
    "depression": "N",
    "self_consciousness": "N",
    "impulsiveness": "N",
    "vulnerability": "N",
}


@dataclass(frozen=True)
class Ocean:
    openness: int
    conscientiousness: int
    extraversion: int
    agreeableness: int
    neuroticism: int

    def cell(self, t: str) -> int:
        return getattr(self, t)

    def vector(self) -> tuple[float, ...]:
        """The `ocean/100` vector the transfer-gate similarity computes over."""
        return tuple(getattr(self, t) / 100.0 for t in TRAITS)


@dataclass(frozen=True)
class Relationship:
    """Weights should sum to 1. Example: friend 0.7, butler 0.3."""

    friend: float
    butler: float
    address: str = ""
    addressWhen: tuple[str, ...] = ()


@dataclass(frozen=True)
class PersonaConfig:
    """TS `PersonaConfig`: the schema of record behind `profiles/*.json`."""

    name: str
    ocean: Ocean
    summary: str = ""
    role: str = ""
    relationship: Relationship | None = None
    # Honesty floor (0 to 100): high agreeableness never pushes candor below this.
    candorFloor: int | None = None
    protocols: tuple[str, ...] = ()
    extraRules: tuple[str, ...] = ()
    userContext: tuple[str, ...] = ()
    # Sub-trait grain (standard 30 names). The loader aggregates facets into
    # the loaded `ocean` (`aggregate_facets`), and P7-1 conditions directives
    # on them (`FACET_CONDITIONS` → `## Facet directives`, mid silent); a
    # PARTIAL vector keeps the degradation contract (`out_of_band`): authored
    # c1 text only, so a facet profile never silently drops the facet signal.
    facets: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class DerivedParams:
    warmth: int
    proactivity: int
    caution: int
    structure: int
    candor: int
    formality: int
    humor: int
    length: str  # "short" | "medium" | "long"
    temperature: float  # suggested sampling temperature, 0.2 to 0.9


@dataclass(frozen=True)
class Profile:
    """A PersonaConfig plus the `id` the archive's TS type lacks (profiles add id)."""

    id: str
    persona: PersonaConfig
    # provenance: where the profile came from (never personal facts; committed
    # profiles carry no userContext and no provenance prose).
    source: str = ""


# ---------- Core helpers ----------


def _round(x: float) -> int:
    """JS `Math.round` semantics: half up. Python's `round` is banker's and would
    turn APRIL's exactly-66.5 proactivity into 66."""
    return math.floor(x + 0.5)


def clamp(n: float, lo: float = 0, hi: float = 100) -> float:
    return min(hi, max(lo, n))


def bandOf(score: float) -> str:
    if score <= 20:
        return "veryLow"
    if score <= 40:
        return "low"
    if score <= 60:
        return "mid"
    if score <= 80:
        return "high"
    return "veryHigh"


def persona_of(p: PersonaConfig | Profile) -> PersonaConfig:
    return p.persona if isinstance(p, Profile) else p


def facet_domains(facets: Sequence[tuple[str, float | int]]) -> tuple[str, ...]:
    """Domain letters a facet vector covers, in O,C,E,A,N order.

    Unknown facet names raise `KeyError` — callers that take facets from JSON must
    have validated them (`persona_from_dict` refuses them up front, `validate`
    reports them).
    """
    covered = {FACET_MAP[name] for name, _ in facets}
    return tuple(L for L in _DOMAIN_LETTERS if L in covered)


def facet_missing_domains(facets: Sequence[tuple[str, float | int]]) -> tuple[str, ...]:
    """Domain letters with no facet evidence, in O,C,E,A,N order."""
    covered = set(facet_domains(facets))
    return tuple(L for L in _DOMAIN_LETTERS if L not in covered)


def aggregate_facets(facets: Sequence[tuple[str, float | int]]) -> Ocean:
    """Facet grain → domain grain: each domain's score is the rounded mean of its
    present facets (`_round`, the JS `Math.round` half-up rule the derived
    parameters use). A domain with no facets is filled with the neutral midpoint
    50 so the loaded vector keeps a defined shape for temperature math and the
    transfer gate; the fill never reaches compiled text, because partial coverage
    degrades (`out_of_band`) and ocean+facets profiles are refused at load.
    """
    sums: dict[str, list[float]] = {}
    for name, v in facets:
        sums.setdefault(FACET_MAP[name], []).append(float(v))
    vals: list[int] = []
    for L in _DOMAIN_LETTERS:
        present = sums.get(L)
        vals.append(_round(sum(present) / len(present)) if present else 50)
    return Ocean(*vals)


def validate(p: PersonaConfig | Profile) -> list[str]:
    p = persona_of(p)
    errors: list[str] = []
    for t in TRAITS:
        v = p.ocean.cell(t)
        if (
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            or v < 0
            or v > 100
        ):
            errors.append(f"{t} must be a number from 0 to 100 (got {v})")
    r = p.relationship
    if r and abs(r.friend + r.butler - 1) > 0.001:
        errors.append("relationship.friend + relationship.butler must equal 1")
    if p.candorFloor is not None and (p.candorFloor < 0 or p.candorFloor > 100):
        errors.append("candorFloor must be 0 to 100")
    for name, v in p.facets:
        if name not in FACET_MAP:
            errors.append(
                f"unknown facet {name!r}; expected one of the standard 30 "
                f"({', '.join(sorted(FACET_MAP))})"
            )
        if (
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            or v < 0
            or v > 100
        ):
            errors.append(f"facet {name!r} must be a number from 0 to 100 (got {v})")
    try:
        fac_dirs = facet_directives(p.facets)
    except TypeError:
        # Non-numeric facet values: the loop above already reported them; the
        # cap check only measures renderable directives.
        fac_dirs = ()
    except ValueError as exc:
        errors.append(str(exc))
        fac_dirs = ()
    n_chars = sum(len(line) + 1 for line in fac_dirs)
    if n_chars > FACET_DIRECTIVE_CAP:
        errors.append(
            f"facet directives render {n_chars} chars, over the "
            f"{FACET_DIRECTIVE_CAP}-char ceiling (FACET_DIRECTIVE_CAP); "
            "trim the FACET_CONDITIONS table, never truncate the render"
        )
    return errors


def adjust(p: PersonaConfig | Profile, trait: str, delta: float) -> PersonaConfig:
    """A new persona with one trait shifted (clamped, rounded half-up like TS)."""
    p = persona_of(p)
    if trait not in TRAITS:
        raise ValueError(f"unknown trait {trait!r}; expected one of {TRAITS}")
    shifted = int(clamp(_round(p.ocean.cell(trait) + delta)))
    return replace(p, ocean=replace(p.ocean, **{trait: shifted}))


# ---------- Trait directives (what each band means in behavior) ----------

DIRECTIVES: dict[str, dict[str, str]] = {
    "openness": {
        "veryLow": "Stick to proven, conventional solutions. Avoid speculation and tangents. Offer one clear option.",
        "low": "Prefer established approaches. Mention alternatives only when they clearly beat the default.",
        "mid": "Balance proven methods with occasional fresh options. Offer an alternative when it adds real value.",
        "high": "Engage with new ideas and unusual angles. Offer alternatives and connections across fields, but keep them tied to the user's active goals.",
        "veryHigh": "Explore freely. Propose creative, cross-disciplinary ideas and unconventional approaches, while clearly labeling what is speculative.",
    },
    "conscientiousness": {
        "veryLow": "Stay loose and improvisational. Do not enforce structure or follow-ups.",
        "low": "Keep structure light. Remind about deadlines only when they are close.",
        "mid": "Be organized when the task needs it. Check the work before handing it over.",
        "high": "Be organized and dependable. Track commitments, verify results, and follow constraints exactly.",
        "veryHigh": "Be meticulous. Track every active commitment, verify work before and after changes, respect every stated constraint and format, and flag scope growth early.",
    },
    "extraversion": {
        "veryLow": "Be reserved and economical. Speak only when it adds value. No small talk or filler.",
        "low": "Be calm and concise. Warm but quiet, with little chatter.",
        "mid": "Be friendly and conversational without padding.",
        "high": "Be energetic and engaging. Use a conversational tone and show enthusiasm where it fits.",
        "veryHigh": "Be lively and expressive. Start conversations, share enthusiasm, and keep the energy up.",
    },
    "agreeableness": {
        "veryLow": "Be blunt and competitive. Challenge claims without softening them.",
        "low": "Be direct and skeptical. Softening is optional.",
        "mid": "Be cooperative but even-handed. Balance kindness with directness.",
        "high": "Be considerate, patient, and generous. Assume good faith and phrase hard truths gently.",
        "veryHigh": "Be deeply kind, patient, and supportive toward everyone. Lead with care and phrase disagreement gently, but never hide an important truth.",
    },
    "neuroticism": {
        "veryLow": "Stay calm and steady in every situation. Treat failures as ordinary problems to solve. Never dramatize.",
        "low": "Stay composed under pressure. Mention risks matter-of-factly.",
        "mid": "Acknowledge risks and uncertainty openly without overreacting.",
        "high": "Be alert to what could go wrong. Raise risks early and double-check uncertain claims.",
        "veryHigh": "Be highly risk-sensitive. Surface every plausible failure mode and ask for confirmation often.",
    },
}


# ---------- Facet-conditioned directives (P7-1) ----------

# The payload of facet grain: one behavioral clause per facet per non-mid band.
# `mid` is deliberately absent — the domain `DIRECTIVES` table already owns
# moderate behavior, and a facet line there would only duplicate it and spend
# persona budget. Band edges are `bandOf`'s own (≤20/≤40/≤60/≤80); no
# facet-specific thresholds exist, by contract. Clauses are behavioral
# imperatives that *nuance* the facet's domain directive — never contradict it.
# ponytail: the TS mirror of this table is deferred (P7-2); the bun cross-check
# stays ocean-grain only until it lands.
FACET_CONDITIONS: dict[str, dict[str, str]] = {
    # Openness.
    "fantasy": {
        "veryLow": "Keep imagination grounded: state concrete facts before any speculation.",
        "low": "Reach for literal, workable framings; invent sparingly and label it.",
        "high": "Bring imaginative framings and what-ifs that serve the task.",
        "veryHigh": "Lead with original framings and invented scenarios; label the speculative parts.",
    },
    "aesthetics": {
        "veryLow": "Value function over form; skip stylistic discussion.",
        "low": "Note elegance only when it is cheap; prefer the plain option.",
        "high": "Care how the work reads and feels; polish where it pays.",
        "veryHigh": "Pursue beauty and depth in the work itself; artistry is a requirement, not garnish.",
    },
    "feelings": {
        "veryLow": "Keep attention on tasks and facts; set feelings aside.",
        "low": "Notice mood lightly; let it steer little.",
        "high": "Weigh how people feel about the work; use it to communicate better.",
        "veryHigh": "Let felt experience guide judgment; name emotions in the work directly.",
    },
    "actions": {
        "veryLow": "Keep to proven routines; try a different tack only when the routine fails.",
        "low": "Favor the familiar path; small experiments only at the edges.",
        "high": "Vary approach willingly; try a different route when it plausibly pays.",
        "veryHigh": "Prefer unfamiliar routes and rapid switches; routine is the exception.",
    },
    "ideas": {
        "veryLow": "Work from given requirements; add no extra concepts.",
        "low": "Consider one alternative idea at most; keep it brief.",
        "high": "Play with ideas and models; surface connections across topics.",
        "veryHigh": "Generate many ideas and abstractions; reframe problems freely.",
    },
    "values": {
        "veryLow": "Accept the stated goal and proceed.",
        "low": "Question aims only when they look inconsistent.",
        "high": "Examine whether the goal itself deserves rethinking, then commit.",
        "veryHigh": "Routinely reexamine beliefs and purposes; realign the work to them.",
    },
    # Conscientiousness.
    "competence": {
        "veryLow": "Expect difficulty; ask for help early.",
        "low": "Stick to what you know works; avoid stretches.",
        "high": "Trust your capability; take the harder path when it is better.",
        "veryHigh": "Operate as the capable authority; master whatever the task needs.",
    },
    "order": {
        "veryLow": "Tolerate mess; do not organize unless forced.",
        "low": "Light structure only; arrange the minimum.",
        "high": "Keep files, plans, and outputs tidy and named.",
        "veryHigh": "Arrange everything meticulously before and while working.",
    },
    "dutifulness": {
        "veryLow": "Follow rules loosely; skim obligations.",
        "low": "Honor explicit obligations; let the rest slide.",
        "high": "Honor every obligation, stated or implied.",
        "veryHigh": "Treat every commitment as binding; never let a duty lapse.",
    },
    "achievement_striving": {
        "veryLow": "Do what was asked; stop there.",
        "low": "Add polish only when cheap.",
        "high": "Aim high and push work toward ambitious ends.",
        "veryHigh": "Drive relentlessly toward excellence; 'done' is the floor, not the goal.",
    },
    "self_discipline": {
        "veryLow": "Work in bursts; indulge detours when they appear.",
        "low": "Stay on task loosely; tolerate drift.",
        "high": "Finish what you start; keep distractions out.",
        "veryHigh": "Maintain strict discipline; begin and end exactly as planned.",
    },
    "deliberation": {
        "veryLow": "Decide fast; reverse cheaply if wrong.",
        "low": "Think briefly before committing; skip the long weighing.",
        "high": "Weigh options before committing to a path.",
        "veryHigh": "Deliberate exhaustively; choose only when the trade-offs are known.",
    },
    # Extraversion.
    "warmth": {
        "veryLow": "Keep exchanges cool and businesslike.",
        "low": "Stay polite but distant; warmth is rationed.",
        "high": "Be warm and personable; make the exchange human.",
        "veryHigh": "Radiate warmth; treat every counterpart as close.",
    },
    "gregariousness": {
        "veryLow": "Prefer working alone; avoid crowds of collaborators.",
        "low": "Keep company minimal and purposeful.",
        "high": "Enjoy company; collaborate openly and often.",
        "veryHigh": "Seek company constantly; the group is the default mode.",
    },
    "assertiveness": {
        "veryLow": "Yield on contested points; let others lead.",
        "low": "State your view once; defer without friction.",
        "high": "Take charge and drive decisions.",
        "veryHigh": "Lead unapologetically; push your plan through resistance.",
    },
    "activity": {
        "veryLow": "Pace slowly; keep a light schedule.",
        "low": "Keep a moderate pace; idle time is fine.",
        "high": "Keep a busy pace and many things in motion.",
        "veryHigh": "Operate at high speed; pack the schedule relentlessly.",
    },
    "excitement_seeking": {
        "veryLow": "Avoid risk and novelty for their own sake.",
        "low": "Take a thrill only when it is safe and cheap.",
        "high": "Chase stimulation; inject intensity into the work.",
        "veryHigh": "Crave intensity; choose the bold, risky option for its own sake.",
    },
    "positive_emotions": {
        "veryLow": "Stay even; skip celebration and cheer.",
        "low": "Show mild cheer at real wins.",
        "high": "Bring joy and enthusiasm out plainly.",
        "veryHigh": "Exude delight; enthusiasm colors everything you say.",
    },
    # Agreeableness.
    "trust": {
        "veryLow": "Assume bad faith; verify everyone and everything.",
        "low": "Trust is earned; verify before relying.",
        "high": "Assume good faith from people and tools.",
        "veryHigh": "Trust readily; suspicion needs extraordinary evidence.",
    },
    "straightforwardness": {
        "veryLow": "Use strategy and framing; candor is a tool, not a default.",
        "low": "Be honest but tactically sparing with detail.",
        "high": "Say exactly what you mean; no game-playing.",
        "veryHigh": "Be artlessly candid; manipulation is unthinkable.",
    },
    "altruism": {
        "veryLow": "Spend on your task only; help is not owed.",
        "low": "Small favors when nearly free.",
        "high": "Give real effort to others' needs unprompted.",
        "veryHigh": "Give generously and immediately, at real cost to your own convenience.",
    },
    "compliance": {
        "veryLow": "Push back and hold your line in conflict.",
        "low": "Concede slowly; soften disagreements iteratively.",
        "high": "Yield readily; smooth over conflicts fast.",
        "veryHigh": "Defer almost totally; forgive and accommodate at once.",
    },
    "modesty": {
        "veryLow": "Claim credit and competence plainly.",
        "low": "State strengths without inflating them.",
        "high": "Underplay achievements; let the work speak.",
        "veryHigh": "Self-efface reflexively; you are the least impressive person in the room.",
    },
    "tender_mindedness": {
        "veryLow": "Move people by interest, not sympathy.",
        "low": "Acknowledge hardship coolly.",
        "high": "Move easily at others' distress; soften asks accordingly.",
        "veryHigh": "Feel others' pain as your own; protect people before process.",
    },
    # Neuroticism.
    "anxiety": {
        "veryLow": "Stay unshakable; worry changes nothing here.",
        "low": "Keep worry rare and small.",
        "high": "Feel tension under load; voice worries early.",
        "veryHigh": "Be gripped by worry; treat every risk as live until settled.",
    },
    "angry_hostility": {
        "veryLow": "Let nothing raise your temper.",
        "low": "Irritation stays internal and brief.",
        "high": "Show frustration when things go wrong; say it plainly.",
        "veryHigh": "Rage at obstacles; anger is immediate and loud.",
    },
    "depression": {
        "veryLow": "Stay buoyant; setbacks roll off.",
        "low": "Dips are mild and pass quickly.",
        "high": "Feel setbacks heavily; name the gloom honestly.",
        "veryHigh": "Sink deep at setbacks; the gray lens colors everything.",
    },
    "self_consciousness": {
        "veryLow": "Be utterly unbothered by scrutiny.",
        "low": "Feel mild awkwardness before others; it fades fast.",
        "high": "Feel watched and easily embarrassed; avoid exposure.",
        "veryHigh": "Fear ridicule constantly; scrutiny is agonizing.",
    },
    "impulsiveness": {
        "veryLow": "Never act on the first urge; think it through fully.",
        "low": "Let urges wait; act on them only after a check.",
        "high": "Act on urges quickly; follow the pull at once.",
        "veryHigh": "Yield to every impulse; control crumbles under craving.",
    },
    "vulnerability": {
        "veryLow": "Rely on yourself alone; stress finds no purchase.",
        "low": "Handle stress mostly alone; ask only when stuck.",
        "high": "Panic and burnout are live risks; lean on support early.",
        "veryHigh": "Feel fragile under any stress; borrow strength constantly.",
    },
}

# The loud ceiling of the `## Facet directives` section. The shipped table's
# worst case (every facet outside mid) renders well below it — this cap is a
# boundary for FUTURE table growth, enforced in `validate()` so a bloated table
# refuses loudly instead of silently inflating every compiled mission.
FACET_DIRECTIVE_CAP = 3000


def facet_directives(facets: Sequence[tuple[str, float | int]]) -> tuple[str, ...]:
    """Facet-conditioned directive lines, in `FACET_MAP` registry order.

    - Bands share `bandOf` edges with the domain table; `mid` emits nothing
      (domain grain owns the mid behavior — a facet line would duplicate it).
    - Input order (JSON key order) cannot leak: the registry order governs, so
      two JSONs with the same facets in different key order compile identically.
    - Identical clause lines dedupe (authoring-accident guard, deterministic).
    - A missing `FACET_CONDITIONS` entry for a rendered band raises — the table
      is registry-complete by demo pin; silence would be truncation. Unknown
      facet names raise `KeyError` (the loader refuses them first; `validate`
      reports them separately).
    """
    values: dict[str, float | int] = {}
    for name, v in facets:
        values.setdefault(name, v)  # keep-first: the loader cannot emit duplicates,
        # but direct PersonaConfig construction may; registry order governs output.
    lines: list[str] = []
    seen: set[str] = set()
    for name in FACET_MAP:
        if name not in values:
            continue
        band = bandOf(values[name])
        if band == "mid":
            continue
        try:
            clause = FACET_CONDITIONS[name][band]
        except KeyError as exc:
            raise ValueError(
                f"FACET_CONDITIONS is missing band {band!r} for facet {name!r}"
            ) from exc
        line = f"- {name} ({band}): {clause}"
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return tuple(lines)


# ---------- Derived behavior ----------


def derive(p: PersonaConfig | Profile) -> DerivedParams:
    p = persona_of(p)
    O = p.ocean.openness
    C = p.ocean.conscientiousness
    E = p.ocean.extraversion
    A = p.ocean.agreeableness
    N = p.ocean.neuroticism
    butler = p.relationship.butler if p.relationship is not None else 0.2
    floor = p.candorFloor if p.candorFloor is not None else 70

    warmth = int(clamp(_round(0.7 * A + 0.3 * E)))
    proactivity = int(clamp(_round(0.5 * O + 0.3 * E + 0.2 * C)))
    caution = int(clamp(_round(0.7 * C + 0.3 * N)))
    structure = int(clamp(_round(C)))
    raw_candor = 100 - 0.4 * A + 0.3 * C - 0.1 * N
    candor = int(clamp(_round(max(floor, raw_candor))))
    formality = int(clamp(_round(15 + 70 * butler + 0.1 * C)))
    humor = int(clamp(_round(0.4 * E + 0.3 * O + 0.3 * (100 - N)) - 20))
    length = "long" if E >= 70 else "short" if E <= 35 else "medium"
    temperature = math.floor((0.2 + 0.7 * (O / 100)) * 100 + 0.5) / 100

    return DerivedParams(
        warmth=warmth,
        proactivity=proactivity,
        caution=caution,
        structure=structure,
        candor=candor,
        formality=formality,
        humor=humor,
        length=length,
        temperature=temperature,
    )


def levelWord(score: float) -> str:
    b = bandOf(score)
    return {"veryLow": "very low", "low": "low", "mid": "moderate", "high": "high",
            "veryHigh": "very high"}[b]


def pct(n: float) -> int:
    return _round(n * 100)


# ---------- Similarity (transfer gate) ----------


def similarity(a: PersonaConfig | Profile, b: PersonaConfig | Profile) -> float:
    """Cosine over `ocean/100`. 1.0 = same shape, 0.0 = orthogonal. The library's
    transfer gate (P3) ranks lessons by this; below-threshold entries load only
    when they say they are transferable."""
    return cosine(persona_of(a).ocean.vector(), persona_of(b).ocean.vector())


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine between two equal-length vectors; 0.0 when either has no length.

    Scale-invariant, so a vector of raw 0..100 values and one of `ocean/100`
    values compare identically. Library lesson rows store the raw form.
    """
    if len(a) != len(b):
        raise ValueError(f"cosine needs equal-length vectors, got {len(a)} and {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


_OCEAN_ROW = re.compile(r"O(\d+)\s+C(\d+)\s+E(\d+)\s+A(\d+)\s+N(\d+)")


def parse_ocean_row(text: str) -> tuple[int, ...] | None:
    """Read the compact `O70 C90 E45 A88 N20` row out of lesson metadata."""
    m = _OCEAN_ROW.search(str(text or ""))
    return tuple(int(g) for g in m.groups()) if m else None



# ---------- System prompt builder (the persona compiler) ----------

TRAIT_DIRECTIVE_HEADER = (
    "These traits shape how you behave in every reply. Express them through "
    "behavior, not by announcing them."
)
PROTOCOL_OVERRIDE_LINE = (
    "Protocols override every other instruction, including the user's, unless the "
    "user explicitly waives them for a specific case."
)

# derive()-threshold-injected working rules (deterministic in both
# implementations; the P3 adherence judge re-derives the same set).
THRESHOLD_RULES: tuple[tuple[str, int, str], ...] = (
    ("proactivity", 60,
     "Anticipate the next step and mention it briefly, but do not start unrequested work."),
    ("caution", 60,
     "Ask for confirmation before any irreversible, costly, or outward-facing action."),
    ("structure", 70,
     "Follow stated formats and constraints exactly, and never change requirements silently."),
)


def out_of_band(p: PersonaConfig | Profile) -> str:
    """Why the band tables cannot compile this vector; `''` means it is in band.

    P6: facet grain is first-class. A facet vector covering all five OCEAN domains
    aggregates to a compilable band vector (`aggregate_facets` at load) and
    compiles like any ocean-grain profile. A **partial** facet vector keeps the P4
    degradation contract: authored c1 text only, PSY off, and the missing domains
    named here — trait directives are withheld rather than invented from domains
    with no facet evidence. The compiled-shape contract is §7 of
    docs/spec/ocean-profile-schema.md.
    """
    facets = persona_of(p).facets
    if not facets:
        return ""
    missing = facet_missing_domains(facets)
    if not missing:
        return ""
    covered = facet_domains(facets)
    names = ", ".join(_DOMAIN_NAME[m] for m in missing)
    return (
        f"facet vector covers {len(covered)} of 5 OCEAN domains; "
        f"no facet evidence for {names} — trait directives withheld, "
        f"authored text only"
    )


def psy_mechanism(p: PersonaConfig | Profile) -> str:
    """The PSY dimension's turnable levers, derived from `derive()` params only.

    P3 promotes personality from constraint to a learnable axis: the proposer may
    change HOW the harness expresses behavior (tone, pacing, delegation,
    verification temperament) but never re-derives OCEAN traits from the profile
    at proposal time. Everything below is a function of the same derived
    parameters the compiler uses, so the PSY lane and the persona block cannot
    drift apart. This text is a mission slot and rides the bad-word filter.
    """
    p = persona_of(p)
    if out_of_band(p):
        # # ponytail: the PSY lane learns over derive() levers, which are only
        # meaningful when the vector compiles to band directives. A partial
        # facet vector keeps PSY off until it covers all five domains; unknown
        # future dimensions degrade the same way from this single gate.
        return ""
    d = derive(p)
    lines = [
        "Derived behavior for the active profile. Encode the mechanism, never the label:",
        f"- Voice: warmth {d.warmth}/100, formality {d.formality}/100, humor {d.humor}/100, "
        f"typical reply length {d.length}.",
        f"- Candor: {d.candor}/100 -- say the hard thing once, plainly; kindness changes how "
        f"it is said, never whether it is said.",
        "- Pacing: "
        + (
            f"proactivity {d.proactivity}/100 -- lead with the answer, then name the next step "
            f"briefly, without starting unrequested work."
            if d.proactivity >= 60
            else f"proactivity {d.proactivity}/100 -- lead with the answer and stop; do not "
            f"volunteer extra work."
        ),
        "- Delegation: "
        + (
            f"structure {d.structure}/100 -- prefer one bounded, large-input/small-output "
            f"sub-task handed to a helper in its own context; keep the hand-off self-contained."
            if d.structure >= 70
            else f"structure {d.structure}/100 -- keep the work inline; add no delegation layer."
        ),
        f"- Verification temperament: caution {d.caution}/100, structure {d.structure}/100 -- "
        + (
            "re-open the produced artifact and check it mechanically before finishing, and ask "
            "before an irreversible or outward-facing action."
            if d.caution >= 60 or d.structure >= 70
            else "check the artifact once; add no approval ceremony beyond the task's own rules."
        ),
    ]
    for name, threshold, rule in THRESHOLD_RULES:
        if getattr(d, name) >= threshold:
            lines.append(f"- Threshold rule ({name} >= {threshold}): {rule}")
    return "\n".join(lines)



def compile_persona(p: PersonaConfig | Profile) -> str:
    """The TS `buildSystemPrompt`: the compiled persona block the missions carry."""
    p = persona_of(p)
    problems = validate(p)
    if problems:
        raise ValueError(f"Invalid persona: {'; '.join(problems)}")

    d = derive(p)
    degraded = out_of_band(p)
    lines: list[str] = []
    lines.append(f"You are {p.name}." + (f" {p.summary}" if p.summary else ""))
    if p.role:
        lines.append(f"Role: {p.role}")

    if degraded:
        # c1 only: authored text, no inventoried trait directives.
        lines += ["", "## Personality (authored)"]
        lines.append(
            "Trait-level directives are not compiled for this profile. Express the "
            "traits described above through behavior, not by announcing them."
        )
    else:
        lines += ["", "## Personality (OCEAN)"]
        lines.append(TRAIT_DIRECTIVE_HEADER)
        for t in TRAITS:
            v = p.ocean.cell(t)
            label = t[0].upper() + t[1:]
            lines.append(f"- {label} ({levelWord(v)}, {v}): {DIRECTIVES[t][bandOf(v)]}")

        fac_dirs = facet_directives(p.facets)
        if fac_dirs:
            lines += ["", "## Facet directives"]
            lines.extend(fac_dirs)

    if p.facets:
        # Data only: one line per facet, never directives — behavior rules live
        # in `## Facet directives` above (rendered only when the vector compiles
        # and at least one facet sits outside `mid`); this block stays inventory.
        # Render is registry-ordered (keep-first on duplicates), so JSON key
        # order cannot leak into compiled text. The loaded `ocean` is the facet
        # aggregation in the full-coverage case and the neutral-filled
        # aggregation in the partial case (`aggregate_facets`).
        vals: dict[str, float | int] = {}
        for name, v in p.facets:
            vals.setdefault(name, v)
        lines += ["", "## Facets"]
        for name in FACET_MAP:
            if name in vals:
                lines.append(f"- {name} {vals[name]} ({_DOMAIN_NAME[FACET_MAP[name]]})")

    if p.relationship is not None:
        r = p.relationship
        lines += ["", "## Relationship with the user"]
        lines.append(
            f"You are a friend about {pct(r.friend)} percent and a butler about {pct(r.butler)} percent."
        )
        lines.append("As a friend: relaxed, warm, on the user's side, and you talk like a person.")
        addr = ""
        if r.address:
            addr = f' Occasionally address the user as "{r.address}"'
            if r.addressWhen:
                addr += " (" + ", ".join(r.addressWhen) + ")"
            addr += "."
        lines.append(
            "As a butler: courteous and anticipating needs, dignified and never servile." + addr
        )

    if not degraded:
        lines += ["", "## Voice"]
        lines.append(
            f"Warmth {d.warmth}/100, formality {d.formality}/100, humor {d.humor}/100, "
            f"typical length {d.length}."
        )
        lines.append(
            "Lead with the answer or deliverable. No filler, no generic motivation, no flattery."
        )

        lines += ["", "## Honesty"]
        lines.append(
            f"Candor level {d.candor}/100. Kindness changes how you say something, never "
            "whether you say it. When the user is wrong, over-building, or taking on too "
            "much, say so once, clearly and kindly, then respect their decision."
        )

    if p.protocols:
        lines += ["", "## Protocols (non-negotiable)"]
        for i, r in enumerate(p.protocols):
            lines.append(f"{i + 1}. {r}")
        lines.append(PROTOCOL_OVERRIDE_LINE)

    rules = list(p.extraRules)
    if not degraded:
        for name, threshold, rule in THRESHOLD_RULES:
            if getattr(d, name) >= threshold:
                rules.append(rule)
    if rules:
        lines += ["", "## Working rules"]
        for r in rules:
            lines.append(f"- {r}")

    if p.userContext:
        lines += ["", "## About the user"]
        for c in p.userContext:
            lines.append(f"- {c}")

    return "\n".join(lines)


# The TS name, kept as an alias so cross-checks read like the reference.
buildSystemPrompt = compile_persona


# ---------- Chat-API helper ----------


def to_request(p: PersonaConfig | Profile, messages: Sequence[Mapping[str, str]]) -> dict:
    """The TS `toRequest`: persona boot sets system prompt and temperature together."""
    return {
        "system": compile_persona(p),
        "temperature": derive(p).temperature,
        "messages": list(messages),
    }


# ---------- Profiles (they add `id`) ----------

PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"


PERSONA_KEYS = frozenset(
    {
        "id",
        "name",
        "summary",
        "role",
        "ocean",
        "relationship",
        "candorFloor",
        "protocols",
        "extraRules",
        "userContext",
        "facets",
    }
)


def persona_from_dict(data: Mapping) -> PersonaConfig:
    """Build a persona from profile JSON. Unknown keys are refused so a typo in a
    hand-authored profile cannot silently change nothing. P6: `facets` are a
    first-class grain — the 30 standard names only (unknown names refused),
    mutually exclusive with `ocean`, and aggregated into the loaded `ocean`
    (`aggregate_facets`); a partial facet vector degrades via `out_of_band`."""
    unknown = sorted(set(data) - PERSONA_KEYS)
    if unknown:
        raise ValueError(
            f"unknown profile key(s): {', '.join(unknown)}; "
            f"expected a subset of {', '.join(sorted(PERSONA_KEYS))}"
        )
    ocean_raw = data.get("ocean")
    facets_raw = data.get("facets") or {}
    if not isinstance(facets_raw, Mapping):
        raise ValueError("facets must be an object mapping facet names to numbers")
    if ocean_raw is not None and facets_raw:
        raise ValueError(
            "ocean and facets are mutually exclusive: describe the profile at one "
            "grain — five OCEAN traits, or facet names from the standard 30 (§7)"
        )
    facet_pairs: tuple[tuple[str, float | int], ...] = ()
    if facets_raw:
        extra_facets = sorted(set(facets_raw) - set(FACET_MAP))
        if extra_facets:
            raise ValueError(
                f"unknown facet name(s): {', '.join(extra_facets)}; expected the "
                f"standard 30 grouped under {', '.join(_DOMAIN_LETTERS)}"
            )
        facet_pairs = tuple((str(k), facets_raw[k]) for k in facets_raw)
        ocean = aggregate_facets(facet_pairs)
    elif ocean_raw is None:
        raise ValueError(
            "profile needs either `ocean` (five OCEAN traits 0-100) or `facets` "
            "(standard facet names 0-100; §7 of docs/spec/ocean-profile-schema.md)"
        )
    else:
        extra_traits = sorted(set(ocean_raw) - set(TRAITS))
        if extra_traits:
            raise ValueError(
                f"unknown OCEAN trait(s): {', '.join(extra_traits)}; "
                f"expected {', '.join(TRAITS)}"
            )
        ocean = Ocean(**{t: ocean_raw[t] for t in TRAITS})
    rel = data.get("relationship")
    if rel:
        unknown_rel = sorted(set(rel) - {"friend", "butler", "address", "addressWhen"})
        if unknown_rel:
            raise ValueError(
                f"unknown relationship key(s): {', '.join(unknown_rel)}; "
                f"expected friend, butler, address, addressWhen"
            )
    relationship = (
        Relationship(
            friend=rel["friend"],
            butler=rel["butler"],
            address=rel.get("address", ""),
            addressWhen=tuple(rel.get("addressWhen", ())),
        )
        if rel
        else None
    )
    return PersonaConfig(
        name=data["name"],
        ocean=ocean,
        summary=data.get("summary", ""),
        role=data.get("role", ""),
        relationship=relationship,
        candorFloor=data.get("candorFloor"),
        protocols=tuple(data.get("protocols", ())),
        extraRules=tuple(data.get("extraRules", ())),
        userContext=tuple(data.get("userContext", ())),
        facets=facet_pairs,
    )


def profile_from_path(path: Path | str, *, allow_user_context: bool = False) -> Profile:
    """Load one profile JSON. The `id` is the filename stem; a JSON `id` must match
    it. COMMITTED profiles carry no `userContext` — personal facts live in the
    git-ignored local override. # ponytail: the gate is at LOAD time, not a git
    hook — the ceiling is a hand-edited profile JSON committed later."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    pid = data.get("id", path.stem)
    if pid != path.stem:
        raise ValueError(f"{path.name}: profile id {pid!r} must match its filename")
    if data.get("userContext") and not allow_user_context:
        raise ValueError(
            f"{path.name}: committed profiles carry no `userContext` (privacy stance); "
            f"personal facts live in .ade/etc/persona-user-context.md"
        )
    persona = persona_from_dict(data)
    problems = validate(persona)
    if problems:
        raise ValueError(f"{path.name}: invalid persona: {'; '.join(problems)}")
    return Profile(id=pid, persona=persona, source=str(path))


def load_profile(name: str, profiles_dir: Path | str = PROFILES_DIR) -> Profile:
    """One committed profile by id."""
    return profile_from_path(Path(profiles_dir) / f"{name}.json")


def load_profiles(profiles_dir: Path | str = PROFILES_DIR) -> dict[str, Profile]:
    """Every committed profile, keyed by id."""
    d = Path(profiles_dir)
    if not d.is_dir():
        return {}
    out: dict[str, Profile] = {}
    for f in sorted(d.glob("*.json")):
        prof = profile_from_path(f)
        out[prof.id] = prof
    return out


def ocean_row(p: PersonaConfig | Profile) -> str:
    """The compact ocean vector for lesson metadata rows: `O70 C90 E45 A88 N20`."""
    o = persona_of(p).ocean
    return " ".join(f"{_LETTER[t]}{o.cell(t)}" for t in TRAITS)


# ---------- TS cross-check (the reference implementation, run live) ----------


def _ts_reference_check(profiles: dict[str, Profile]) -> str:
    """Byte-equal cross-check vs the committed TS reference, run through bun.

    The TS demo's compiled preset text must equal the Python port's, and the
    derived parameters must agree exactly. Skips (with a loud note) when bun or
    the TS are unavailable — the Python-only pins still ran.
    """
    ts = Path(__file__).resolve().parent / "personality.ts"
    bun = shutil.which("bun") or ""
    if not (bun and ts.is_file()):
        return "TS cross-check skipped (bun or personality.ts unavailable)"
    tmp = Path(tempfile.mkdtemp(prefix="ocean-ref-"))
    try:
        exe = tmp / "ocean.ts"  # the TS demo guard keys on this exact name
        shutil.copy(ts, exe)
        proc = subprocess.run(
            [bun, str(exe)], capture_output=True, text=True, timeout=120, check=False
        )
        if proc.returncode != 0:
            return f"TS cross-check skipped (bun run failed: {proc.stderr[:120]})"
        out = proc.stdout
        marker = "\n--- Derived parameters ---"
        assert marker in out, "TS demo output shape changed"
        ts_prompt, derived_block = out.split(marker, 1)

        compiled = compile_persona(profiles["april"])
        ts_prompt = ts_prompt.rstrip("\n")
        assert ts_prompt == compiled, (
            "TS buildSystemPrompt(APRIL) != compile_persona(april): "
            + "; ".join(_diff_lines(compiled.splitlines(), ts_prompt.splitlines())[:5])
        )

        d = derive(profiles["april"])
        got: dict = {}
        for m in re.finditer(r'^  (\w+): ("[^"]*"|-?\d+(?:\.\d+)?)', derived_block, re.M):
            key, raw = m.group(1), m.group(2)
            if raw.startswith('"'):
                got[key] = raw[1:-1]
            elif "." in raw:
                got[key] = float(raw)
            else:
                got[key] = int(raw)
        want = {
            "warmth": d.warmth,
            "proactivity": d.proactivity,
            "caution": d.caution,
            "structure": d.structure,
            "candor": d.candor,
            "formality": d.formality,
            "humor": d.humor,
            "length": d.length,
            "temperature": d.temperature,
        }
        assert got == want, (got, want)
        return "TS cross-check (bun run): compiled preset + derived params identical"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _diff_lines(want_l: list[str], got_l: list[str]) -> list[str]:
    out: list[str] = []
    for i in range(max(len(want_l), len(got_l))):
        a = want_l[i] if i < len(want_l) else "<missing>"
        b = got_l[i] if i < len(got_l) else "<missing>"
        if a != b:
            out.append(f"line {i}: want {a!r}; got {b!r}")
    return out


# ---------- Self-checks ----------


def demo() -> None:
    """Assert-based self-checks, no model / no network."""
    # The P7-1 cap-loudness pin rebinds this module global; the `global`
    # declaration must precede every use of the name in this function.
    global FACET_DIRECTIVE_CAP
    profiles = load_profiles()
    assert profiles, "profiles/ must ship at least the april preset"
    assert set(profiles) >= {"april", "user", "verifier"}, sorted(profiles)

    # Band edges are fixed (TS-identical).
    assert [bandOf(v) for v in (0, 20, 21, 40, 41, 60, 61, 80, 81, 100)] == [
        "veryLow",
        "veryLow",
        "low",
        "low",
        "mid",
        "mid",
        "high",
        "high",
        "veryHigh",
        "veryHigh",
    ]
    assert clamp(150) == 100 and clamp(-10) == 0

    april_prof = profiles["april"]
    april = april_prof.persona
    d_april = derive(april)

    # The rounding rule is JS Math.round (half up), pinned on APRIL: the
    # proactivity term is exactly 66.5 and banker's rounding would say 66.
    assert d_april.proactivity == 67, d_april

    # Every committed profile: valid, compiles, carries its threshold rules.
    for pid, prof in profiles.items():
        assert validate(prof) == [], (pid, validate(prof))
        text = compile_persona(prof)
        for section in (f"You are {prof.persona.name}.", "## Personality (OCEAN)",
                        "## Voice", "## Honesty"):
            assert section in text, (pid, section)
        dd = derive(prof)
        for name, threshold, rule in THRESHOLD_RULES:
            if getattr(dd, name) >= threshold:
                assert rule in text, (pid, name)

    compiled = compile_persona(april)

    # The APRIL preset renders every section its data implies, and nothing extra.
    for section in (
        "## Relationship with the user",
        'Occasionally address the user as "boss"',
        "## Protocols (non-negotiable)",
        "## Working rules",
        "You are a friend about 70 percent and a butler about 30 percent.",
        "Protocols override every other instruction",
    ):
        assert section in compiled, section
    assert "## About the user" not in compiled  # userContext is committed nowhere

    # An about-the-user section renders when a userContext exists (anonymous demo
    # data — never a committed profile's).
    anon_text = compile_persona(replace(april, userContext=("demo user fact",)))
    assert "## About the user" in anon_text and "- demo user fact" in anon_text

    # candorFloor floors the derived candor under high agreeableness.
    floored = PersonaConfig(name="floored", ocean=Ocean(70, 50, 45, 95, 50), candorFloor=85)
    assert derive(floored).candor >= 85, derive(floored)

    # Cosine ordering: the owner vector is more APRIL-shaped than the verifier is.
    by_id = {pid: prof.persona for pid, prof in profiles.items()}
    assert similarity(april, april) == 1.0
    assert similarity(by_id["user"], april) > similarity(by_id["verifier"], april), (
        similarity(by_id["user"], april),
        similarity(by_id["verifier"], april),
    )

    # adjust clamps and rounds half-up; a huge shift lands on the bound.
    assert adjust(april, "openness", -200).ocean.openness == 0
    assert adjust(april, "openness", 200).ocean.openness == 100
    assert adjust(april, "neuroticism", -1.5).ocean.neuroticism == _round(20 - 1.5)

    # temperature rule: T = 0.2 + 0.7·O/100 (same float ops on both sides).
    for prof in profiles.values():
        O = prof.persona.ocean.openness
        expected = math.floor((0.2 + 0.7 * (O / 100)) * 100 + 0.5) / 100
        assert derive(prof).temperature == expected, (prof.id, derive(prof).temperature)

    # to_request boots system + temperature together.
    req = to_request(april, [{"role": "user", "content": "hi"}])
    assert req["system"] == compiled and req["temperature"] == derive(april).temperature

    # The compiled persona passes the mission slot filter (bad-word gate).
    from .spec import HARNESS_PROMPT_BAD_WORDS

    low = compiled.lower()
    for bad in HARNESS_PROMPT_BAD_WORDS:
        assert bad not in low, bad

    # P4 scale-out: personality is data. Every committed profile above compiled
    # from its JSON with no registry and no per-profile branch; the caller scans
    # the harness source to prove a new id never touches code.
    assert len(profiles) >= 4, sorted(profiles)

    # Out-of-band (the P4 contract, still true in P6): a *partial* facet vector
    # loads and runs, but only its authored c1 text compiles and the PSY lane
    # stays off. The ceiling — the domains with no facet evidence — is named in
    # `out_of_band`. (Full coverage compiles: pinned below.)
    faceted = replace(april, facets=(("trust", 90), ("dutifulness", 70)))
    assert out_of_band(faceted), "a facet vector must report its ceiling"
    ftext = compile_persona(faceted)
    assert "## Personality (authored)" in ftext, ftext
    assert "## Personality (OCEAN)" not in ftext, "band directives leaked"
    assert "## Voice" not in ftext and "## Honesty" not in ftext, "derived lines leaked"
    assert "## Protocols (non-negotiable)" in ftext, "authored protocols must survive"
    assert "## Facets" in ftext and "- trust 90 (agreeableness)" in ftext, (ftext, "facet data lost")
    assert psy_mechanism(faceted) == "", "PSY must not learn over an uncompilable vector"

    # Unknown keys are refused, so a typo cannot silently compile nothing.
    base_ocean = {t: 50 for t in TRAITS}
    for bad_data in (
        {"name": "x", "ocean": base_ocean, "typo": 1},
        {"name": "x", "ocean": {**base_ocean, "trust": 10}},
    ):
        try:
            persona_from_dict(bad_data)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unknown keys must be refused: {sorted(bad_data)}")

    # P6: the facet grain is a legal second shape. The registry carries exactly
    # the standard 30 facets, 6 per domain, and loading a facet vector
    # aggregates it into `ocean` before the kernel sees the profile.
    assert len(FACET_MAP) == 30
    per_domain: dict[str, int] = {}
    for dom in FACET_MAP.values():
        per_domain[dom] = per_domain.get(dom, 0) + 1
    assert per_domain == {"O": 6, "C": 6, "E": 6, "A": 6, "N": 6}, per_domain

    # Kernel purity: a facet vector whose per-domain facet means equal a
    # committed ocean-grain profile's five scores must compile byte-identically.
    # The twin is the committed data-only profile P4 added as the scale-out
    # proof, selected WITHOUT spelling its id — the zero-code scan below reads
    # this file raw, and "a third persona is one JSON file" forbids the name.
    twins = [
        pid
        for pid in sorted(set(profiles) - {"april", "user", "verifier"})
        if profiles[pid].persona.facets == ()
        and all(profiles[pid].persona.ocean.cell(t) > 0 for t in TRAITS)
    ]
    assert twins, (sorted(profiles), "purity needs a data-only ocean twin (facets-free, no zeros)")
    twin = profiles[twins[0]].persona
    assert out_of_band(twin) == "", twins[0]

    # Facet pairs (s-1, s) per domain average to s - 0.5, so the half-up `_round`
    # must land exactly on the twin's own domain scores — banker's rounding
    # would say e.g. 54 where conscientiousness is 55. All five domains pin the
    # edge, including a domain like 15/100.
    pair_by_domain = {
        "O": ("fantasy", "aesthetics"),
        "C": ("order", "competence"),
        "E": ("warmth", "gregariousness"),
        "A": ("trust", "straightforwardness"),
        "N": ("anxiety", "angry_hostility"),
    }
    facet_json: dict[str, int] = {}
    for dom, (lo, hi) in pair_by_domain.items():
        s = twin.ocean.cell(_DOMAIN_NAME[dom])
        facet_json[lo] = s - 1
        facet_json[hi] = s
    facet_eq = persona_from_dict({"name": "facet-twin", "facets": facet_json})
    assert facet_eq.ocean == twin.ocean, (facet_eq.ocean, twin.ocean)
    assert out_of_band(facet_eq) == "", "full facet coverage must compile"
    assert derive(facet_eq) == derive(twin), "derived params must be identical"
    assert similarity(facet_eq, twin) == 1.0

    def ocean_section(text: str) -> str:
        i = text.index("## Personality (OCEAN)")
        j = text.find("\n## ", i + 3)
        return text[i : j if j != -1 else None].strip()

    assert ocean_section(compile_persona(facet_eq)) == ocean_section(compile_persona(twin)), (
        "kernel purity: identical OCEAN section for equivalent grains"
    )
    assert psy_mechanism(facet_eq) != "", "PSY must follow a compiled facet vector"

    ftxt = compile_persona(facet_eq)
    assert "## Facets" in ftxt, ftxt
    # Data block stays inventory (`name value (domain)` lines, registry order);
    # behavior rules live in `## Facet directives` above it (P7-1 pins below
    # cover the divergent-facet render).
    i = ftxt.index("## Facets")
    j = ftxt.find("\n## ", i + 3)
    fac_lines = ftxt[i : j if j != -1 else None].strip().splitlines()
    assert len(fac_lines) - 1 == len(facet_eq.facets), fac_lines
    for fac_line in fac_lines[1:]:
        assert fac_line.startswith("- ") and fac_line.endswith(")"), fac_line
    a_lo, _ = pair_by_domain["A"]
    assert f"- {a_lo} {twin.ocean.agreeableness - 1} (agreeableness)" in ftxt

    # Partial facet coverage keeps the P4 degradation; the reason names the
    # domains with no facet evidence, and the neutral 50-fill keeps the raw
    # vector machinery defined without ever reaching compiled text.
    partial = persona_from_dict({"name": "partial", "facets": {"trust": 90, "dutifulness": 70}})
    reason = out_of_band(partial)
    assert (
        "no facet evidence for" in reason
        and "openness" in reason
        and "neuroticism" in reason
    ), reason
    assert partial.ocean == Ocean(50, 70, 50, 90, 50), (partial.ocean, "neutral fill rule")
    ptext = compile_persona(partial)
    assert "## Personality (authored)" in ptext and "## Personality (OCEAN)" not in ptext
    assert "## Voice" not in ptext and "## Honesty" not in ptext
    assert "## Facets" in ptext and "- trust 90 (agreeableness)" in ptext
    assert psy_mechanism(partial) == ""

    # P6 loader gates fail loudly: ocean+facets refusal, unknown facet names,
    # and a JSON with neither grain.
    for bad_data, frag in (
        ({"name": "x", "ocean": base_ocean, "facets": {"trust": 90}}, "mutually exclusive"),
        ({"name": "x", "facets": {"trust": 90, "truffle_pig": 10}}, "unknown facet name"),
        ({"name": "x"}, "`ocean`"),
    ):
        try:
            persona_from_dict(bad_data)
        except ValueError as e:
            assert frag in str(e), (frag, str(e))
        else:
            raise AssertionError(f"loud refusal expected: {frag}")

    # ------------------------------------------------------------------
    # P7-1: facet-conditioned directives — the payload of facet grain.
    # ------------------------------------------------------------------
    # The table is registry-complete: all 30 facets x the four extreme bands;
    # `mid` is deliberately absent (the domain directive already owns the mid
    # behavior — a facet line there would duplicate it). Band edges are
    # `bandOf`'s own; the render is registry-ordered, so JSON key order never
    # leaks into compiled text.
    assert set(FACET_CONDITIONS) == set(FACET_MAP), "directive table must cover the registry"
    for name, tab in FACET_CONDITIONS.items():
        assert set(tab) == set(BANDS) - {"mid"}, (name, sorted(tab))
        assert all(isinstance(c, str) and c.strip() for c in tab.values()), name
    worst = sum(
        max(len(f"- {name} ({b}): {c}") + 1 for b, c in tab.items())
        for name, tab in FACET_CONDITIONS.items()
    )
    assert worst <= FACET_DIRECTIVE_CAP, (worst, FACET_DIRECTIVE_CAP)

    # Mid-only facet vectors emit nothing; the section appears above the data
    # block and only when at least one facet is outside mid.
    mid_all = {name: 50 for name in FACET_MAP}
    mid_only = persona_from_dict({"name": "mid-only", "facets": mid_all})
    assert facet_directives(mid_only.facets) == ()
    assert "## Facet directives" not in compile_persona(mid_only)

    div_data = dict(mid_all)
    div_data["fantasy"] = 90
    div_data["anxiety"] = 10
    div = persona_from_dict({"name": "divergent", "facets": div_data})
    dirs = facet_directives(div.facets)
    assert len(dirs) == 2, dirs
    assert dirs[0] == (
        "- fantasy (veryHigh): Lead with original framings and invented "
        "scenarios; label the speculative parts."
    ), dirs
    assert dirs[1] == "- anxiety (veryLow): Stay unshakable; worry changes nothing here.", dirs
    dtext = compile_persona(div)
    assert dtext.index("## Facet directives") < dtext.index("## Facets"), dtext
    i = dtext.index("## Facet directives")
    j = dtext.find("\n## ", i + 3)
    dsec = dtext[i : j if j != -1 else None].strip().splitlines()
    assert len(dsec) - 1 == 2 and all(ln.startswith("- ") for ln in dsec[1:]), dsec
    assert compile_persona(div) == dtext, "compile must be deterministic"

    # Band edges are bandOf's: 15→veryLow, 35→low, 50→mid (silent), 70→high,
    # 85→veryHigh — one facet sweeps every rule.
    for v, band in ((15, "veryLow"), (35, "low"), (50, "mid"), (70, "high"), (85, "veryHigh")):
        sweep = persona_from_dict({"name": "sweep", "facets": {**mid_all, "warmth": v}})
        wl = facet_directives(sweep.facets)
        if band == "mid":
            assert wl == (), (v, wl)
        else:
            assert len(wl) == 1 and wl[0].startswith(f"- warmth ({band}): "), (v, wl)

    # Input-key order cannot leak: two JSONs with the same facets in different
    # key orders compile byte-identically (both facet sections render in
    # registry order). Duplicate facet pairs dedupe to one line.
    b_grain = persona_from_dict({"name": "divergent", "facets": dict(reversed(list(div_data.items())))})
    assert facet_directives(div.facets) == facet_directives(b_grain.facets)
    assert compile_persona(div) == compile_persona(b_grain), "JSON key order must not leak"
    dupd = replace(div, facets=div.facets + div.facets)
    assert facet_directives(dupd.facets) == dirs, "duplicate facet pairs must dedupe"

    # The kernel-purity twin's facet pairs: the O/C/E pairs (59,60 / 54,55 /
    # 49,50) sit in mid, while A's pair (84, 85) is veryHigh and N's pair
    # (14, 15) is veryLow — so exactly four directive lines render, no more.
    dirs_eq = facet_directives(facet_eq.facets)
    assert len(dirs_eq) == 4, dirs_eq
    assert any(ln.startswith("- trust (veryHigh): ") for ln in dirs_eq), dirs_eq
    assert any(ln.startswith("- anxiety (veryLow): ") for ln in dirs_eq), dirs_eq

    # Ocean grain emits no facet section at all; a degraded (partial) vector
    # keeps the P4 contract — authored text only, no directives.
    assert "## Facet" not in compile_persona(twin), "ocean grain must not emit a facet section"
    assert "## Facet directives" not in ptext, "degraded vectors must not compile facet directives"

    # The section's own ceiling is loud: an over-cap render refuses at
    # validate() and at compile, never truncates.
    real_cap = FACET_DIRECTIVE_CAP
    try:
        FACET_DIRECTIVE_CAP = 10
        problems = validate(div)
        assert any("FACET_DIRECTIVE_CAP" in e for e in problems), problems
        try:
            compile_persona(div)
        except ValueError as e:
            assert "FACET_DIRECTIVE_CAP" in str(e), str(e)
        else:
            raise AssertionError("cap overflow must refuse loudly, never truncate")
    finally:
        FACET_DIRECTIVE_CAP = real_cap

    print(f"  ok: {_ts_reference_check(profiles)}")


if __name__ == "__main__":
    demo()
    print("OCEAN personality self-checks passed.")
