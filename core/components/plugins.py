"""Adapter for the plugins (c8) component."""

from __future__ import annotations

import re

from .base import ComponentAdapterBase

_EXPORT_RE = re.compile(r"\bexport\b")


class PluginsAdapter(ComponentAdapterBase):
    name = "plugins"
    surface_paths = (".codex/plugins/", "plugins/")

    def validate(self, tree) -> list[str]:
        problems: list[str] = []
        for rel, content in tree.items():
            if not self._owns(rel):
                continue
            if not rel.endswith(".ts"):
                continue
            if not _EXPORT_RE.search(content):
                problems.append(
                    f"{rel}: plugin must export at least one symbol "
                    f"(missing `export` statement)"
                )
        return problems

    def describe(self, edit=None) -> str:
        files = edit.files if edit is not None else {}
        return f"plugins: {len(files)} file(s) managing plugins/MCP adapters"
