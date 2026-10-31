"""A deterministic APRIL-domain adapter used by `april demo` and local CI."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import tree as harness_tree
from .spec import HarnessSpec, HarnessPrompts, AgentAdapter, SurfaceSpec
from .proposer import Proposer, Reply


DEMO_SURFACE = SurfaceSpec(
    name="demo",
    always_on=("AGENTS.md",),
    always_on_max=100_000,
    always_on_cap_reason="demo surface cap",
    skill_dir=".agents/skills",
    skill_name_rule="dir",
    trigger_hint="",
    autotrigger_file="",
    trigger_line="",
    subagent_requires_mode=False,
    plugin_dir=None,
    hooks_file=None,
    stubs=(),
)

_BASE_TEXT = (
    "# Demo Harness\n\n"
    "Base demo harness: ledger reconciliation uses a positive-only filter (bug).\n"
)

_FIXED_TEXT = (
    "# Demo Harness\n\n"
    "Fixed demo harness: ledger reconciliation handles positive and negative entries.\n"
)


@dataclass
class DemoSubstrate:
    name: str = "demo"
    surface_spec: SurfaceSpec = field(default_factory=lambda: DEMO_SURFACE)

    def surface(self) -> SurfaceSpec:
        return self.surface_spec


@dataclass
class DemoAdapter:
    spec: HarnessSpec = field(default_factory=lambda: HarnessSpec(
        name="april-demo",
        runs_root=Path("runs"),
        install_mode="workspace_agents_md",
        prompts=HarnessPrompts(work="Improve a deterministic ledger reconciliation demo."),
        channels={},
        domain_word="capability domain",
        leak_globs=(),
        allow_subagents=False,
        obs_trunc=50_000,
    ))
    substrate: DemoSubstrate = field(default_factory=DemoSubstrate)
    _base: Path = Path("runs") / "_demo_base_harness"

    def tasks(self, split: str = "all"):
        return ["demo/ledger-reconciliation"]

    def domain_of(self, task_id: str) -> str:
        return "ledger"

    def task_prompt(self, task_id: str) -> str:
        return "Reconcile ledger entries, including negative adjustments (demo task)."

    def task_files(self, task_id: str):
        return {}

    def execute(self, task_id: str, harness_dir, run_id: str, *, timeout=None):
        run_dir = Path(tempfile.mkdtemp(prefix="april-demo-run-"))
        run_dir.mkdir(parents=True, exist_ok=True)
        improved = False
        if harness_dir is not None and Path(harness_dir).is_dir():
            try:
                for p in Path(harness_dir).rglob("*"):
                    if p.is_file() and "Fixed demo harness" in p.read_text(errors="replace"):
                        improved = True
            except OSError:
                pass
        (run_dir / "artifact.md").write_text(
            "Ledger reconciliation complete. Improved: " + str(improved).lower() + "\n",
            encoding="utf-8",
        )
        return run_dir

    def delivered(self, run_dir):
        return Path(run_dir, "artifact.md").is_file()

    def trajectory(self, run_dir, *, obs_trunc: int = 50_000):
        return "demo trajectory"

    def deliverable_files(self, run_dir):
        return {"artifact.md": str(Path(run_dir) / "artifact.md")}

    def deliverable_text(self, run_dir):
        path = Path(run_dir) / "artifact.md"
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def base_harness(self):
        self._base.mkdir(parents=True, exist_ok=True)
        (self._base / "AGENTS.md").write_text(_BASE_TEXT, encoding="utf-8")
        return self._base

    def validate_tree(self, tree):
        harness_tree.validate(self.substrate.surface(), tree)

    def score(self, run_dir, task_id):
        text = self.deliverable_text(run_dir)
        return {"improved": "Improved: true" in text}

    def prompts_for(self, task_id):
        from .spec import HarnessPrompts
        return HarnessPrompts(work="Improve a deterministic ledger reconciliation demo.")


class DeterministicProposer:
    """Proposer stand-in that deterministically fixes the demo harness."""

    def __init__(self, *, audit_dir=None):
        self.audit_dir = audit_dir
        self.spec = type("Spec", (), {"kind": "demo", "model": "deterministic"})()
        self.attempts = 1

    def call(self, mission, context_dir, label, *, system="", timeout=None, max_attempts=None, harvest=None):
        import uuid
        tmp = Path(tempfile.mkdtemp(prefix="april-demo-prop-"))
        if context_dir and Path(context_dir).is_dir():
            shutil.copytree(context_dir, tmp / "context", dirs_exist_ok=True)
        sub = harvest or "context/harness"
        src = tmp / sub
        if src.is_dir():
            for p in src.rglob("*.md"):
                p.write_text(_FIXED_TEXT, encoding="utf-8")
        # copy harvested tree to a durable location
        dest = None
        if src.is_dir():
            if self.audit_dir is None:
                self.audit_dir = Path(tempfile.mkdtemp(prefix="april-demo-audit-"))
            Path(self.audit_dir).mkdir(parents=True, exist_ok=True)
            safe = f"{label}.workspace"
            dest = Path(self.audit_dir) / safe
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(src, dest)
        text = "<notes>deterministic fix: corrected positive-only ledger filter</notes>"
        return Reply(label=label, text=text, ok=True, cost_usd=0.0, wall_s=0.0, attempts=1, cached=False, channel="demo", workspace=dest)


def make_adapter():
    return DemoAdapter()


__all__ = ["DemoAdapter", "DeterministicProposer", "make_adapter", "DEMO_SURFACE"]
