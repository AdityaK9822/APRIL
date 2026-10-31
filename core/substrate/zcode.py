# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The zcode substrate: ZCode CLI's editable surface, defined from its own docs.

Facts come from ZCode's usage and design docs (`ZCode/apps/zcode-cli/docs/`):
instructions merge `~/.zcode/AGENTS.md` (user, not ours) then workspace `AGENTS.md`
(project, editable); skills load on demand from `.agents/skills/<name>/SKILL.md`
with frontmatter `name` matching the directory; custom agents are
`.zcode/agents/<name>.md` dispatched through the model-visible `Agent` tool by
`subagent_type`; hooks arrive as a run-config file with `hooks.enabled` +
`hooks.events` over the v2 event list; local plugins need
`.zcode-plugin/plugin.json` and run-config enablement. This module only WRITES
workspace files and seeds memory — ZCode source is never touched.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..harness.tree import SurfaceSpec, Tree

# zcode hooks: the exact v2 event list from packages/contracts/src/hooks/index.ts.
ZCODE_HOOK_EVENTS = frozenset(
    {
        "SessionStart",
        "UserPromptSubmit",
        "PreToolUse",
        "PermissionRequest",
        "PostToolUse",
        "PostToolUseFailure",
        "Stop",
    }
)

ZCODE_SURFACE = SurfaceSpec(
    name="zcode",
    # c1 persona/procedure, c2 guardrails and c4 tool guidance share the ONE always-on
    # instruction file zcode assembles: the workspace AGENTS.md.
    always_on=("AGENTS.md",),
    always_on_max=60_000,  # ponytail ceiling: zcode books no documented cap; kept so
    # always-on prose cannot silently become the whole context.
    always_on_cap_reason=(
        "AGENTS.md is merged into every request's instruction block; long material "
        "belongs in an on-demand .agents/skills/<name>/SKILL.md"
    ),
    skill_dir=".agents/skills",
    skill_name_rule="must_match",  # docs 08: frontmatter name must equal the dir name
    trigger_hint=(
        "add a trigger line for it in AGENTS.md, e.g. 'When <situation>, use "
        "skills/{name}' naming the skill"
    ),
    autotrigger_file="AGENTS.md",
    trigger_line="When relevant, use the `{name}` skill: {desc}.",
    # c5: the model-visible `Agent` tool (historical alias Task) dispatches by
    # subagent_type: <name>; each agent is .zcode/agents/<name>.md.
    subagent_path=".zcode/agents/{name}.md",
    subagent_requires_mode=False,
    # c8 OPTION: a local plugin loads from its manifest only.
    plugin_dir=".zcode/plugins",
    plugin_manifest=".zcode/plugins/{name}/.zcode-plugin/plugin.json",
    # c2 enforcement lever lives in the project run config: hooks block is validated
    # against the v2 event list. NOTE: workspace hooks stay UNTRUSTED (docs 09) until
    # the launcher grants trust; P1 ships schema validation, not trust wiring.
    hooks_file=".zcode/config.json",
    hooks_shape="nested",
    hook_types=("process", "command"),
    hook_events=ZCODE_HOOK_EVENTS,
    # c3 variant: the memory seed, materialised into the isolated cli storage root by
    # the adapter (MEMORY.md is never read from the workspace by zcode itself).
    memory_file="MEMORY.md",
    memory_max=40_000,  # ponytail ceiling: memory text is injected by the Main Memory prompt.
    compile_skill_scripts=True,
    reject_empty_always_on=True,
    stubs=(),
)


def memory_project_key(workspace: Path) -> str:
    """ZCode's own workspace key: sha256 of the resolved path, first 16 hex chars.

    Replicated from ZCode `packages/core/src/memory/project-root.ts` (keySource =
    workspaceIdentity if set, else the resolved workspace path — POSIX keeps case;
    Windows lowercases, which is irrelevant for paths we stage). Ponytail: this
    replicates a zcode-internal contract; re-verify against that file on any ZCode
    update or the memory seed silently reaches the wrong store.
    """
    return hashlib.sha256(str(workspace.resolve(strict=False)).encode()).hexdigest()[:16]


def memory_project_slug(workspace: Path) -> str:
    """ZCode's slug: lowercased sanitized basename, shortened to 48 chars."""
    slug = re.sub(r"[^a-z0-9._-]+", "-", Path(workspace).name.lower()).strip("-")
    return slug[:48] or "project"


def memory_root_for(workspace: Path, data_base_dir: Path) -> Path:
    """The isolated memory root a zcode process reads for this workspace:
    `<ZCODE_DATA_BASE_DIR>/.zcode/cli/memories/projects/<slug>-<hash>/memory/`."""
    cli_root = data_base_dir / ".zcode" / "cli"
    key = f"{memory_project_slug(workspace)}-{memory_project_key(workspace)}"
    return cli_root / "memories" / "projects" / key / "memory"


def seed_memory(surface: SurfaceSpec, tree: Tree, workspace: Path, run_home: Path) -> Path | None:
    """Materialise the c3 seed: workspace MEMORY.md into the isolated memory store."""
    if surface.memory_file is None or surface.memory_file not in tree:
        return None
    root = memory_root_for(workspace, Path(run_home))
    root.mkdir(parents=True, exist_ok=True)
    (root / "MEMORY.md").write_text(tree[surface.memory_file], encoding="utf-8")
    return root


@dataclass
class ZcodeSubstrate:
    """The substrate half of the benchmark seam: a name and the surface schema."""

    name: str = "zcode"
    surface_spec: SurfaceSpec = field(default_factory=lambda: ZCODE_SURFACE)

    def surface(self) -> SurfaceSpec:
        return self.surface_spec


ZCODE_SUBSTRATE = ZcodeSubstrate()


__all__ = [
    "ZCODE_HOOK_EVENTS",
    "ZCODE_SURFACE",
    "ZcodeSubstrate",
    "ZCODE_SUBSTRATE",
    "memory_project_key",
    "memory_project_slug",
    "memory_root_for",
    "seed_memory",
]
