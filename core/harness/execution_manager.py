"""Async Harness execution manager: the end-to-end task lifecycle.

`Harness` is the async facade over `schedule.run_task` — the ONE driver from a task id
to `adapter.execute()` (k bases roll once via `schedule._roll_bases`, every recursion
mode runs through `recursion.run_mode`, selection lands per mode, and `summary.json`
is written under the namespace task dir). There is deliberately no second path.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Sequence

from .proposer import ProposerError
from .recursion import ModeResult, Stage
from .schedule import TaskResult
from .schedule import run_task as _schedule_run_task

__all__ = ["Harness", "TaskResult", "ModeResult", "Stage"]


class _DryProposer:
    """The offline stand-in for the model Proposer: every session fails closed.

    A call raises `ProposerError` with zero transport visits, so `_run_stage` falls
    back to the current harness in one step. Fallback stages are still recorded
    sessions, so the ledger's R/P identity must hold on this path — that is exactly
    the arithmetic P0's acceptance proves.
    """

    spec = type(
        "ChannelSpecLike",
        (),
        {"kind": "dry", "model": "", "effort": "", "steps": 0, "timeout": 0},
    )()
    attempts = 1
    audit_dir = None

    def call(
        self,
        mission: str,
        context_dir: Path | str | None,
        label: str,
        *,
        system: str = "",
        timeout: int | None = None,
        max_attempts: int | None = None,
        harvest: str | None = None,
    ) -> Any:
        raise ProposerError(
            f"[{label}] dry: no model attached (APRIL_EXECUTOR=dry); the stage falls back",
            attempts=0,
        )


class Harness:
    """Async facade: one benchmark adapter, one task, all requested recursion modes."""

    def __init__(self, adapter: Any, *, runs_root=None, **_: Any) -> None:
        self.adapter = adapter
        spec = getattr(adapter, "spec", None)
        default_root = (
            Path(getattr(spec, "runs_root", Path("runs"))) if spec is not None else Path("runs")
        )
        self.runs_root = runs_root if runs_root is not None else default_root

    def score(self, selection=None, *, run_dir=None, task_id=""):
        from .judge import score_after_selection

        return score_after_selection(
            self.adapter, selection, run_dir=run_dir, task_id=task_id or ""
        )

    def _proposers(self, prop=None, selector_prop=None) -> tuple[Any, Any]:
        """The (prop, selector) pair for `schedule.run_task`.

        A caller passing `prop=` / `selector_prop=` runs real model sessions. Without
        one, the offline dry path fails closed: `_DryProposer` serves both, proposal
        stages fall back to the current harness, and a k>1 selector falls back in
        `selection._fallback`.
        """
        prop = prop if prop is not None else _DryProposer()
        selector_prop = selector_prop if selector_prop is not None else prop
        return prop, selector_prop

    async def run_task(
        self,
        task_id: str,
        *,
        mode: str = "both",
        k: int | None = None,
        k_value: int | None = None,
        modes: Sequence[str] | None = None,
        seed: int | None = None,
        tag: str = "",
        **kwargs: Any,
    ) -> TaskResult:
        """Alias-preserving delegate to `schedule.run_task`, run in a worker thread.

        'both' -> both modes gathered ('agg' and 'seq'); 'parallel'/'sequential' map to
        'agg'/'seq'. k bases roll once and stay shared across modes; each mode then
        recurses through `recursion.run_mode` — Propose-Probe-Compose with `Proposer` —
        and blind selection lands per mode. `summary.json` records the mode blocks and
        each mode's ledger.
        """
        requested = list(modes) if modes is not None else mode
        if isinstance(requested, str):
            requested = ["agg", "seq"] if requested == "both" else [requested]
        aliases = {"parallel": "agg", "sequential": "seq"}
        run_modes = [aliases.get(str(m), str(m)) for m in requested]
        k_int = int(k if k is not None else (k_value if k_value is not None else 1))
        prop, selector_prop = self._proposers(
            kwargs.pop("prop", None), kwargs.pop("selector_prop", None)
        )
        return await asyncio.to_thread(
            _schedule_run_task,
            task_id,
            k_int,
            adapter=self.adapter,
            prop=prop,
            selector_prop=selector_prop,
            runs_root=Path(self.runs_root),
            modes=run_modes,
            seed=seed,
            tag=tag,
            **kwargs,
        )
