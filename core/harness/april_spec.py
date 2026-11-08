"""APRIL-domain HarnessSpec configuration."""

from __future__ import annotations

from pathlib import Path

from .spec import HarnessPrompts, HarnessSpec

APRIL_PROMPTS = HarnessPrompts(
    work=(
        "Improve APRIL's embodied harness for device control, MCP integrations, and "
        "networked physical workflows. Harnesses should make task completion more "
        "reliable across sensing, acting, and network operations."
    ),
    domain_word="capability domain",
    domain_guidance="Focus on device safety, authorization, and reliable execution.",
)


APRIL_SPEC = HarnessSpec(
    name="april",
    runs_root=Path("runs"),
    install_mode="workspace_config",
    prompts=APRIL_PROMPTS,
    channels={},
    domain_word="capability domain",
    leak_globs=(),
    allow_subagents=True,
    reserved_scripts=frozenset(),
    proposer_deliverables="contents",
    state_deliverable=False,
    obs_trunc=50_000,
)


__all__ = ["APRIL_PROMPTS", "APRIL_SPEC"]
