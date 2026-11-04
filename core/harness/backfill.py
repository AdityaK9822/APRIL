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

"""Legacy-lesson backfill (P7-3)."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .library import SIMILARITY_FLOOR
from .personality import cosine, load_profile, parse_ocean_row


def _coerce_vector(value: Any) -> tuple[float, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        row = parse_ocean_row(value)
        if row is None:
            parts = [p for p in value.replace(",", " ").split() if p]
            try:
                nums = tuple(float(p) for p in parts)
            except (ValueError, TypeError):
                return None
            if len(nums) != 5:
                return None
            value = nums
        else:
            value = row
    try:
        nums = tuple(float(x) for x in value)
    except (TypeError, ValueError):
        return None
    if len(nums) != 5:
        return None
    if any(not (x == x and x not in (float("inf"), float("-inf"))) for x in nums):
        return None
    if any(abs(x) > 1.0 for x in nums):
        return tuple(x / 100.0 for x in nums)
    return tuple(x for x in nums)


def _profile_vectors(profiles: Any) -> dict[str, tuple[float, ...]]:
    out: dict[str, tuple[float, ...]] = {}
    if isinstance(profiles, dict):
        for key, val in profiles.items():
            pid = str(key).strip()
            if not pid:
                continue
            if isinstance(val, str):
                vec = _coerce_vector(val)
            elif hasattr(val, "persona") and hasattr(val, "id"):
                try:
                    vec = val.persona.ocean.vector()
                except Exception:
                    vec = None
            elif isinstance(val, (tuple, list)):
                vec = _coerce_vector(val)
            elif isinstance(val, dict):
                if "ocean" in val:
                    vec = _coerce_vector(val["ocean"])
                elif "facets" in val:
                    from . import personality as _p
                    try:
                        vec = _p.aggregate_facets(val["facets"]).vector()
                    except Exception:
                        vec = None
                else:
                    vec = _coerce_vector(list(val.values()))
            else:
                try:
                    vec = _coerce_vector(getattr(val, "vector", lambda: None)())
                except Exception:
                    vec = None
            if vec is not None:
                out[pid] = vec
        return out
    ids: list[str] = []
    if isinstance(profiles, str):
        ids = [profiles]
    else:
        for item in profiles:
            if isinstance(item, str):
                ids.append(item.strip())
            else:
                try:
                    ids.append(str(getattr(item, "id", item)).strip())
                except Exception:
                    continue
    for pid in ids:
        if not pid:
            continue
        try:
            out[pid] = load_profile(pid).persona.ocean.vector()
        except Exception:
            continue
    if not out and profiles is None:
        pass
    return out


def nearest_profile(lesson_ocean: Any, profiles: Any) -> str | None:
    vec = _coerce_vector(lesson_ocean)
    if vec is None:
        return None
    candidates = _profile_vectors(profiles)
    best: tuple[float, str] | None = None
    for pid, pvec in candidates.items():
        score = cosine(vec, pvec)
        if score < SIMILARITY_FLOOR:
            continue
        if best is None or score > best[0] or (score == best[0] and pid < best[1]):
            best = (score, pid) if (best is None or score > best[0] or (score == best[0] and pid < best[1])) else best
    # simpler tie-resolve:
    best2 = None
    for pid, pvec in candidates.items():
        score = cosine(vec, pvec)
        if score < SIMILARITY_FLOOR:
            continue
        if best2 is None or score > best2[0] or (score == best2[0] and pid < best2[1]):
            best2 = (score, pid)
    return best2[1] if best2 else None


@dataclass
class BackfillAction:
    task_id: str
    decision: str
    profile: str | None = None
    transferable: bool | None = None
    reason: str = ""


@dataclass
class BackfillPlan:
    assignments: list[dict] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    actions: list[BackfillAction] = field(default_factory=list)


def plan_backfill(rows: Sequence[dict], profiles: Any = None) -> BackfillPlan:
    plan = BackfillPlan()
    if isinstance(profiles, dict):
        profile_ids_input = list(profiles.keys())
    elif profiles is None:
        from . import personality as _p
        profile_ids_input = list(_p.load_profiles().keys())
    else:
        try:
            profile_ids_input = [str(getattr(x, "id", x)).strip() for x in profiles]
        except Exception:
            profile_ids_input = []
        if not profile_ids_input:
            try:
                profile_ids_input = list(profiles)
            except Exception:
                profile_ids_input = []
    vectors = _profile_vectors(profile_ids_input) if not isinstance(profiles, dict) else _profile_vectors(profiles)
    if not vectors and isinstance(profiles, dict):
        vectors = _profile_vectors(profiles)
    for row in rows or []:
        rid = str(row.get("task_id") or row.get("id") or "")
        current = str(row.get("profile") or row.get("profile_id") or "").strip()
        ocean = row.get("ocean")
        if ocean is None:
            ocean = row.get("profile_ocean") or row.get("ocean_row") or row.get("row")
        if current:
            plan.skipped.append((rid, "already-profiled"))
            plan.actions.append(BackfillAction(rid, "already-profiled", profile=current, reason="row already carries a profile id"))
            continue
        vec = _coerce_vector(ocean)
        if vec is None:
            plan.skipped.append((rid, "no-vector"))
            plan.actions.append(BackfillAction(rid, "no-vector", reason="no ocean vector stored (legacy text-only row)"))
            continue
        prof = nearest_profile(vec, vectors)
        if prof is None:
            plan.skipped.append((rid, "keep-free"))
            plan.actions.append(BackfillAction(rid, "keep-free", reason=f"nearest profile below similarity floor ({SIMILARITY_FLOOR})"))
            continue
        transferable = row.get("transferable", True)
        assignment = {
            "task_id": rid,
            "profile": prof,
            "ocean": " ".join(f"{t}{v}" for t, v in zip("OCEAN", (int(round(x * 100)) for x in vec))),
            "ocean_vec": vec,
            "transferable": bool(transferable) if transferable is not None else True,
        }
        plan.assignments.append(assignment)
        plan.actions.append(BackfillAction(rid, "assign", profile=prof, transferable=assignment["transferable"], reason=f"nearest profile within similarity floor: {prof}"))
    return plan


def apply_backfill(rows, *, library_root=None, profiles=None, dry_run=True, backup=True) -> dict:
    plan = plan_backfill(rows, profiles)
    report = {
        "dry_run": dry_run,
        "n_rows": len(list(rows)),
        "n_assign": len(plan.assignments),
        "n_skipped": len(plan.skipped),
        "assignments": list(plan.assignments),
        "skipped": list(plan.skipped),
    }
    if dry_run:
        return report
    if not plan.assignments:
        raise RuntimeError("backfill: nothing to apply (no profileable rows). Precondition for an apply run is at least one unprofiled row with a usable ocean vector.")
    root = Path(library_root) if library_root is not None else None
    if root is not None:
        root = Path(root)
        if backup and root.exists():
            backup_dir = root.parent / f"{root.name}.backfill-backup"
            if not backup_dir.exists():
                shutil.copytree(root, backup_dir)
        out = root / ".backfill-plan.json"
        out.write_text(__import__("json").dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def demo() -> None:
    near_ocean = (69, 89, 44, 87, 21)
    far_ocean = (10, 10, 90, 90, 90)
    profiles = ["april"]
    assert nearest_profile(near_ocean, profiles) == "april", nearest_profile(near_ocean, profiles)
    assert nearest_profile(far_ocean, profiles) is None, nearest_profile(far_ocean, profiles)
    assert nearest_profile(None, profiles) is None

    rows = [
        {"task_id": "r0", "profile": "user", "ocean": (85, 64, 55, 88, 44)},
        {"task_id": "r1", "ocean": near_ocean},
        {"task_id": "r2", "ocean": far_ocean},
    ]
    rows.append({"task_id": "r3", "lesson": "text only"})
    plan = plan_backfill(rows, profiles)
    assert len(plan.assignments) == 1, (plan.assignments, plan.skipped)
    assert plan.assignments[0]["task_id"] == "r1"
    assert plan.assignments[0]["profile"] == "april"
    assert [s[0] for s in plan.skipped] == ["r0", "r2", "r3"]
    skip_reasons = {s[0]: s[1] for s in plan.skipped}
    assert skip_reasons["r0"] == "already-profiled"
    assert skip_reasons["r2"] == "keep-free"
    assert skip_reasons["r3"] == "no-vector"
    assert plan.assignments[0]["ocean"] == "O69 C89 E44 A87 N21"

    tmp = Path(tempfile.mkdtemp(prefix="backfill-"))
    (tmp / "probe").mkdir()
    before = sorted(str(p) for p in tmp.rglob("*"))
    report = apply_backfill(rows, library_root=tmp, profiles=profiles, dry_run=True)
    assert report["dry_run"] is True
    assert report["n_assign"] == 1
    after = sorted(str(p) for p in tmp.rglob("*"))
    assert before == after, "dry_run must not write"
    report2 = apply_backfill(rows, library_root=tmp, profiles=profiles, dry_run=False)
    assert (tmp / ".backfill-plan.json").is_file()
    assert report2["n_assign"] == 1

    applied_rows = [dict(r) for r in rows]
    for a in report["assignments"]:
        applied_rows[[r["task_id"] for r in applied_rows].index(a["task_id"])]["profile"] = a["profile"]
    plan2 = plan_backfill(applied_rows, profiles)
    assert plan2.assignments == [], plan2.assignments


# CLI / entrypoint
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Legacy-lesson backfill (inert by default).")
    ap.add_argument("--rows", type=Path, help="JSON file with the legacy row list")
    ap.add_argument("--profiles", nargs="*", default=None, help="profile ids to consider")
    ap.add_argument("--library-root", type=Path, default=None)
    ap.add_argument("--apply", action="store_true", help="write the side-car")
    args = ap.parse_args()
    rows: list[dict] = []
    if args.rows and args.rows.is_file():
        rows = json.loads(args.rows.read_text(encoding="utf-8"))
    profiles = args.profiles if args.profiles else None
    plan = plan_backfill(rows, profiles)
    if not plan.assignments:
        print("backfill: no profileable rows — refusing to apply (precondition).")
        raise SystemExit(0)
    report = apply_backfill(rows, library_root=args.library_root, profiles=profiles, dry_run=not args.apply)
    print(json.dumps(report, indent=2, default=str))
