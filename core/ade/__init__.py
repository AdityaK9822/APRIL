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

"""The ADE: adopted harnesses deploy to `.ade/harnesses/<persona>/<domain>/`.

Spec: `docs/spec/persona-dimension.md` (authored before this code). The layout is
runtime state, like `runs/`: git-ignored, pointed at a temp root by the offline
self-checks through `APRIL_ADE_ROOT`. Personal facts stay out of this tree —
`.ade/etc/` carries the local override only.

The ADE must itself be an APRIL agent: every operation is a plain callable AND a
CLI (`python3 -m core.ade`), so the agent drives deployment with its own shell
tool exactly as a human would. There is no UI-only path.

Deployment = validate a tree on a `SurfaceSpec`, optionally stamp the persona
(clamped by the always-on `## persona:` cap), fingerprint it, and index it. Boot =
resolve the deployed tree for a persona (or the committed profile), map c1 into
the system message, c2 into the permission layer, and `derive().temperature` into
sampling — the `toRequest()` semantics, at runtime.
"""

from .boot import ActionGuard, PersonaBoot, apply_to_runtime, boot, load_local_overrides, unboot
from .deploy import (
    ADE_ROOT_ENV,
    INDEX_NAME,
    deployment_root,
    deployed_dir,
    deploy,
    deployed_rows,
    index_path,
    load_deployed,
)
from . import views

__all__ = [
    "ADE_ROOT_ENV",
    "INDEX_NAME",
    "deployment_root",
    "deployed_dir",
    "deploy",
    "deployed_rows",
    "index_path",
    "load_deployed",
    "PersonaBoot",
    "ActionGuard",
    "boot",
    "apply_to_runtime",
    "unboot",
    "load_local_overrides",
    "views",
]
