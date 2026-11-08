"""The zcode benchmark adapter: materialize a harness, run the zcode CLI, parse the stream.

The adapter stays at the PROCESS boundary (ZCode is never built, configured or
edited by APRIL): the batch recipe is ZCode's own documented one
(`ZCode/apps/zcode-cli/docs/usage/13-automation.md`):

    zcode --prompt <p> --cwd <workdir> --mode yolo \
        --disallowed-tools "AskUserQuestion EnterPlanMode ExitPlanMode" \
        --output-format stream-json --no-color

with per-sample isolation `ZCODE_DATA_BASE_DIR=<runHome>` (+ HOME/USERPROFILE)
and a one-shot environment whitelist. The deliverable is a FORCED OUTPUT FILE:
each task names `deliverables/<file>` inside the workspace; a run that ends
without it is not delivered (saved as failure evidence, never counted as
success). Retry semantics are copied from the claude channel shape (attempts
with a fixed backoff, wall timeout per attempt); each attempt re-spawns a FRESH
sample — `--resume` is deliberately not used, because a timed-out rollout is not
a session worth continuing, it is evidence to keep and replace.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping

from ..substrate.zcode import ZcodeSubstrate, seed_memory
from . import config
from . import tree as harness_tree
from .spec import HarnessPrompts, HarnessSpec, _DEFAULT_CHANNEL_MODEL, resolve_channel_model

BENCHTASKS_DIR = Path(__file__).resolve().parent / "benchtasks"
BASETREE_DIR = Path(__file__).resolve().parent / "basetree" / "zcode"

# The batch recipe's fixed CLI arguments, straight from the zcode docs.
BATCH_ARGS = (
    "--mode",
    "yolo",
    "--disallowed-tools",
    "AskUserQuestion EnterPlanMode ExitPlanMode",
    "--output-format",
    "stream-json",
    "--no-color",
)
# Non-inherited env names allowed through, from the same doc (case-insensitive match).
_ENV_ALLOW = re.compile(r"^(path|systemroot|windir|comspec|pathext|temp|tmp|tmpdir)$", re.I)
# Copied from the claude channel: attempts with a fixed backoff, wall clock per attempt.
ATTEMPTS = max(1, int(getattr(config, "TRANSPORT_ATTEMPTS", 2)))
RETRY_BACKOFF_S = 10
DEFAULT_WALL_S = 3600


def _runs_root(spec: HarnessSpec) -> Path:
    """One runs root adapter-side and schedule-side: the APRIL_RUNS_ROOT override when
    set, else spec.runs_root."""
    env = os.environ.get("APRIL_RUNS_ROOT", "").strip()
    return Path(env) if env else Path(getattr(spec, "runs_root", Path("runs")))


@dataclass(frozen=True)
class BenchTask:
    """One authored mini-task under `core/harness/benchtasks/`."""

    task_id: str  # "<domain>/<name>"
    domain: str
    name: str
    prompt: str  # task.md text, exactly as authored
    deliverable: str  # the FORCED deliverable path, workspace-relative
    slots: Mapping[str, str]
    fixtures: tuple[tuple[str, str], ...]  # (fixture filename, content)


def load_benchtasks(root: Path = BENCHTASKS_DIR) -> dict[str, BenchTask]:
    """Read every authored task dir: task.md (the prompt), deliverable.md (notes kept
    for provenance), slots.json (HarnessPrompts slots + the forced deliverable),
    fixtures/* (staged into the workspace as input/)."""
    tasks: dict[str, BenchTask] = {}
    if not root.is_dir():
        return tasks
    for task_md in sorted(root.glob("*/*/task.md")):
        d = task_md.parent
        task_id = f"{d.parent.name}/{d.name}"
        slots = json.loads((d / "slots.json").read_text(encoding="utf-8"))
        fixtures = tuple(
            (p.name, p.read_text(encoding="utf-8", errors="replace"))
            for p in sorted((d / "fixtures").glob("*"))
            if p.is_file()
        )
        tasks[task_id] = BenchTask(
            task_id=task_id,
            domain=d.parent.name,
            name=d.name,
            prompt=task_md.read_text(encoding="utf-8"),
            deliverable=str(slots["deliverable"]),
            slots=slots,
            fixtures=fixtures,
        )
    return tasks


