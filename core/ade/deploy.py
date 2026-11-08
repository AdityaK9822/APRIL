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

"""Deployment: an adopted tree lands in `.ade/harnesses/<persona>/<domain>/`.

Rules (spec: `docs/spec/persona-dimension.md` 2-3):

- the source must be a valid tree on the given `SurfaceSpec` — refuse, never
  sanitize, an invalid one (`tree.validate` raising is the contract);
- a persona-free adopted tree can be stamped with the persona it deploys under:
  the compiled c1 block goes to `systemprompt.md`, the protocols to
  `guardrails.md`, both under a `## persona:` tag inside the always-on cap;
- every deployment is fingerprinted (`runmark.fingerprint`) and indexed in
  `index.json`; the loader refuses a tree whose file bytes changed after the
  fingerprint was written.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..harness import tree as tree_mod
from ..harness.library import domain_dir

ADE_ROOT_ENV = "APRIL_ADE_ROOT"
INDEX_NAME = "index.json"

# Deployments address personas by their committed profile id; keep them
# path-safe so `<persona>` is a real directory segment everywhere.
_PERSONA_RX = re.compile(r"[a-z0-9][a-z0-9_-]*")

# Deployed-trees carry the persona as an always-on `## persona:` section too,
# but the ceiling is a DEPLOYMENT ceiling, not the engine's proposal cap: the
# compiled persona is the runtime persona's system prompt and cannot become an
# on-demand skill. 6000 fits every committed profile today (APRIL ≈ 4.4k).
# # ponytail: the real ceiling is the runtime output budget; revisit when a
# runtime token budget exists, or split long persona prose into skills with
# only the kernel always-on.
ADE_PERSONA_CAP = 6000

# A stamp is persona text on an always-on file — exactly what the tree census
# caps, so the engine regex is kept as the detection contract.
_PERSONA_SECTION_RX = re.compile(r"^#{2,3}\s*persona\s*:.*$", re.I | re.M)


@dataclass(frozen=True)
class DeployedTree:
    """One on-disk deployment, with the index row that minted it."""

    row: dict
    dir: Path
    tree: tree_mod.Tree


def deployment_root(root: Path | str | None = None) -> Path:
    """The `.ade/` root: explicit arg > `APRIL_ADE_ROOT` > the repo checkout."""
    if root is not None:
        return Path(root)
    env = os.environ.get(ADE_ROOT_ENV, "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / ".ade"


def deployed_dir(
    persona: str, domain: str, *, root: Path | str | None = None
) -> Path:
    persona = _persona(persona)
    return (
        deployment_root(root)
        / "harnesses"
        / persona
        / (domain_dir(domain) or "default")
    )


def index_path(root: Path | str | None = None) -> Path:
    return deployment_root(root) / "harnesses" / INDEX_NAME


def _persona(persona: str) -> str:
    name = str(persona or "").strip()
    if not _PERSONA_RX.fullmatch(name):
        raise ValueError(
            f"persona {name!r} must match [a-z0-9][a-z0-9_-]* "
            f"(a committed profile id, used verbatim as a path segment)"
        )
    return name


def _load_index(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: unreadable deployment index: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(f"{path}: the deployment index must be a JSON list")
    return data


def deployed_rows(
    persona: str | None = None, root: Path | str | None = None
) -> list[dict]:
    """Every index row, newest last — optionally only one persona's."""
    rows = _load_index(index_path(root))
    if persona is None:
        return rows
    key = _persona(persona)
    return [r for r in rows if r.get("persona") == key]


def _read_source_tree(
    harness: Path, surface: tree_mod.SurfaceSpec
) -> tree_mod.Tree:
    harness = Path(harness)
    if not tree_mod.is_tree(surface, harness):
        raise ValueError(
            f"{harness}: not a {surface.name} tree — none of "
            f"{', '.join(surface.always_on)} is present"
        )
    tree = tree_mod.read_tree(surface, harness)
    # The deployment gate is the same one a proposal faces: validate raises on
    # any problem and never shrinks a tree to make it fit.
    tree_mod.validate(surface, tree, allow_subagents=False)
    return tree


