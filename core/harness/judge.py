"""Judge / score boundary: scoring runs only after selection succeeds."""

from __future__ import annotations

from typing import Any


def selection_ok(selection: Any) -> bool:
    """Whether selection succeeded and an artifact may be scored."""
    if selection is None:
        return False
    if isinstance(selection, dict):
        return bool(selection.get("ok", selection.get("success", False)))
    return bool(getattr(selection, "ok", getattr(selection, "success", False)))


def score_after_selection(
    adapter: Any,
    selection: Any = None,
    *,
    run_dir: Any = None,
    task_id: str = "",
) -> dict | None:
    """Return ``adapter.score(run_dir, task_id)`` only after selection succeeds.

    A missing judge result is represented as ``None``, never as zero, and scoring
    is never attempted when selection did not succeed.
    """
    if not selection_ok(selection):
        return None
    if run_dir is None:
        return None
    scorer = getattr(adapter, "score", None)
    if not callable(scorer):
        return None
    try:
        return scorer(run_dir, task_id)
    except Exception:
        return None


class JudgeBoundary:
    """Small explicit boundary object for delayed scoring."""

    def __init__(self, adapter: Any = None):
        self.adapter = adapter

    def score(self, selection: Any = None, *, run_dir: Any = None, task_id: str = ""):
        return score_after_selection(self.adapter, selection, run_dir=run_dir, task_id=task_id)


# Compatibility aliases.
delayed_score = score_after_selection
Judge = JudgeBoundary

__all__ = [
    "Judge",
    "JudgeBoundary",
    "delayed_score",
    "score_after_selection",
    "selection_ok",
]
