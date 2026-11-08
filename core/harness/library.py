# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The per-domain experience library."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from . import context
from . import tree as harness_tree
from .tree import SurfaceSpec

# P3: the transfer gate. A lesson distilled under a different persona loads into a
# profile-backed run only when its OCEAN shape is close enough to the active one,
# or when the lesson itself marks it transferable (INV/DOM edits are, PSY-only
# edits are not). 0.95 keeps same-persona lessons and gates a genuinely different
# persona shape; measured: april<->user 0.9667 passes, april<->verifier 0.9111
# is gated unless transferable.
SIMILARITY_FLOOR = 0.95


def slug(task_id: str) -> str:
    return task_id.replace("/", "__")


def has_experience(experience: dict | None) -> bool:
    return isinstance(experience, dict) and all(
        isinstance(experience.get(key), str) and experience[key].strip()
        for key in ("cue", "lesson", "evidence")
    )


def domain_dir(domain: str) -> str:
    return re.sub(r"\s*[/\\]\s*", "__", domain).strip() or "unknown"


@dataclass
class Library:
    root: Path
    domain: str
    surface: SurfaceSpec
    # P3: the persona this library serves. Empty means persona-free retrieval
    # (recency order); a non-empty profile ranks by OCEAN cosine and applies
    # the transfer gate.
    profile: str = ""

    @property
    def dir(self) -> Path:
        return Path(self.root) / domain_dir(self.domain)

    @property
    def index(self) -> Path:
        return self.dir / "INDEX.md"

    def entry_dir(self, task_id: str) -> Path:
        return self.dir / "harnesses" / slug(task_id)

    def exists(self) -> bool:
        return self.index.is_file()

    def context_dir(self) -> Path | None:
        return self.dir if self.exists() and any(self.dir.rglob("EXPERIENCE.md")) else None

    def entries(self) -> list[str]:
        d = self.dir / "harnesses"
        return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []

    def load_context(self, max_entries: int = 5, *, profile: str | None = None) -> str:
        """Load past experience in this domain as in-context memory text.

        Persona-free retrieval keeps the recency order this library has always
        used. With a profile active, entries are ranked by OCEAN cosine against
        the profile and a below-floor entry whose lesson is not `transferable`
        is withheld: a PSY-specific lesson learned under a different persona is
        not evidence for this one. Entries with no stored vector (persona-free
        lessons) stay eligible when transferable and sort last.
        """
        if not self.exists():
            return ""
        names = self.entries()
        if not names:
            return ""

        entry_paths = [self.dir / "harnesses" / name for name in names]
        active = str(profile if profile is not None else self.profile).strip()

        if not active:
            # Most recently added entries first (by directory mtime), then lexically.
            try:
                entry_paths.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
            except OSError:
                entry_paths.sort(key=lambda p: p.name, reverse=True)
            selected = entry_paths[: max(0, int(max_entries))]
        else:
            selected = self._ranked(entry_paths, active, max_entries)

        parts: list[str] = []
        if active:
            # A gated lesson must not leak back in through the browse index: the
            # index for a profile-backed run lists only the entries that passed
            # the cosine gate.
            parts.append(self._index_text([p.name for p in selected]).strip())
        elif self.index.is_file():
            parts.append(self.index.read_text(encoding="utf-8", errors="replace").strip())

        for entry in selected:
            exp_path = entry / "EXPERIENCE.md"
            if not exp_path.is_file():
                continue
            body = exp_path.read_text(encoding="utf-8", errors="replace").strip()
            if body:
                parts.append(f"---\n# {entry.name}\n\n{body}")

        return "\n\n".join(parts).strip()

    def _ranked(self, entry_paths: list[Path], profile: str, max_entries: int) -> list[Path]:
        """Cosine-rank entries for `profile`, dropping gated non-transferable ones."""
        from .personality import cosine, load_profile, parse_ocean_row

        vector = load_profile(profile).persona.ocean.vector()
        scored: list[tuple[float, float, str, Path]] = []
        for entry in entry_paths:
            exp_path = entry / "EXPERIENCE.md"
            meta = _field(exp_path, "profile")
            row = parse_ocean_row(meta)
            transferable = _field(exp_path, "transferable").strip().lower() != "false"
            if row is not None:
                score = cosine(vector, tuple(v / 100 for v in row))
            else:
                score = 0.0
            if score < SIMILARITY_FLOOR and not transferable:
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                mtime = 0.0
            scored.append((score, mtime, entry.name, entry))
        scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return [entry for _score, _mtime, _name, entry in scored[: max(0, int(max_entries))]]

    def tree_of(self, task_id: str) -> harness_tree.Tree:
        return harness_tree.read_tree(self.surface, self.entry_dir(task_id) / "harness")

    def forget(self, task_ids: Sequence[str]) -> None:
        removed = False
        for tid in task_ids:
            d = self.entry_dir(tid)
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
                removed = True
        if removed:
            self.rebuild_index()

    def retain(self, task_ids: Sequence[str]) -> None:
        keep = {slug(task_id) for task_id in task_ids}
        self.forget([entry for entry in self.entries() if entry not in keep])

    def add(
        self,
        task_id: str,
        harness: harness_tree.Tree,
        *,
        why: str = "",
        label: str = "",
        run_id: str = "",
        experience: dict | None = None,
    ) -> Path | None:
        if not has_experience(experience):
            return None
        context.assert_tree_has_no_grader_verdicts(harness)
        context.assert_tree_has_no_grader_verdicts({"EXPERIENCE.md": str(experience) + why})
        d = self.entry_dir(task_id)

        shutil.rmtree(d / "harness", ignore_errors=True)
        (d / "harness").mkdir(parents=True, exist_ok=True)
        harness_tree.write_tree(self.surface, harness, d / "harness", stubs=False)

        exp = experience or {}
        lines = [
            f"# {task_id}",
            "",
            f"- adopted: `{label}`" + (f"  (run `{run_id}`)" if run_id else ""),
            f"- components: {_inventory(self.surface, harness)}",
            "",
        ]
        # P2: run provenance — the persona this lesson was distilled under and
        # its compact ocean vector ("O70 C90 E45 A88 N20"). The transfer gate
        # (P3) ranks lessons by cosine similarity over this vector.
        if str(exp.get("profile_id", "")).strip():
            oc = str(exp.get("ocean", "")).strip()
            lines.append(
                f"- **profile**: `{str(exp['profile_id']).strip()}`" + (f" — {oc}" if oc else "")
            )
        # P3: the transfer mark is written even for persona-free lessons: absent
        # means transferable, and an explicit `false` is what the cosine gate
        # reads when a lesson is PSY-specific.
        transferable = exp.get("transferable", True)
        lines.append(f"- **transferable**: {'true' if transferable else 'false'}")
        if why.strip():
            lines += ["## Why this was chosen", why.strip(), ""]
        if exp.get("edits"):
            lines += ["## What each edit did", str(exp["edits"]).strip(), ""]
        if exp.get("lesson"):
            lines += ["## Transferable lesson"]
            lines += [
                f"- **{f}**: {str(exp[f]).strip()}"
                for f in ("cue", "lesson", "evidence", "confidence")
                if exp.get(f)
            ]
            lines += [""]
        (d / "EXPERIENCE.md").write_text("\n".join(lines), encoding="utf-8")
        self.rebuild_index()
        return d

    def rebuild_index(self) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index.write_text(self._index_text(self.entries()), encoding="utf-8")
        return self.index

    def _index_text(self, names: Sequence[str]) -> str:
        rows = [
            f"# Library — {self.domain}",
            "",
            "Each entry is an earlier task in THIS domain whose harness was chosen, stored "
            "with its FULL component tree and why it was picked. Browse this index, then "
            "open the entries that look relevant to the matter in front of you.",
            "",
        ]
        if not names:
            rows.append("_(empty — this is the first task in this domain)_")
        for name in names:
            ed = self.dir / "harnesses" / name
            cue = _field(ed / "EXPERIENCE.md", "cue")
            tree = harness_tree.read_tree(self.surface, ed / "harness")
            rows += [
                f"## `harnesses/{name}/`",
                f"- harness: `harnesses/{name}/harness/` — {_inventory(self.surface, tree)}",
                f"- why:     `harnesses/{name}/EXPERIENCE.md`",
            ]
            persona = _field(ed / "EXPERIENCE.md", "profile")
            if persona:
                rows.append(f"- persona: {persona}")
            transferable = _field(ed / "EXPERIENCE.md", "transferable")
            if transferable:
                rows.append(f"- transferable: {transferable}")
            if cue:
                rows.append(f"- cue:     {cue}")
            rows.append("")
        return "\n".join(rows)


