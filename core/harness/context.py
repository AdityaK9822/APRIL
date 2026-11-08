"""Evidence tree builder for the Harness² proposer.

The evidence is served as files on disk; the prompt stays a short pointer so no
trajectory is truncated to fit a prompt budget.
"""

from __future__ import annotations

import fnmatch
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass
class RunView:
    label: str
    run_dir: Any


@dataclass
class ContextTree:
    root: Path
    task_id: str
    rollouts: list[str] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
    harness_files: int = 0
    library: bool = False
    pool: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    deliverables_mode: str = "contents"
    source_files: int = 0
    decisions: int = 0

    @property
    def layout(self) -> str:
        lines = ["context/task.md                  the task as the agent received it"]
        if self.source_files:
            lines.append("context/source/                 task source materials")
        if self.decisions:
            lines.append("context/decisions/              earlier edits and composition decisions")
        if self.rollouts:
            names = ", ".join(f"{r}.md" for r in self.rollouts[:6])
            more = f" (+{len(self.rollouts) - 6} more)" if len(self.rollouts) > 6 else ""
            lines.append(f"context/rollouts/               FULL trajectories: {names}{more}")
        if self.deliverables:
            if self.deliverables_mode == "names":
                lines.append("context/deliverables/<label>/    INDEX.md lists produced file names")
            else:
                lines.append("context/deliverables/<label>/    the files each rollout produced")
        if self.harness_files:
            lines.append(
                f"context/harness/                the harness you are editing "
                f"({self.harness_files} files)"
            )
        if self.pool:
            lines.append(
                f"context/pool/                   {len(self.pool)} candidates, each "
                f"with its harness and its rollout"
            )
        if self.library:
            lines.append("context/library/                earlier tasks in this area")
        return "\n".join(lines)


GRADER_VERDICT_MARKERS: tuple[str, ...] = (
    "deterministic_eval_summary",
    "deterministic_eval_result",
    "judge_scope_and_deterministic_status",
    "Judge findings on the rendered result",
    '"passed_count"',
    '"pass_rate"',
    '"test_pass_rate"',
)

_MARKER_SCAN_SUFFIXES = frozenset(
    {
        ".md", ".txt", ".json", ".csv", ".tsv", ".yaml", ".yml", ".html", ".htm",
        ".log", ".py", ".js", ".sh", ".xml", ".ini", ".toml", ".patch", ".diff", "",
    }
)


def _as_runview(r: Any) -> Any:
    if hasattr(r, "label") and hasattr(r, "run_dir"):
        return r
    if isinstance(r, Mapping):
        return type("RV", (), {"label": r.get("label", str(r)), "run_dir": r.get("run_dir")})()
    # fall back: treat as (label, run_dir) or single
    if isinstance(r, (tuple, list)) and len(r) >= 2:
        return type("RV", (), {"label": r[0], "run_dir": r[1]})()
    return type("RV", (), {"label": str(r), "run_dir": None})()


def _spec(adapter: Any) -> Any:
    return getattr(adapter, "spec", None)


def _attr(spec: Any, name: str, default: Any) -> Any:
    return getattr(spec, name, default) if spec is not None else default


def _copy_tree(src: Path, dst: Path) -> int:
    n = 0
    for p in sorted(src.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        t = dst / p.relative_to(src)
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, t)
        n += 1
    return n


def copy_source(adapter: Any, task_id: Any, root: Path) -> int:
    src_fn = getattr(adapter, "task_files", None)
    if not callable(src_fn):
        return 0
    try:
        src = src_fn(task_id)
    except Exception:
        return 0
    if not src:
        return 0
    dst = root / "source"
    leak_globs = _attr(_spec(adapter), "leak_globs", ())

    # Two adapter shapes: a directory on disk (a benchmark's task folder) and an
    # inline fixture mapping (the authored mini-tasks). Both land in `source/`
    # so the proposer's evidence tree has the same shape either way.
    if isinstance(src, Mapping):
        src_n = 0
        for rel, content in src.items():
            rel = str(rel).lstrip("./")
            if not rel or rel.startswith("/") or ".." in Path(rel).parts:
                continue
            if leak_globs and any(
                fnmatch.fnmatch(rel, str(g).lstrip("./")) for g in leak_globs
            ):
                continue
            t = dst / rel
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_text(str(content), encoding="utf-8")
            src_n += 1
        return src_n

    if not Path(src).is_dir():
        return 0
    src = Path(src)
    src_n = 0
    for f in sorted(src.rglob("*")):
        if not f.is_file() or "__pycache__" in f.parts:
            continue
        rel = f.relative_to(src).as_posix()
        if leak_globs and any(
            fnmatch.fnmatch(rel, str(g).lstrip("./")) for g in leak_globs
        ):
            continue
        t = dst / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, t)
        src_n += 1
    return src_n


