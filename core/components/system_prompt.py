"""Adapter for the system_prompt (c1) component."""

from __future__ import annotations

from .base import ComponentAdapterBase


class SystemPromptAdapter(ComponentAdapterBase):
    name = "system_prompt"
    surface_paths = ("system_prompt.md", "AGENTS.md", "system_prompt/")

    def validate(self, tree) -> list[str]:
        problems: list[str] = []
        for rel, content in tree.items():
            if not self._owns(rel):
                continue
            if not content.strip():
                problems.append(f"{rel}: system prompt must not be empty")
        return problems

    def describe(self, edit=None) -> str:
        files = edit.files if edit is not None else {}
        return f"system_prompt: {len(files)} file(s) managing the agent prompt"
