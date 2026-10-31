"""Base adapter contract for the eight Harness^2 component editors.

Every harness component implements the ComponentAdapter protocol so the registry
can load, apply, validate and diff them uniformly. The edit contract is
omitted-is-inherited.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from core.harness.tree import Tree

COMPONENT_NAMES = (
    "system_prompt",
    "guardrails",
    "memory",
    "tool_guidance",
    "subagents",
    "skills",
    "scripts",
    "plugins",
)


@dataclass
class ComponentEdit:
    component: str
    files: dict[str, str] = field(default_factory=dict)
    notes: str = ""


def _matches(rel: str, pattern: str) -> bool:
    rel = rel.replace("\\", "/").lstrip("/")
    if pattern.endswith("/"):
        prefix = pattern.rstrip("/")
        return rel == prefix or rel.startswith(prefix + "/")
    return rel == pattern


class ComponentAdapterBase:
    name: str = ""
    surface_paths: tuple[str, ...] = ()

    def _owns(self, rel: str) -> bool:
        return any(_matches(rel, p) for p in self.surface_paths)

    def load(self, tree: Tree) -> ComponentEdit:
        files = {rel: content for rel, content in tree.items() if self._owns(rel)}
        return ComponentEdit(component=self.name, files=files)

    def apply(self, tree: Tree, edit: ComponentEdit) -> Tree:
        result = dict(tree)
        for rel, content in (edit.files or {}).items():
            rel = rel.replace("\\", "/").strip("/")
            if content == "":
                result.pop(rel, None)
            else:
                result[rel] = content
        return result

    def validate(self, tree: Tree) -> list[str]:
        return []

    def describe(self, edit: ComponentEdit | None = None) -> str:
        files = edit.files if edit is not None else {}
        return f"{self.name}: {len(files)} file(s)"


@runtime_checkable
class ComponentAdapter(Protocol):
    name: str
    surface_paths: tuple[str, ...]

    def load(self, tree: Tree) -> ComponentEdit: ...

    def apply(self, tree: Tree, edit: ComponentEdit) -> Tree: ...

    def validate(self, tree: Tree) -> list[str]: ...

    def describe(self, edit: ComponentEdit | None = None) -> str: ...


class ComponentRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ComponentAdapter] = {}

    def register(self, adapter: ComponentAdapter) -> None:
        if not getattr(adapter, "name", ""):
            raise ValueError("adapter must have a non-empty name")
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> ComponentAdapter:
        if name not in self._adapters:
            raise KeyError(f"unknown component: {name!r}")
        return self._adapters[name]

    def names(self) -> list[str]:
        return list(self._adapters)

    def load_all(self, tree: Tree) -> dict[str, ComponentEdit]:
        return {name: adapter.load(tree) for name, adapter in self._adapters.items()}

    def apply_all(self, tree, edits) -> Tree:
        result = dict(tree)
        if isinstance(edits, dict):
            edit_values = list(edits.values())
        elif isinstance(edits, (list, tuple)):
            edit_values = list(edits)
        else:
            edit_values = [edits]
        for edit in edit_values:
            adapter = self.get(edit.component)
            result = adapter.apply(result, edit)
        return result

    def validate_all(self, tree: Tree) -> list[str]:
        problems: list[str] = []
        for name, adapter in self._adapters.items():
            for problem in adapter.validate(tree):
                problems.append(f"{name}: {problem}")
        return problems

    def diff(self, before: Tree, after: Tree) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for name, adapter in self._adapters.items():
            owned = adapter.surface_paths

            def _owned(rel: str) -> bool:
                return any(_matches(rel, p) for p in owned)

            before_subset = {k: v for k, v in before.items() if _owned(k)}
            after_subset = {k: v for k, v in after.items() if _owned(k)}
            result[name] = {
                "added": sorted(set(after_subset) - set(before_subset)),
                "removed": sorted(set(before_subset) - set(after_subset)),
                "modified": sorted(
                    rel for rel in set(before_subset) & set(after_subset)
                    if before_subset[rel] != after_subset[rel]
                ),
            }
        return result


def default_registry() -> ComponentRegistry:
    reg = ComponentRegistry()
    try:
        from .system_prompt import SystemPromptAdapter
    except Exception:  # pragma: no cover - adapter may not exist in partial checkouts
        SystemPromptAdapter = None

    try:
        from .guardrails import GuardrailsAdapter
    except Exception:  # pragma: no cover - adapter may not exist in partial checkouts
        GuardrailsAdapter = None

    try:
        from .memory import MemoryAdapter
    except Exception:  # pragma: no cover - adapter may not exist in partial checkouts
        MemoryAdapter = None

    try:
        from .tool_guidance import ToolGuidanceAdapter
    except Exception:  # pragma: no cover - adapter may not exist in partial checkouts
        ToolGuidanceAdapter = None

    try:
        from .subagents import SubagentsAdapter
    except Exception:  # pragma: no cover - adapter may not exist in partial checkouts
        SubagentsAdapter = None

    try:
        from .skills import SkillsAdapter
    except Exception:  # pragma: no cover - adapter may not exist in partial checkouts
        SkillsAdapter = None

    try:
        from .scripts import ScriptsAdapter
    except Exception:  # pragma: no cover - adapter may not exist in partial checkouts
        ScriptsAdapter = None

    try:
        from .plugins import PluginsAdapter
    except Exception:  # pragma: no cover - adapter may not exist in partial checkouts
        PluginsAdapter = None

    surface_paths_by_name = {
        "system_prompt": ("system_prompt.md", "AGENTS.md", "system_prompt/"),
        "guardrails": ("guardrails.md", "guardrails/"),
        "memory": ("memory.md", "memory/"),
        "tool_guidance": ("tool_guidance.md", "tool_guidance/"),
        "subagents": ("sub_agents/",),
        "skills": (".agents/skills/", "skills/"),
        "scripts": ("scripts/",),
        "plugins": (".codex/plugins/", "plugins/"),
    }
    for component_name in COMPONENT_NAMES:
        if component_name == "system_prompt" and SystemPromptAdapter is not None:
            reg.register(SystemPromptAdapter())
            continue
        if component_name == "guardrails" and GuardrailsAdapter is not None:
            reg.register(GuardrailsAdapter())
            continue
        if component_name == "memory" and MemoryAdapter is not None:
            reg.register(MemoryAdapter())
            continue
        if component_name == "tool_guidance" and ToolGuidanceAdapter is not None:
            reg.register(ToolGuidanceAdapter())
            continue
        if component_name == "subagents" and SubagentsAdapter is not None:
            reg.register(SubagentsAdapter())
            continue
        if component_name == "skills" and SkillsAdapter is not None:
            reg.register(SkillsAdapter())
            continue
        if component_name == "scripts" and ScriptsAdapter is not None:
            reg.register(ScriptsAdapter())
            continue
        if component_name == "plugins" and PluginsAdapter is not None:
            reg.register(PluginsAdapter())
            continue
        adapter = ComponentAdapterBase()
        adapter.name = component_name
        adapter.surface_paths = surface_paths_by_name.get(component_name, ())
        reg.register(adapter)
    return reg
