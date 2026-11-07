"""HarnessStatusWidget - Displays current Harness run status."""

from textual.widgets import Static
from typing import Any, Optional


class HarnessStatusWidget(Static):
    """Widget showing current harness run mode, k, stage, finals, experience count."""

    def __init__(self, id: str = None):
        super().__init__(id=id)
        self.mode: str = "idle"
        self.k: int = 0
        self.current_stage: str = "idle"
        self.finals: list[str] = []
        self.experience_count: int = 0
        self.status: str = "idle"
        self._render()

    def _render(self) -> None:
        finals = ", ".join(self.finals) if self.finals else "none"
        text = (
            "[bold]Harness Run Status[/bold]\n\n"
            f"  Mode: [cyan]{self.mode}[/cyan]\n"
            f"  k: [cyan]{self.k}[/cyan]\n"
            f"  Stage: [yellow]{self.current_stage}[/yellow]\n"
            f"  Finals: [cyan]{finals}[/cyan]\n"
            f"  Lessons: [cyan]{self.experience_count}[/cyan]\n"
            f"  Status: [bold]{self.status}[/bold]\n"
        )
        self.update(text)

    def update_status(self, *args: Any, **kwargs: Any) -> None:
        """Accept flexible updates for run status.

        Supports:
        - ``update_status("running")``
        - ``update_status(mode=..., k=..., current_stage=..., finals=..., experience_count=..., status=...)``
        - ``update_status({"mode": ..., ...})``
        """
        data = {}
        if len(args) == 1 and isinstance(args[0], dict):
            data.update(args[0])
        elif len(args) == 1 and isinstance(args[0], str):
            data["status"] = args[0]
        elif args:
            # positional mapping: mode, k, current_stage, finals, experience_count, status
            fields = ["mode", "k", "current_stage", "finals", "experience_count", "status"]
            for idx, value in enumerate(args):
                if idx < len(fields):
                    data[fields[idx]] = value
        data.update(kwargs)

        for key, value in data.items():
            if key in {"mode", "k", "current_stage", "finals", "experience_count", "status"}:
                setattr(self, key, value)
        self._render()

    # Convenience alias matching other widgets.
    update_run_status = update_status

    def set_stage(self, stage: str) -> None:
        self.current_stage = str(stage)
        self._render()

    def set_finals(self, finals) -> None:
        self.finals = list(finals) if finals is not None else []
        self._render()

    def set_experience_count(self, count: int) -> None:
        self.experience_count = int(count)
        self._render()

    def to_running(self) -> None:
        self.status = "running"
        self._render()

    def to_success(self) -> None:
        self.status = "success"
        self._render()

    def to_failed(self) -> None:
        self.status = "failed"
        self._render()


__all__ = ["HarnessStatusWidget"]
