"""Adapter for the skills (c6) component."""

from __future__ import annotations

import re

from .base import ComponentAdapterBase


class SkillsAdapter(ComponentAdapterBase):
    name = "skills"
    surface_paths = (".agents/skills/", "skills/")

    def __init__(
        self,
        must_match: bool = False,
        skill_name_rule: str | None = None,
        **kwargs,
    ) -> None:
        self.must_match = bool(kwargs.get("must_match", must_match))
        if skill_name_rule is not None:
            self.skill_name_rule = skill_name_rule
        else:
            self.skill_name_rule = "must_match" if self.must_match else "warn_on_mismatch"

    def _skill_name(self, rel: str) -> str | None:
        for prefix in (".agents/skills/", "skills/"):
            if rel.startswith(prefix):
                rest = rel[len(prefix):]
                if rest.endswith("/SKILL.md"):
                    return rest[: -len("/SKILL.md")]
        return None

    def validate(self, tree) -> list[str]:
        problems: list[str] = []
        skill_rels = [r for r in tree if self._skill_name(r) is not None]
        other_text = "\n".join(
            content for rel, content in tree.items() if rel not in skill_rels
        )

        for rel in skill_rels:
            content = tree[rel]
            name = self._skill_name(rel)
            assert name is not None
            if not re.search(r"^description:\s*\S", content, re.M):
                problems.append(
                    f"{rel} needs a `description:` in its frontmatter, "
                    f"or the skill is dropped SILENTLY at load"
                )
            name_match = re.search(r"^name:\s*(\S+)\s*$", content, re.M)
            if self.skill_name_rule == "must_match":
                if not (name_match and name_match.group(1) == name):
                    problems.append(
                        f"{rel} needs frontmatter `name: {name}` matching "
                        f"its directory (a mismatch is dropped SILENTLY at load)"
                    )
            elif name_match and name_match.group(1) != name:
                problems.append(
                    f"{rel} frontmatter `name: {name_match.group(1)}` OVERRIDES "
                    f"the directory name at load, so trigger lines naming "
                    f"`{name}` stop matching; drop the `name:` line or make it "
                    f"`name: {name}`"
                )
            if name not in other_text:
                problems.append(
                    f"skill '{name}' is never named in the always-on text, so "
                    f"the agent will not know to invoke it — an untriggered "
                    f"skill is dead weight"
                )
        return problems

    def describe(self, edit=None) -> str:
        files = edit.files if edit is not None else {}
        return f"skills: {len(files)} file(s) managing skill library"