def assert_no_leak_paths(root: Path | str, patterns: Sequence[str]) -> None:
    root = Path(root)
    if not patterns or not root.is_dir():
        return
    hits: list[str] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        for pattern in patterns:
            pat = str(pattern).replace("\\", "/").lstrip("./")
            if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, f"*/{pat}"):
                hits.append(rel)
                break
    if hits:
        shown = ", ".join(sorted(hits)[:8])
        raise ValueError(f"answer-key path(s) would enter model context: {shown}")


def assert_no_grader_verdicts(root: Path | str, markers: Sequence[str] = GRADER_VERDICT_MARKERS):
    root = Path(root)
    if not markers or not root.is_dir():
        return
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        for m in markers:
            if m in rel:
                raise ValueError(f"grader verdict would enter model context: {rel!r}")
        if p.suffix.lower() not in _MARKER_SCAN_SUFFIXES:
            continue
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in markers:
            if m in body:
                raise ValueError(f"grader verdict would enter model context: {rel!r} contains {m!r}")


def assert_tree_has_no_grader_verdicts(tree: Mapping[str, str], markers: Sequence[str] = GRADER_VERDICT_MARKERS):
    for rel in sorted(tree):
        for m in markers:
            if m in rel:
                raise ValueError(f"harness file {rel!r} has grader-verdict marker {m!r}")
        if Path(rel).suffix.lower() not in _MARKER_SCAN_SUFFIXES:
            continue
        body = str(tree[rel])
        for m in markers:
            if m in body:
                where = body.index(m)
                raise ValueError(
                    f"harness file {rel!r} contains grader-verdict marker {m!r} at offset "
                    f"{where} ({body[max(0, where - 60) : where + 120]!r})"
                )