@dataclass
class ZcodeAdapter:
    """Benchmark seam for the zcode substrate: authored mini-tasks + the CLI recipe."""

    spec: HarnessSpec = field(
        default_factory=lambda: HarnessSpec(
            name="zcode",
            runs_root=Path("runs"),
            install_mode="workspace_config",  # config.json + AGENTS.md live in the workspace
            prompts=HarnessPrompts(
                work="Improve APRIL's embodied harness for networked physical work.",
                domain_word="capability domain",
                domain_guidance="Read device and network state before planning a write.",
            ),
            # The P1 selection channel is claude_cli (P1-1.6: proposer on claude_cli).
            # Offline run_task callers pass a stand-in selector_prop explicitly.
            channels={
                "selector": resolve_channel_model(
                    kind="claude_cli", model=_DEFAULT_CHANNEL_MODEL["claude_cli"]
                )
            },
            domain_word="capability domain",
            allow_subagents=True,
            reserved_scripts=frozenset(),
            proposer_deliverables="contents",
            state_deliverable=False,
            obs_trunc=50_000,
        )
    )
    substrate: ZcodeSubstrate = field(default_factory=ZcodeSubstrate)
    tasks_dir: Path = BENCHTASKS_DIR
    # P2: the committed profile whose compiled persona rides the proposal
    # missions ("" = persona-free). Mirrored onto spec.profile so every prompt
    # seam (resolve_prompts) sees it.
    profile: str = ""

    def __post_init__(self) -> None:
        if str(self.profile or "").strip() and self.spec.profile != self.profile:
            self.spec = replace(self.spec, profile=self.profile)

    # -- the benchmark seam ------------------------------------------------------

    def _tasks(self) -> dict[str, BenchTask]:
        return load_benchtasks(self.tasks_dir)

    def tasks(self, split: str = "all") -> list[str]:
        return sorted(self._tasks())

    def domain_of(self, task_id: str) -> str:
        return self._task(task_id).domain

    def task_prompt(self, task_id: str) -> str:
        return self._task(task_id).prompt

    def task_files(self, task_id: str) -> dict[str, str]:
        return dict(self._task(task_id).fixtures)

    def prompts_for(self, task_id: str) -> HarnessPrompts:
        """Per-task slot values; the HarnessPrompts constructor enforces the
        no-grader-vocabulary rule on every visible slot."""
        s = self._task(task_id).slots
        return HarnessPrompts(
            work=str(s.get("work", "")),
            inv_levers=str(s.get("inv_levers", "")),
            dom_levers=str(s.get("dom_levers", "")),
            yardstick=str(s.get("yardstick", "")),
            domain_word=str(s.get("domain_word", "capability domain")),
            domain_guidance=str(s.get("domain_guidance", "")),
        )

    def base_harness(self) -> Path:
        return BASETREE_DIR

    def validate_tree(self, tree: harness_tree.Tree) -> None:
        harness_tree.validate(
            self.substrate.surface(),
            tree,
            allow_subagents=self.spec.allow_subagents,
            reserved_scripts=harness_tree.RESERVED_SCRIPTS | set(self.spec.reserved_scripts),
        )

    def score(self, run_dir, task_id: str):
        # P1 has no grader vocabulary anywhere in the slots; a missing judge result is
        # None, never a zero.
        return None

    def _task(self, task_id: str) -> BenchTask:
        tasks = self._tasks()
        if task_id not in tasks:
            raise KeyError(f"unknown benchtask {task_id!r}; known: {sorted(tasks)}")
        return tasks[task_id]

    # -- execution: the batch recipe ----------------------------------------------

    def execute(self, task_id: str, harness_dir, run_id: str, *, timeout=None) -> Path:
        root = _runs_root(self.spec)
        parts = [p for p in str(run_id).replace("\\", "/").split("/") if p not in ("", ".")]
        if not parts or ".." in parts:
            raise ValueError(f"run_id {run_id!r} must name a run dir under the runs root")
        run_dir = root.joinpath(*parts)
        workspace = run_dir / "workspace"
        run_home = run_dir / "zcode_home"
        run_dir.mkdir(parents=True, exist_ok=True)

        task = self._task(task_id)
        # The harness tree: the proposed one, else the shipped base tree.
        if harness_dir is not None and Path(harness_dir).is_dir():
            tree = harness_tree.read_tree(self.substrate.surface(), Path(harness_dir))
            harness_line = f"harness: {len(tree)} file(s) on the surface"
        else:
            tree = harness_tree.read_tree(self.substrate.surface(), BASETREE_DIR)
            harness_line = "harness: base (inherited)"

        # Spawn the documented batch recipe; each attempt is a FRESH sample: the
        # workspace and runHome are rebuilt so a timed-out rollout never leaks state
        # into its retry (launch failure / cancel / timeout -> keep the failure
        # evidence, count nothing as success).
        deliverable_rel = task.deliverable
        prompt = (
            f"{task.prompt}\n\n"
            "REMINDER: the deliverable is a forced output file. Write it to "
            f"`{deliverable_rel}` relative to the workspace. The run ends with the file "
            "existing and non-empty, or not delivered at all."
        )
        stream_path = run_dir / "agent_stream.jsonl"
        stderr_path = run_dir / "agent_stderr.txt"
        wall = int(timeout or DEFAULT_WALL_S)
        TRY_TO_TRY = max(1, ATTEMPTS)
        attempts_note: list[str] = []
        outcome = ""
        mem_root: Path | None = None
        for attempt in range(1, TRY_TO_TRY + 1):
            _reset_dir(workspace)
            _reset_dir(run_home)
            harness_tree.write_tree(self.substrate.surface(), tree, workspace)
            (workspace / "input").mkdir(parents=True, exist_ok=True)
            for fname, content in task.fixtures:
                (workspace / "input" / fname).write_text(content, encoding="utf-8")
            # c3 seed: MEMORY.md goes to the isolated runtime store, never the workspace.
            mem_root = seed_memory(self.substrate.surface(), tree, workspace, run_home)
            code, err = _spawn_cli(prompt, workspace, run_home, stream_path, stderr_path, wall)
            if code == 0:
                text = stream_path.read_text(encoding="utf-8", errors="replace")
                if text.strip():
                    outcome = text
                    break
                code = 1  # an exit-0 with no stream is a failed sample, not success
                err = "exit 0 but the stream was empty"
            attempts_note.append(
                f"attempt {attempt}/{TRY_TO_TRY}: exit {code}\n{_indent(err.strip()[:400])}"
            )
            if attempt < TRY_TO_TRY:
                time.sleep(RETRY_BACKOFF_S)
        if not outcome:
            attempts_note.append(
                "no usable stream after all attempts: run not delivered (evidence kept)"
            )

        # The forced-deliverable contract: workspace deliverables ARE the run's.
        copied = _extract_deliverable(workspace, run_dir)

        # Trajectory: the launch facts, then the stream parsed to a transcript
        # (obs-truncated downstream by the schedule; kept whole here for the improver).
        memory_line = (
            f"memory seed: staged at {mem_root.relative_to(run_dir)}"
            if mem_root
            else "memory seed: none"
        )
        notes = [
            f"task_id: {task_id}",
            f"run_id: {run_id}",
            harness_line,
            memory_line,
            f"deliverable: {deliverable_rel} (forced output file)",
            *attempts_note,
            (
                f"delivered: {', '.join(sorted(copied))}"
                if copied
                else f"missing: {deliverable_rel} was not produced"
            ),
        ]
        (run_dir / "trajectory.txt").write_text(
            "zcode adapter rollout (process boundary; cli output below).\n"
            + "\n".join(notes)
            + "\n\n"
            + _stream_transcript(stream_path),
            encoding="utf-8",
        )
        return run_dir

    def delivered(self, run_dir) -> bool:
        d = Path(run_dir) / "deliverables"
        return d.is_dir() and any(p.is_file() and p.stat().st_size > 0 for p in d.iterdir())

    def trajectory(self, run_dir, *, obs_trunc: int = 50_000) -> str:
        try:
            body = (Path(run_dir) / "trajectory.txt").read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            return ""
        return body[:obs_trunc] + (
            f"\n... [trajectory clipped to {obs_trunc} chars]" if len(body) > obs_trunc else ""
        )

    def deliverable_files(self, run_dir) -> dict[str, str]:
        d = Path(run_dir) / "deliverables"
        if not d.is_dir():
            return {}
        return {p.name: str(p) for p in sorted(d.iterdir()) if p.is_file()}

    def deliverable_text(self, run_dir) -> str:
        files = self.deliverable_files(run_dir)
        if not files:
            return ""
        return Path(next(iter(files.values()))).read_text(encoding="utf-8", errors="replace")


