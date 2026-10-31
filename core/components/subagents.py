"""Adapter for the subagents (c5) component."""

from __future__ import annotations

import re

from .base import ComponentAdapterBase


class SubagentsAdapter(ComponentAdapterBase):
    name = "subagents"
    surface_paths = ("sub_agents/",)

    def __init__(self, subagent_requires_mode: bool = False, **kwargs) -> None:
        self.subagent_requires_mode = bool(
            kwargs.get("requires_mode", subagent_requires_mode)
        )

    def validate(self, tree) -> list[str]:
        problems: list[str] = []
        for rel, content in tree.items():
            if not self._owns(rel):
                continue
            if not rel.endswith("AGENT.md"):
                continue
            if not re.search(r"^description:\s*\S", content, re.M):
                problems.append(f"{rel}: AGENT.md needs a `description:`")
            if self.subagent_requires_mode and not re.search(
                r"^mode:\s*subagent\s*$", content, re.M
            ):
                problems.append(f"{rel}: AGENT.md needs frontmatter `mode: subagent`")
        return problems

    def describe(self, edit=None) -> str:
        files = edit.files if edit is not None else {}
        return f"subagents: {len(files)} file(s) managing sub-agent definitions"