def _inventory(surface: SurfaceSpec, tree: harness_tree.Tree) -> str:
    st: dict[str, int] = {"skills": 0, "sub_agents": 0, "scripts": 0}
    skill_prefix = surface.skill_dir + "/"
    plugin_prefix = None if surface.plugin_dir is None else surface.plugin_dir + "/"
    hooks_file = surface.hooks_file
    for rel in tree:
        if rel.startswith(skill_prefix) and rel.endswith("SKILL.md"):
            st["skills"] += 1
        elif rel.startswith("sub_agents/"):
            st["sub_agents"] += 1
        elif rel.startswith("scripts/"):
            st["scripts"] += 1
        elif plugin_prefix is not None and rel.startswith(plugin_prefix):
            st["plugins"] = st.get("plugins", 0) + 1
        elif rel == hooks_file:
            st["hooks"] = st.get("hooks", 0) + 1
    on = len(harness_tree.always_on_text(surface, tree))
    bits = [f"{v} {k}" for k, v in st.items() if v] or ["always-on edits only"]
    return f"{', '.join(bits)}; {on:,} always-on chars"


def _field(path: Path, name: str) -> str:
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(f"- **{name}**:"):
            return line.split(":", 1)[1].strip()
    return ""


def root_for(base: Path | str, *, benchmark: str, k: int, variant: str = "", tag: str = "") -> Path:
    if tag:
        return Path(base) / benchmark / tag
    parts = [f"k{int(k)}"] + ([variant] if variant else [])
    return Path(base) / benchmark / "-".join(parts)




