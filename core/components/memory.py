"""Adapter for the memory (c3) component."""

from __future__ import annotations

from .base import ComponentAdapterBase


class MemoryAdapter(ComponentAdapterBase):
    name = "memory"
    surface_paths = ("memory.md", "memory/")

    def describe(self, edit=None) -> str:
        files = edit.files if edit is not None else {}
        return f"memory: {len(files)} file(s) configuring cross-session memory"