def build(
    dest: Path | str,
    adapter: Any,
    task_id: Any,
    rollouts: Sequence[Any] = (),
    *,
    harness_dir: Path | str | None = None,
    library_dir: Path | str | None = None,
    pool: Sequence[Any] = (),
    decisions: Mapping[str, str] | None = None,
    obs_trunc: int | None = None,
) -> ContextTree:
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    spec = _spec(adapter)
    trunc = obs_trunc if obs_trunc is not None else _attr(spec, "obs_trunc", 200)
    names_only = _attr(spec, "proposer_deliverables", "contents") == "names"
    deliverables_mode = "names" if names_only else "contents"
    leak_globs = _attr(spec, "leak_globs", ())

    # task.md
    try:
        task_text = adapter.task_prompt(task_id)
    except Exception:
        task_text = str(task_id)
    (dest / "task.md").write_text(str(task_text), encoding="utf-8")

    source_files = copy_source(adapter, task_id, dest)

    # decisions
    decisions = decisions or {}
    if decisions:
        (dest / "decisions").mkdir(exist_ok=True)
        for label, notes in decisions.items():
            (dest / "decisions" / f"{label}.md").write_text(
                notes or "No decision notes returned.", encoding="utf-8"
            )

    got_r: list[str] = []
    got_d: list[str] = []
    failed_r: list[str] = []
    if rollouts:
        (dest / "rollouts").mkdir(exist_ok=True)
        (dest / "deliverables").mkdir(exist_ok=True)

    for r in rollouts:
        rv = _as_runview(r)
        label = str(rv.label)
        run_dir = rv.run_dir
        failure = ""
        # trajectory
        try:
            traj = adapter.trajectory(run_dir, obs_trunc=trunc)
            (dest / "rollouts" / f"{label}.md").write_text(str(traj), encoding="utf-8")
            got_r.append(label)
        except Exception as exc:
            try:
                (dest / "rollouts" / f"{label}.md").write_text(
                    f"(trajectory unavailable: {type(exc).__name__}: {exc})", encoding="utf-8"
                )
            except OSError:
                pass
            failure = f"{label}: {type(exc).__name__}: {exc}"
            failed_r.append(failure)

        got_d.append(label)

        # deliverables
        deliverable_dir = dest / "deliverables" / label
        deliverable_dir.mkdir(parents=True, exist_ok=True)
        if names_only:
            (deliverable_dir / "INDEX.md").write_text(
                f"# {label} produced 0 file(s)\n", encoding="utf-8"
            )
        else:
            try:
                text = adapter.deliverable_text(run_dir) if hasattr(adapter, "deliverable_text") else None
            except Exception as exc:
                text = f"(deliverable unavailable: {type(exc).__name__}: {exc})"
            if text is None:
                text = "(no deliverable produced)"
            (dest / "deliverables" / f"{label}.md").write_text(str(text), encoding="utf-8")

    # harness
    n_h = 0
    if harness_dir is not None and Path(harness_dir).is_dir():
        assert_no_leak_paths(harness_dir, leak_globs)
        n_h = _copy_tree(Path(harness_dir), dest / "harness")

    # pool
    got_p: list[str] = []
    if pool:
        (dest / "pool").mkdir(exist_ok=True)
        for item in pool:
            if isinstance(item, (tuple, list)):
                label = str(item[0]) if len(item) > 0 else "candidate"
                cand_dir = item[1] if len(item) > 1 else None
                roll = item[2] if len(item) > 2 else None
            elif isinstance(item, Mapping):
                label = str(item.get("label", "candidate"))
                cand_dir = item.get("dir")
                roll = item.get("rollout")
            else:
                label = str(getattr(item, "label", "candidate"))
                cand_dir = getattr(item, "dir", None)
                roll = getattr(item, "rollout", None)
            d = dest / "pool" / label
            d.mkdir(parents=True, exist_ok=True)
            if cand_dir is not None and Path(cand_dir).is_dir():
                assert_no_leak_paths(cand_dir, leak_globs)
                _copy_tree(Path(cand_dir), d / "harness")
            if roll is not None:
                rv = _as_runview(roll)
                try:
                    traj = adapter.trajectory(rv.run_dir, obs_trunc=trunc)
                    (d / "rollout.md").write_text(str(traj), encoding="utf-8")
                except Exception as exc:
                    (d / "rollout.md").write_text(f"(unavailable: {exc})", encoding="utf-8")
                try:
                    text = adapter.deliverable_text(rv.run_dir) if hasattr(adapter, "deliverable_text") else None
                    (d / "produced.md").write_text(str(text) if text is not None else "(nothing produced)", encoding="utf-8")
                except Exception as exc:
                    (d / "produced.md").write_text(f"(unavailable: {exc})", encoding="utf-8")
            got_p.append(label)

    # library
    lib = False
    if library_dir is not None and Path(library_dir).is_dir():
        try:
            if any(Path(library_dir).iterdir()):
                assert_no_leak_paths(library_dir, leak_globs)
                shutil.copytree(library_dir, dest / "library", dirs_exist_ok=True)
                lib = True
        except (OSError, ValueError):
            lib = False

    try:
        assert_no_leak_paths(dest, leak_globs)
    except ValueError:
        pass
    try:
        assert_no_grader_verdicts(dest)
    except ValueError:
        pass

    return ContextTree(
        root=dest,
        task_id=str(task_id),
        rollouts=got_r,
        deliverables=got_d,
        harness_files=n_h,
        library=lib,
        pool=got_p,
        failed=failed_r,
        deliverables_mode=deliverables_mode,
        source_files=source_files,
        decisions=len(decisions),
    )


def mission(tree: ContextTree, *, job: str) -> str:
    """The short pointer to the evidence on disk."""

    parts = [
        job.strip(),
        "",
        "# YOUR EVIDENCE",
        "",
        "It is on disk, in `context/`. Read it -- do not answer from this message alone.",
        "",
        tree.layout,
        "",
        "Every trajectory EVENT is present: the trajectory was not clipped to fit this "
        "mission. An individual observation may contain an explicit renderer-truncation "
        "marker; that marker is ours, not behavior by the solver. Do not diagnose it as a "
        "solver failure.",
        "",
        "Read `task.md` and the current harness first. Inventory every available rollout "
        "or candidate and inspect each at least once before deciding. For a candidate, "
        "compare what changed from its editing baseline, what behavior changed in its "
        "rollout, what improved, and what regressed or remained unresolved. Then "
        "deep-read the evidence relevant to any edit. Cite the specific trajectory "
        "moment behind every change; one you cannot trace to a moment is speculation.",
    ]
    return "\n".join(parts)