# helpers ----------------------------------------------------------------------


def _reset_dir(d: Path) -> None:
    """Empty a dir in place: reruns of the same run_id reuse it, never accumulate."""
    for p in sorted(d.rglob("*"), reverse=True):
        try:
            if p.is_dir() and not p.is_symlink():
                p.rmdir()
            else:
                p.unlink()
        except OSError:
            pass


def _child_env(run_home: Path) -> dict[str, str]:
    """The one-shot environment whitelist from the zcode batch recipe, plus the
    per-sample isolation triple (HOME/USERPROFILE/ZCODE_DATA_BASE_DIR = runHome)."""
    env = {k: v for k, v in os.environ.items() if _ENV_ALLOW.match(k)}
    env.update(
        {
            "HOME": str(run_home),
            "USERPROFILE": str(run_home),
            "ZCODE_DATA_BASE_DIR": str(run_home),
        }
    )
    return env


def _zcode_bin() -> str:
    """The CLI binary, read at SPAWN time: `APRIL_ZCODE_BIN` is the per-invocation
    override (offline self-checks point it at the process-boundary stub), and
    config.ZCODE_BIN — bound at import — is the fallback."""
    return os.environ.get("APRIL_ZCODE_BIN", "").strip() or config.ZCODE_BIN


def _spawn_cli(
    prompt: str, workspace: Path, run_home: Path, stream_path: Path, stderr_path: Path, wall: int
) -> tuple[int, str]:
    """One CLI attempt with the recipe's argument array and env; returns (exit code,
    collected stderr). The whole process TREE is killed on timeout — a killed parent
    is not a finished sample. A launch failure (e.g. no binary) is failed evidence
    too: it is retried like any other attempt, never raised."""
    cmd = [_zcode_bin(), "--prompt", prompt, "--cwd", str(workspace), *BATCH_ARGS]
    with open(stream_path, "wb") as out, open(stderr_path, "wb") as err:
        try:
            proc = subprocess.Popen(  # noqa: S603 — argument array, no shell
                cmd,
                cwd=str(workspace),
                env=_child_env(run_home),
                stdout=out,
                stderr=err,
                shell=False,
                start_new_session=True,
            )
        except OSError as exc:
            err.write(f"adapt: launch failed: {exc}\n".encode())
            return 127, f"launch failed: {exc}"
        try:
            code = proc.wait(timeout=wall)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
            proc.wait(timeout=10)
            err.write(
                f"\nadapt: killed the whole process tree after the {wall}s wall timeout\n".encode()
            )
            return 124, f"timeout after {wall}s"
    return code, stderr_path.read_text(encoding="utf-8", errors="replace")