_EXPERIENCE_HEADER = """# EXPERIENCE.md — Global Lesson Library

This file is the root-level lesson library for the APRIL Harness² engine. After a
harness is adopted, the engine appends a lesson entry here so future runs can
reuse the hard-won tweak.

Entries are append-only Markdown. Do not edit or remove prior rows; corrections
are recorded as new entries with an updated status.
"""


def _experience_value(experience: Any, *names: str) -> str:
    if not isinstance(experience, dict):
        return ""
    for name in names:
        value = experience.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _coerce_root_experience_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[Path, dict[str, str]]:
    path: Path | None = None
    experience: dict[str, Any] | None = kwargs.get("experience")
    data: dict[str, Any] = dict(kwargs)

    # Resolve an explicit path from positional/keyword arguments.
    if args and isinstance(args[0], (str, Path)):
        path = Path(args[0])
        args = args[1:]
    for key in ("path", "file", "filename", "experience_file", "root_experience", "target"):
        if path is None and key in data and isinstance(data[key], (str, Path)):
            path = Path(data.pop(key))
    if path is None:
        path = Path(data.pop("root", Path("EXPERIENCE.md"))) if "root" in data and isinstance(data["root"], (str, Path)) else Path("EXPERIENCE.md")

    # A positional dict is treated as the experience payload.
    if experience is None and args and isinstance(args[0], dict):
        experience = args[0]
        args = args[1:]
    if experience is None and isinstance(data.get("entry"), dict):
        experience = data.pop("entry")
    if experience is None and isinstance(data.get("record"), dict):
        experience = data.pop("record")

    if experience is None:
        experience = {}

    # Map remaining positional values onto common fields.
    positional_fields = ["domain", "lesson", "cue", "evidence", "confidence", "status", "adopted", "task_id", "task"]
    for index, value in enumerate(args):
        if index < len(positional_fields):
            data.setdefault(positional_fields[index], value)

    normalized: dict[str, str] = {}
    for key in ("domain", "task_id", "task", "adopted", "label", "run_id", "why"):
        if key in data and data[key] is not None:
            normalized[key] = str(data[key]).strip()

    # Cue/lesson/evidence/confidence/status may live in the experience payload.
    normalized["cue"] = str(data.get("cue", _experience_value(experience, "cue"))).strip()
    normalized["lesson"] = str(data.get("lesson", _experience_value(experience, "lesson", "why"))).strip()
    normalized["evidence"] = str(data.get("evidence", _experience_value(experience, "evidence"))).strip()
    normalized["confidence"] = str(data.get("confidence", _experience_value(experience, "confidence") or "medium")).strip()
    normalized["status"] = str(data.get("status", _experience_value(experience, "status") or "adopted")).strip()
    # P2: persona provenance may ride the payload or explicit kwargs; both are
    # run facts written verbatim (never model claims).
    normalized["profile_id"] = str(
        data.get("profile_id", _experience_value(experience, "profile_id"))
    ).strip()
    normalized["ocean"] = str(
        data.get("ocean", _experience_value(experience, "ocean"))
    ).strip()
    # P3: false only when the lesson was learned entirely in the PSY lane; the
    # library's cosine gate reads this on reload.
    normalized["transferable"] = str(
        data.get("transferable", _experience_value(experience, "transferable") or "true")
    ).strip().lower()
    if "domain" not in normalized or not normalized["domain"]:
        normalized["domain"] = str(data.get("domain", _experience_value(experience, "domain") or "unknown")).strip()
    if not normalized.get("task_id"):
        normalized["task_id"] = str(data.get("task_id", data.get("task", ""))).strip()
    if not normalized.get("adopted"):
        normalized["adopted"] = str(data.get("adopted", data.get("label", ""))).strip()
    if not normalized.get("lesson") and experience:
        normalized["lesson"] = str(experience.get("lesson", "")).strip() if isinstance(experience, dict) else normalized["lesson"]

    return path, normalized


