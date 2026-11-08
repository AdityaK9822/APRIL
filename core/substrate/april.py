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

"""APRIL's own substrate: the editable file surface of a deployed APRIL harness.

P0 ships the surface schema plus `dry` structural parses; `materialise`/`execute`/
`read_trajectory`/`preflight` arrive with the zcode substrate in P1. Ponytail: this
substrate stages no runtime until then -- `APRIL_EXECUTOR=live` is a loud error.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..harness.tree import SurfaceSpec

APRIL_SURFACE = SurfaceSpec(
    name="april",
    # c1/c2/c4 ride along with every APRIL request; c3/c6..c8 exist but are off-surface
    # until a first deployment needs them.
    always_on=("systemprompt.md", "guardrails.md", "tool_guidance.md"),
    always_on_max=40_000,
    always_on_cap_reason=(
        "always-on files are sent with every request and every round of every "
        "recursion; long material becomes an on-demand .agents/skills/<name>/SKILL.md"
    ),
    skill_dir=".agents/skills",
    skill_name_rule="dir",
    trigger_hint=(
        "add a line in systemprompt.md that names the skill and says when to use it"
    ),
    autotrigger_file="systemprompt.md",
    trigger_line="When relevant, use the `{name}` skill: {desc}.",
    subagent_requires_mode=False,
    plugin_dir=None,
    hooks_file=None,
    hook_events=frozenset(),
    compile_skill_scripts=False,
    reject_empty_always_on=True,
    stubs=(),
)


@dataclass
class AprilSubstrate:
    """The `SubstrateLike` half core needs: a name and the surface schema."""

    name: str = "april"
    surface_spec: SurfaceSpec = APRIL_SURFACE

    def surface(self) -> SurfaceSpec:
        return self.surface_spec


APRIL_SUBSTRATE = AprilSubstrate()


__all__ = ["APRIL_SURFACE", "AprilSubstrate", "APRIL_SUBSTRATE"]
