"""The benchmark seam: everything a benchmark must supply, and nothing more."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol, runtime_checkable

from .tree import SurfaceSpec

ModelId = str

CHANNELS = ("claude_cli", "opencode")
INSTALL_MODES = ("workspace_agents_md", "home_dir_jinja", "workspace_config", "codex_root")

_DEFAULT_CHANNEL_MODEL = {
    "claude_cli": "claude-sonnet",
    "opencode": "openai/gpt-4o-mini",
}


@dataclass(frozen=True)
class ChannelSpec:
    kind: str
    model: ModelId = ""
    effort: str = "high"
    steps: int = 120
    timeout: int = 3600

    def __post_init__(self) -> None:
        if self.kind not in CHANNELS:
            raise ValueError(f"unknown channel {self.kind!r}; expected one of {CHANNELS}")


def resolve_channel_model(
    kind=None,
    model=None,
    *,
    effort: str = "high",
    steps: int = 120,
    timeout: int = 3600,
):
    use_default = kind is None and model is None
    if (kind is None) != (model is None):
        raise ValueError(
            "channel and model must be overridden TOGETHER; got "
            f"kind={kind!r}, model={model!r}"
        )
    if kind is None:
        kind = "opencode"
    if kind not in CHANNELS:
        raise ValueError(f"unknown channel {kind!r}; expected one of {CHANNELS}")
    if model is None:
        model = _DEFAULT_CHANNEL_MODEL[kind]
    if not str(model).strip():
        if use_default:
            return ChannelSpec(kind, "", effort=effort, steps=steps, timeout=timeout)
        raise ValueError("model override must not be empty")
    return ChannelSpec(kind, model, effort=effort, steps=steps, timeout=timeout)


HARNESS_PROMPT_BAD_WORDS = ("benchmark", "evaluation", "grader", "rubric", "score")


@dataclass(frozen=True)
class HarnessPrompts:
    work: str = ""
    domain_word: str = "domain"
    inv_levers: str = ""
    dom_levers: str = ""
    yardstick: str = ""
    deliverable_word: str = "deliverable"
    domain_guidance: str = ""
    # P2 constraint mode: `persona_guidance` is the COMPILED persona block (the
    # output of personality.compile_persona) — normally filled by
    # resolve_prompts from HarnessSpec.profile, or passed pre-compiled by a
    # benchmark that manages its own profiles. It rides the same bad-word
    # filter as every other mission slot.
    persona_guidance: str = ""
    # P3 seam, landed with the P2 slot extension: the PSY dimension's lever
    # text (personality as a learnable axis). Empty until P3 fills it.
    psy_levers: str = ""
    selection_checks: str = ""
    selection_lead: str = ""
    selection_conformance: str = "full"
    prompt_pack: str = "adapt"

    def __post_init__(self) -> None:
        if self.prompt_pack not in ("adapt", "tts"):
            raise ValueError(
                f"HarnessPrompts.prompt_pack must be 'adapt' or 'tts', got {self.prompt_pack!r}"
            )
        visible = {
            "work": self.work,
            "inv_levers": self.inv_levers,
            "dom_levers": self.dom_levers,
            "yardstick": self.yardstick,
            "domain_guidance": self.domain_guidance,
            "psy_levers": self.psy_levers,
            "persona_guidance": self.persona_guidance,
            "selection_checks": self.selection_checks,
        }
        for field_name, value in visible.items():
            low = str(value).lower()
            for bad in HARNESS_PROMPT_BAD_WORDS:
                if bad in low:
                    raise ValueError(
                        f"HarnessPrompts.{field_name} must describe the WORK, not its "
                        f"measurement (found {bad!r})."
                    )


# Alias matching the reference implementation's naming.
BenchPrompts = HarnessPrompts


@dataclass(frozen=True)
class HarnessSpec:
    name: str = "default"
    runs_root: Path = Path("runs")
    install_mode: str = "workspace_agents_md"
    prompts: HarnessPrompts = HarnessPrompts()
    # P2: id of the committed profile in profiles/<id>.json that compiles into
    # this spec's proposal missions ("" = run persona-free). The profile is
    # data; personal facts never travel with it.
    profile: str = ""
    channels: dict | None = None
    domain_word: str = "domain"
    leak_globs: tuple[str, ...] = ()
    allow_subagents: bool = False
    reserved_scripts: frozenset[str] = frozenset()
    proposer_deliverables: str = "contents"
    state_deliverable: bool = False
    obs_trunc: int = 50_000

    def __post_init__(self) -> None:
        if self.channels is None:
            object.__setattr__(self, "channels", {})
        if self.install_mode not in INSTALL_MODES:
            raise ValueError(
                f"unknown install_mode {self.install_mode!r}; expected one of {INSTALL_MODES}"
            )
        if self.proposer_deliverables not in ("contents", "names"):
            raise ValueError(
                f"HarnessSpec.proposer_deliverables must be 'contents' or 'names', got "
                f"{self.proposer_deliverables!r}"
            )
        if self.obs_trunc < 10_000:
            raise ValueError(
                f"obs_trunc={self.obs_trunc} is in the range that fabricates defects; "
                f"use >= 10_000 (default 50_000)"
            )
        bad = sorted(s for s in self.reserved_scripts if "/" in s or not s.endswith(".py"))
        if bad:
            raise ValueError(
                f"HarnessSpec.reserved_scripts takes bare .py BASENAMES, not paths: {bad}"
            )
        if not isinstance(self.prompts, (HarnessPrompts, BenchPrompts)):
            raise ValueError("HarnessSpec.prompts must be a HarnessPrompts")

BenchSpec = HarnessSpec


@dataclass
class RunView:
    label: str
    run_id: str = ""
    run_dir: Path = Path(".")
    ok: bool = True
    delivered: bool = True
    cost_usd: float = 0.0
    wall_s: float = 0.0
    error: str = ""


@runtime_checkable
class SubstrateLike(Protocol):
    name: str

    def surface(self) -> SurfaceSpec:
        ...


@runtime_checkable
class AgentAdapter(Protocol):
    spec: HarnessSpec
    substrate: SubstrateLike

    def tasks(self, split: str = "all") -> list[str]: ...

    def domain_of(self, task_id: str) -> str: ...

    def task_prompt(self, task_id: str) -> str: ...

    def task_files(self, task_id: str): ...

    def execute(self, task_id: str, harness_dir, run_id: str, *, timeout=None) -> Path: ...

    def delivered(self, run_dir) -> bool: ...

    def trajectory(self, run_dir, *, obs_trunc: int) -> str: ...

    def deliverable_files(self, run_dir) -> dict: ...

    def deliverable_text(self, run_dir) -> str: ...

    def base_harness(self): ...

    def validate_tree(self, tree) -> None: ...

    def score(self, run_dir, task_id) -> dict | None: ...


# Alias matching the reference implementation's naming.
BenchmarkAdapter = AgentAdapter


def resolve_prompts(adapter: AgentAdapter, task_id: str) -> HarnessPrompts:
    fn = getattr(adapter, "prompts_for", None)
    prompts = fn(task_id) if callable(fn) else getattr(adapter.spec, "prompts", None)
    if not isinstance(prompts, (HarnessPrompts, BenchPrompts)):
        raise TypeError(
            f"{type(adapter).__name__}.prompts_for({task_id!r}) returned "
            f"{type(prompts).__name__}, expected HarnessPrompts"
        )
    # P2 constraint mode: when the spec names a profile, its compiled persona
    # fills the `persona_guidance` slot unless the prompts already carry one
    # (an explicit block wins — never overwrite a benchmark's own text). The
    # reload happens HERE, per mission build, so a profile edit shows up
    # without touching the adapter. Lazy import: the seam imports nothing.
    spec = getattr(adapter, "spec", None)
    profile_id = str(getattr(spec, "profile", "") or "").strip()
    if isinstance(prompts, HarnessPrompts) and profile_id:
        from .personality import compile_persona, load_profile, psy_mechanism

        profile = load_profile(profile_id)
        updates: dict[str, str] = {}
        if not prompts.persona_guidance.strip():
            updates["persona_guidance"] = compile_persona(profile).strip()
        # P3: a profile-backed run activates the PSY dimension. The slot carries
        # derive() params, never raw traits, and stays empty on persona-free runs
        # (which is exactly the signal `prompts.active_dims` reads).
        if not prompts.psy_levers.strip():
            updates["psy_levers"] = psy_mechanism(profile).strip()
        if updates:
            prompts = replace(prompts, **updates)
    return prompts


__all__ = [
    "AgentAdapter",
    "BenchmarkAdapter",
    "BenchSpec",
    "BenchPrompts",
    "HarnessSpec",
    "HarnessPrompts",
    "RunView",
    "ModelId",
    "resolve_prompts",
    "resolve_channel_model",
    "ChannelSpec",
    "SubstrateLike",
    "CHANNELS",
    "INSTALL_MODES",
]
