"""Adapter for the tool_guidance (c4) component."""

from __future__ import annotations

from .base import ComponentAdapterBase


class ToolGuidanceAdapter(ComponentAdapterBase):
    name = "tool_guidance"
    surface_paths = ("tool_guidance.md", "tool_guidance/")

    def describe(self, edit=None) -> str:
        files = edit.files if edit is not None else {}
        return f"tool_guidance: {len(files)} file(s) configuring tools and MCP guidance"
