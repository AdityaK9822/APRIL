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

"""TUI data views: the JSON contracts the widgets render.

Pure functions, no event-loop code: a widget only displays what these build.
The stable seam is the shape, not the renderer (spec:
`docs/spec/persona-dimension.md` 5). Nothing here reads personal facts — the
persona view reports COUNTS of local facts, never their text.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..harness.library import domain_dir
from .boot import ActionGuard, boot
from .deploy import deployed_rows, deployment_root, load_deployed

_FIELD_RX = re.compile(r"^-\s*\*\*(?P<name>[a-z_]+)\*\*:\s*(?P<value>.*)$", re.I)


def _field(path: Path, name: str) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    for line in text.splitlines():
        m = _FIELD_RX.match(line)
        if m and m.group("name").lower() == name:
            return m.group("value").strip()
    return ""


def selection_view(task_dir: Path | str) -> dict | None:
    """`selection.json` as the blind selector recorded it (persona-free by design)."""
    p = Path(task_dir) / "selection.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def adoption_views(task_dir: Path | str) -> dict[str, dict]:
    """Every `reflection/<mode><k>/adoption.json`, keyed by the reflection dir."""
    root = Path(task_dir) / "reflection"
    out: dict[str, dict] = {}
    if not root.is_dir():
        return out
    for d in sorted(p.name for p in root.iterdir() if p.is_dir()):
        p = root / d / "adoption.json"
        if p.is_file():
            try:
                out[d] = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
    return out


def library_view(root: Path | str | None = None) -> list[dict]:
    """Per persona: per domain, the INDEX rows the `/library` pane lists."""
    root = Path(root) if root is not None else deployment_root(None) / "library"
    rows: list[dict] = []
    if not root.is_dir():
        return rows
    for persona_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        persona = persona_dir.name
        for domain_dir_ in sorted(p for p in root.glob("*") if p.is_dir()):
            # The library root is library_root/<profile>/<domain libre>/
            d = root / persona_dir.name / domain_dir_.name
            hdir = d / "harnesses"
            if not d.is_dir() or not hdir.is_dir():
                continue
            entries = []
            for ed in sorted(hdir.iterdir()):
                if not ed.is_dir():
                    continue
                entries.append(
                    {
                        "entry": ed.name,
                        "profile": _field(ed / "EXPERIENCE.md", "profile"),
                        "ocean": _field(ed / "EXPERIENCE.md", "ocean"),
                        "transferable": _field(ed / "EXPERIENCE.md", "transferable"),
                        "confidence": _field(ed / "EXPERIENCE.md", "confidence"),
                        "cue": _field(ed / "EXPERIENCE.md", "cue"),
                    }
                )
            rows.append({"persona": persona, "domain": domain_dir_.name, "entries": entries})
    return rows


def persona_view(
    persona: str,
    *,
    domain: str = "default",
    library_root: Path | str | None = None,
    root: Path | str | None = None,
) -> dict:
    """The boot summary plus a persona's deployments and library rows.

    Personal facts appear only as a count (`user_context_facts`).
    """
    name = str(persona).strip()
    b = boot(name, domain=domain, root=root, local_context=True)
    deployment = load_deployed(name, domain, root=root)
    guard = ActionGuard(b.persona, b.guardrails)
    lib = library_view(library_root) if library_root is not None else []
    return {
        "persona": b.persona,
        "domain": domain_dir(b.domain) or "default",
        "source": b.source,
        "temperature": b.temperature,
        "system_prompt_chars": len(b.system_prompt),
        "guardrail_chars": len(b.guardrails),
        "attested_rules": guard.attested_rules(),
        "machine_rules": list(b.machine_rules),
        "user_context_facts": len(b.user_context),
        "fingerprint": None if deployment is None else deployment.row.get("fingerprint"),
        "deployed_dir": None if deployment is None else str(deployment.dir),
        "deployments": deployed_rows(name, root),
        "library": [r for r in lib if r["persona"] == name],
    }


def run_selections(runs_root: Path | str, persona: str) -> list[dict]:
    """Every `selection.json` under the persona's `-P<persona>` namespaces.

    A scheduled sweep keeps selections beside the task dir; this is the view
    the TUI uses to show what the blind selector chose per persona.
    """
    out: list[dict] = []
    root = Path(runs_root)
    if not root.is_dir():
        return out
    marker = f"-P{persona}"
    for p in sorted(root.glob(f"*{marker}*/**/selection.json")):
        if not p.is_file():
            continue
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append({"path": str(p), "selection": rec})
    return out


__all__ = [
    "selection_view",
    "adoption_views",
    "library_view",
    "persona_view",
    "run_selections",
]