def _append_root_experience(*args: Any, **kwargs: Any) -> Path:
    """Append one adopted-harness entry to the root-level ``EXPERIENCE.md``."""
    path, data = _coerce_root_experience_args(args, kwargs)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if not existing.strip() or "EXPERIENCE.md — Global Lesson Library" not in existing:
        if existing.strip():
            existing = _EXPERIENCE_HEADER + "\n\n" + existing.lstrip()
        else:
            existing = _EXPERIENCE_HEADER + "\n"
        path.write_text(existing, encoding="utf-8")

    domain = data.get("domain", "unknown") or "unknown"
    task_id = data.get("task_id", "")
    adopted = data.get("adopted", "")
    cue = data.get("cue", "")
    lesson = data.get("lesson", "")
    evidence = data.get("evidence", "")
    confidence = data.get("confidence", "medium") or "medium"
    status = data.get("status", "adopted") or "adopted"

    lines = [
        "",
        "## Adopted harness entry",
        "",
        f"- **Domain**: {domain}",
    ]
    if task_id:
        lines.append(f"- **Task ID**: {task_id}")
    if adopted:
        lines.append(f"- **Adopted**: {adopted}")
    profile_id = data.get("profile_id", "")
    if profile_id:
        persona = f"`{profile_id}`" + (f" ({data.get('ocean', '')})" if data.get("ocean") else "")
        lines.append(f"- **Persona**: {persona}")
    lines.extend(
        [
            f"- **Lesson**: {lesson}",
            f"- **Cue**: {cue}",
            f"- **Evidence**: {evidence}",
            f"- **Confidence**: {confidence}",
            f"- **Transferable**: {data.get('transferable', 'true') or 'true'}",
            f"- **Status**: {status}",
            "",
        ]
    )
    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


append_root_experience = _append_root_experience

__all__ = ["Library", "has_experience", "slug", "domain_dir", "root_for", "_append_root_experience", "append_root_experience"]