def _extract_deliverable(workspace: Path, run_dir: Path) -> list[str]:
    """The forced-deliverable contract: copy workspace deliverables into the run dir.
    Returns the copied names (empty means the run is not delivered)."""
    src = workspace / "deliverables"
    if not src.is_dir():
        return []
    dst = run_dir / "deliverables"
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for p in sorted(src.glob("*")):
        if p.is_file():
            (dst / p.name).write_bytes(p.read_bytes())
            copied.append(p.name)
    return copied


def _stream_transcript(stream_path: Path) -> str:
    """stream-json events -> a readable transcript. Unknown event shapes stay as raw
    lines; a `result` event's text is the final answer."""
    try:
        raw = stream_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(no stream)"
    lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            lines.append(f"[raw] {line[:400]}")
            continue
        kind = ev.get("type") or ev.get("event") or "?"
        text = ""
        msg = ev.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, list):
                text = " ".join(
                    c.get("text", "") for c in content if isinstance(c, dict)
                ).strip()
            elif isinstance(content, str):
                text = content.strip()
        elif isinstance(msg, str):
            text = msg.strip()
        if not text and isinstance(ev.get("result"), str):
            text = ev["result"].strip()
        if text:
            lines.append(f"[{kind}] {text}")
        else:
            mini = {k: v for k, v in ev.items() if k != "message"}
            lines.append(f"[{kind}] {json.dumps(mini, ensure_ascii=False)[:400]}")
    return "\n".join(lines) if lines else "(empty stream)"


def _indent(s: str) -> str:
    return "\n".join("    " + ln for ln in s.splitlines())


def make_adapter() -> ZcodeAdapter:
    return ZcodeAdapter()


__all__ = [
    "BENCHTASKS_DIR",
    "BASETREE_DIR",
    "BATCH_ARGS",
    "BenchTask",
    "ZcodeAdapter",
    "load_benchtasks",
    "make_adapter",
]