def _stamp(surface: tree_mod.SurfaceSpec, tree: tree_mod.Tree, persona: str) -> tree_mod.Tree:
    """Carry the persona into an otherwise persona-free adopted tree.

    c1: the compiled persona under `## persona: compiled`; c2: the protocol
    list under `## persona: protocols`. Sections already carrying `## persona:`
    are left as the selection authored them — deployment never rewrites a
    proposal's persona.
    """
    from ..harness.personality import (
        PROTOCOL_OVERRIDE_LINE,
        compile_persona,
        load_profile,
    )

    profile = load_profile(persona)
    out = dict(tree)

    # Resolve the c1 (system prompt) / c2 (guardrails) slots by ROLE rather than
    # fixed file name: APRIL has distinct per-role files (systemprompt.md /
    # guardrails.md); the zcode surface carries both halves in the single
    # AGENTS.md file, so a ZCODE deployment stamps both sections into it. The
    # decrement that previously left zcode surfaces stamping nowhere (empty c1)
    # is retired here (P7-5).
    c1 = surface.always_on[0]
    c2 = surface.always_on[1] if len(surface.always_on) > 1 else surface.always_on[0]
    if c1 not in surface.always_on:
        raise ValueError(f"surface {surface.name!r} has no always-on c1 (system prompt) file")
    if c1 in surface.always_on and not re.search(r"##\s*persona\s*:\s*compiled\b", out.get(c1, ""), re.I):
        block = compile_persona(profile)
        if len(block) > ADE_PERSONA_CAP:
            raise ValueError(
                f"{c1}: compiled persona is {len(block)} chars, over the "
                f"{ADE_PERSONA_CAP}-char deployment cap; shrink the profile"
            )
        out[c1] = (out.get(c1, "").rstrip() + f"\n\n## persona: compiled\n\n{block}\n")

    if (
        c2 in surface.always_on
        and profile.persona.protocols
        and not re.search(r"##\s*persona\s*:\s*protocols\b", out.get(c2, ""), re.I)
    ):
        lines = ["## Protocols (non-negotiable)"]
        lines += [f"{i + 1}. {rule}" for i, rule in enumerate(profile.persona.protocols)]
        lines += ["", PROTOCOL_OVERRIDE_LINE]
        out[c2] = out.get(c2, "").rstrip() + "\n\n## persona: protocols\n" + "\n".join(lines) + "\n"

    # The deployment cap census runs again on the stamped tree — an overflow
    # fails the deploy loudly instead of shipping an over-budget harness.
    tree_mod.validate(surface, out, allow_subagents=False, persona_cap=ADE_PERSONA_CAP)
    return out


def deploy(
    harness: Path | str,
    *,
    surface: tree_mod.SurfaceSpec,
    persona: str,
    domain: str = "default",
    task_id: str = "",
    run_dir: str = "",
    score: float | None = None,
    stamp: bool = True,
    root: Path | str | None = None,
) -> dict:
    """Validate + fingerprint + index one adopted tree, and return its index row.

    Overwrites the persona/domain slot in place (one deployment per slot); the
    index keeps the history. `score` is the post-selection score when one exists.
    """
    name = _persona(persona)
    dest = deployed_dir(name, domain, root=root)
    tree = _read_source_tree(harness, surface)
    if stamp:
        tree = _stamp(surface, tree, name)

    # One tree per (persona, domain) slot: overwrite in place. The dest is ADE
    # state, never repo content, so clearing it is paper, not evidence.
    if dest.exists():
        shutil.rmtree(dest)
    tree_mod.write_tree(surface, tree, dest, stubs=False)

    from ..harness import runmark

    row = {
        "persona": name,
        "domain": domain_dir(domain) or "default",
        "date": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
        "run_dir": run_dir,
        "score": score,
        "fingerprint": runmark.fingerprint(dest),
    }
    path = index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = _load_index(path) + [row]
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return row


def load_deployed(
    persona: str,
    domain: str = "default",
    *,
    surface: tree_mod.SurfaceSpec | None = None,
    root: Path | str | None = None,
) -> DeployedTree | None:
    """The deployed tree for `(persona, domain)`, fingerprint-verified.

    `None` when nothing was ever deployed there — the boot falls back to the
    committed profile upstream; an index/tree mismatch raises loudly instead.
    """
    if surface is None:
        from ..substrate.april import APRIL_SURFACE

        surface = APRIL_SURFACE
    dest = deployed_dir(persona, domain, root=root)
    if not tree_mod.is_tree(surface, dest):
        return None
    key = domain_dir(domain) or "default"
    rows = [r for r in deployed_rows(persona, root) if r.get("domain") == key]
    if not rows:
        return None
    row = rows[-1]
    from ..harness import runmark

    if runmark.fingerprint(dest) != row.get("fingerprint"):
        raise ValueError(
            f"{dest}: deployed tree changed after deployment (fingerprint "
            f"{row.get('fingerprint')!r} no longer matches); redeploy it"
        )
    return DeployedTree(row=row, dir=dest, tree=tree_mod.read_tree(surface, dest))


__all__ = [
    "ADE_ROOT_ENV",
    "INDEX_NAME",
    "DeployedTree",
    "deployment_root",
    "deployed_dir",
    "deployed_rows",
    "index_path",
    "deploy",
    "load_deployed",
]
