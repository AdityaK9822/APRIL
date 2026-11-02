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
cannot express (currently `facets`, the deferred 30-facet expansion) still loads
and runs, but degrades to its authored c1 guidance with the PSY lane off —
`out_of_band()` names the reason, never a silent approximation.

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
    # Deferred 30-facet expansion: sub-trait values the band tables cannot
    # compile. Kept on the persona so a facet profile degrades to its authored
    # c1 text instead of silently dropping the facet signal (`out_of_band`).
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
        if (
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            or v < 0
            or v > 100
        ):
            errors.append(f"facet {name!r} must be a number from 0 to 100 (got {v})")
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

    P4 scale-out contract: a profile is data, and the data the compiler knows is
    the five OCEAN traits × five bands. A profile that carries facet-level
    signal is loadable and its authored text still compiles (c1 guidance), but
    trait directives, derived voice/honesty lines and threshold rules are
    withheld rather than invented from traits that do not describe the vector.
    # ponytail: 30-facet Big Five expansion is DEFERRED. When facets land they
    # become authored table data (`FACET_CONDITIONS`) and this degradation path
    # shrinks to genuinely unknown keys; until then a facet profile is the
    # honest ceiling of "one JSON file, zero code".
    """
    facets = persona_of(p).facets
    if facets:
        names = ", ".join(name for name, _ in facets[:4])
        more = "" if len(facets) <= 4 else f", +{len(facets) - 4} more"
        return f"{len(facets)} facet trait(s) with no band directives ({names}{more})"
    return ""


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
        # meaningful when the vector compiles to band directives. A facet profile
        # keeps PSY off (2-dim ledger) until the facet tables are authored.
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
    hand-authored profile cannot silently change nothing. `facets` is accepted
    (deferred 30-facet expansion) and is what `out_of_band` degrades on."""
    unknown = sorted(set(data) - PERSONA_KEYS)
    if unknown:
        raise ValueError(
            f"unknown profile key(s): {', '.join(unknown)}; "
            f"expected a subset of {', '.join(sorted(PERSONA_KEYS))}"
        )
    extra_traits = sorted(set(data["ocean"]) - set(TRAITS))
    if extra_traits:
        raise ValueError(
            f"unknown OCEAN trait(s): {', '.join(extra_traits)}; "
            f"expected {', '.join(TRAITS)} (facets belong under `facets`)"
        )
    facets_raw = data.get("facets") or {}
    if not isinstance(facets_raw, Mapping):
        raise ValueError("facets must be an object mapping facet names to numbers")
    ocean = Ocean(**{t: data["ocean"][t] for t in TRAITS})
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
        facets=tuple((str(k), v) for k, v in facets_raw.items()),
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

    # Out-of-band: a facet vector loads and runs, but only its authored c1 text
    # compiles and the PSY lane stays off. The ceiling is named in `out_of_band`.
    faceted = replace(april, facets=(("trust", 90), ("dutifulness", 70)))
    assert out_of_band(faceted), "a facet vector must report its ceiling"
    ftext = compile_persona(faceted)
    assert "## Personality (authored)" in ftext, ftext
    assert "## Personality (OCEAN)" not in ftext, "band directives leaked"
    assert "## Voice" not in ftext and "## Honesty" not in ftext, "derived lines leaked"
    assert "## Protocols (non-negotiable)" in ftext, "authored protocols must survive"
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

    print(f"  ok: {_ts_reference_check(profiles)}")


if __name__ == "__main__":
    demo()
    print("OCEAN personality self-checks passed.")
