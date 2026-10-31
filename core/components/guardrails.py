"""Adapter for the guardrails (c2) component."""

from __future__ import annotations

import re

from .base import ComponentAdapterBase

_PROHIBITION = re.compile(
    r"\b(forbid(?:den)?|must not|do not|prohibit(?:ed|s)?|never)\b",
    re.IGNORECASE,
)


class GuardrailsAdapter(ComponentAdapterBase):
    name = "guardrails"
    surface_paths = ("guardrails.md", "guardrails/")

    def validate(self, tree) -> list[str]:
        problems: list[str] = []
        for rel, content in tree.items():
            if not self._owns(rel):
                continue
            if not _PROHIBITION.search(content):
                problems.append(
                    f"{rel}: guardrails must declare at least one prohibition "
                    f"(add 'must not', 'forbid', 'prohibit', 'never', or 'do not')"
                )
        return problems

    def describe(self, edit=None) -> str:
        files = edit.files if edit is not None else {}
        return f"guardrails: {len(files)} file(s) declaring safety policy"
