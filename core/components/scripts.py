"""Adapter for the scripts (c7) component."""

from __future__ import annotations

import re

from core.harness.tree import _py_compiles

from .base import ComponentAdapterBase

_RESERVED = frozenset({"read_doc.py", "pack.py", "unpack.py"})
_REF_RE = re.compile(r"(?:[A-Za-z0-9_.\-]+/)*scripts/[A-Za-z0-9_.\-]+\.py")


class ScriptsAdapter(ComponentAdapterBase):
    name = "scripts"
    surface_paths = ("scripts/",)

    def validate(self, tree) -> list[str]:
        problems: list[str] = []

        # Every script must compile.
        for rel, content in tree.items():
            if not self._owns(rel) or not rel.endswith(".py"):
                continue
            errs: list[str] = []
            _py_compiles(rel, content, errs)
            problems.extend(errs)

        # Every non-reserved script reference must resolve to a shipped file.
        seen: set[tuple[str, str]] = set()
        for source_rel, content in tree.items():
            for ref in _REF_RE.findall(content):
                key = (source_rel, ref)
                if key in seen:
                    continue
                seen.add(key)
                if ref.rsplit("/", 1)[-1] in _RESERVED:
                    continue
                if ref not in tree:
                    problems.append(
                        f"{source_rel} invokes `{ref}` but that file is not in the harness"
                    )

        return problems

    def describe(self, edit=None) -> str:
        files = edit.files if edit is not None else {}
        return f"scripts: {len(files)} file(s) managing local scripts"
