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

"""Runtime persona boot: `APRIL_PERSONA=<id>` attaches a persona to the agent.

Resolution order (spec: `docs/spec/persona-dimension.md` 4):

1. the DEPLOYED tree `.ade/harnesses/<persona>/<domain>/` (fingerprint-verified);
2. otherwise the committed `profiles/<id>.json`, compiled — an unknown persona
   raises loudly instead of silently running unpersonified.

c1 (`systemprompt.md` / `compile_persona`) becomes the system message; c2
(`guardrails.md` / the profile's protocols) becomes the permission layer — the
`ActionGuard` that wraps shell execution and reuses the post-selection
checklist's machine gates verbatim; and `derive().temperature` overrides the
configured sampling temperature, so system prompt + temperature land together
from one source (the TS `toRequest()` semantics).

Local facts join at BOOT time only: the `## APRIL userContext` block of the
git-ignored `.ade/etc/persona-user-context.md` renders as "## About the user".
It is read, never written, never committed, and never logged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..harness import judge
from ..harness.personality import (
    PROTOCOL_OVERRIDE_LINE,
    compile_persona,
    derive,
    load_profile,
    persona_of,
)
from ..harness.tree import SurfaceSpec
from .deploy import DeployedTree, deployment_root, load_deployed

# The two machine gates, by the same ids the post-selection checklist uses.
MACHINE_RULES: tuple[str, ...] = (
    "no-unapproved-public-action",
    "no-secrets-stored-echoed-logged",
)

_LOCAL_CONTEXT_HEADING = re.compile(r"^##\s+APRIL userContext\b.*$", re.I | re.M)

_ABOUT_USER = "## About the user"


@dataclass(frozen=True)
class PersonaBoot:
    """Everything a persona changes about a runtime, resolved in one place."""

    persona: str
    domain: str
    source: str  # "deployed:<domain>" or "profile:<id>"
    system_prompt: str
    guardrails: str
    temperature: float
    machine_rules: tuple[str, ...] = MACHINE_RULES
    deployment: DeployedTree | None = None
    user_context: tuple[str, ...] = ()


def _compiled_guardrails(persona) -> str:
    """The c2 text when no tree exists: the profile's protocols, verbatim.

    The persona block already carries these as prose; the guard needs them as
    the runtime's own rules, so they compile once here.
    """
    protocols = persona_of(persona).protocols
    if not protocols:
        return ""
    lines = ["## Protocols (non-negotiable)"]
    lines += [f"{i + 1}. {rule}" for i, rule in enumerate(protocols)]
    lines += ["", PROTOCOL_OVERRIDE_LINE]
    return "\n".join(lines)


def load_local_overrides(root: Path | str | None = None) -> tuple[str, ...]:
    """The `- ` facts under `## APRIL userContext` in the local override file.

    Strictly that heading: the provenance prose around it never becomes prompt
    text. Empty when the file (or the block) is absent.
    """
    path = deployment_root(root) / "etc" / "persona-user-context.md"
    if not path.is_file():
        return ()
    text = path.read_text(encoding="utf-8", errors="replace")
    m = _LOCAL_CONTEXT_HEADING.search(text)
    if not m:
        return ()
    facts: list[str] = []
    for line in text[m.end():].splitlines():
        if line.startswith("#"):
            break
        if line.strip().startswith("- "):
            facts.append(line.strip()[2:].strip())
    return tuple(facts)


def boot(
    persona: str,
    *,
    domain: str = "default",
    surface: SurfaceSpec | None = None,
    root: Path | str | None = None,
    local_context: bool = True,
) -> PersonaBoot:
    """Resolve persona → (system prompt, guardrails, temperature, source)."""
    if surface is None:
        from ..substrate.april import APRIL_SURFACE

        surface = APRIL_SURFACE
    name = str(persona or "").strip()
    if not name:
        raise ValueError("boot requires a persona id (APRIL_PERSONA)")

    # A fingerprint mismatch is never a reason to fall back silently — the
    # deployed tree drifted, so re-deployment has to be a decision.
    deployment = load_deployed(name, domain, surface=surface, root=root)

    profile = load_profile(name)  # unknown persona: loud FileNotFoundError
    temperature = float(derive(profile).temperature)
    if deployment is not None:
        tree = deployment.tree
        system_prompt = tree.get("systemprompt.md", "").strip()
        guardrails = tree.get("guardrails.md", "").strip()
        source = f"deployed:{deployment.row.get('domain', domain)}"
    else:
        system_prompt = compile_persona(profile).strip()
        guardrails = _compiled_guardrails(profile)
        source = f"profile:{name}"

    facts = load_local_overrides(root) if local_context else ()
    if facts and _ABOUT_USER not in system_prompt:
        system_prompt = (
            system_prompt.rstrip() + "\n\n" + _ABOUT_USER
            + "\n" + "\n".join(f"- {f}" for f in facts)
        )

    return PersonaBoot(
        persona=name,
        domain=domain,
        source=source,
        system_prompt=system_prompt,
        guardrails=guardrails,
        temperature=temperature,
        deployment=deployment,
        user_context=facts,
    )


class ActionGuard:
    """The runtime permission layer a persona's c2 text loads into.

    Machine-decidable, deterministic, and shared with the post-selection
    checklist: an explicit public action requires an approval marker in the
    same command string; credential-shaped text is refused outright. Everything
    else the guardrails say is attested (recorded with the action), never
    pretended to be verified at runtime.
    """

    def __init__(self, persona: str, guardrails: str = "", temperature: float | None = None):
        self.persona = str(persona)
        self.guardrails = str(guardrails or "")
        self.temperature = temperature

    def check(self, command: str) -> tuple[bool, str]:
        cmd = str(command or "")
        secrets = judge.secret_hits(cmd)
        if secrets:
            return (
                False,
                "secrets hygiene: never store, echo, or log secrets — "
                f"command carries credential-shaped text ({', '.join(secrets)})",
            )
        if judge.public_action_hits(cmd) and not judge.approved_marker(cmd):
            return (
                False,
                "public actions need a go-ahead: show the user first and get an "
                "explicit approval, then rerun with the marker in the command "
                "(e.g. `user approved the release`)",
            )
        return True, ""

    def attested_rules(self) -> list[str]:
        """The rule lines the guardrails carry beyond the two machine gates."""
        out: list[str] = []
        in_block = False
        for raw in self.guardrails.splitlines():
            line = raw.strip()
            if line == "## Protocols (non-negotiable)":
                in_block = True
                continue
            if line.startswith("## "):
                in_block = False
            if in_block and line and line != PROTOCOL_OVERRIDE_LINE:
                out.append(line.lstrip("0123456789. ").strip())
        return [rule for rule in out if rule]


def apply_to_runtime(
    agent: Any,
    persona: str | None = None,
    *,
    domain: str = "default",
    root: Path | str | None = None,
) -> PersonaBoot | None:
    """Attach a persona to an `AgentRuntime`; `None` is a no-op (no persona set).

    Mutates, in order: the system message at the head of the session context
    (exactly once), `config.temperature` from `derive()`, and
    `agent.persona_guard = ActionGuard(...)`. Emits one status event so the TUI
    can surface the boot.
    """
    config = getattr(agent, "config", None)
    pid = str(
        persona if persona is not None else getattr(config, "persona", "") or ""
    ).strip()
    if not pid:
        return None

    b = boot(pid, domain=domain, root=root)

    ctx = agent.session.context
    already = bool(
        ctx
        and ctx[0].get("role") == "system"
        and ctx[0].get("content") == b.system_prompt
    )
    if not already:
        ctx.insert(0, {"role": "system", "content": b.system_prompt})
    # The persona owns sampling while the boot is the active persona.
    config.temperature = b.temperature
    agent.persona_guard = ActionGuard(pid, b.guardrails, b.temperature)

    emit = getattr(agent, "_emit_status", None)
    if callable(emit):
        # # ponytail: core/events.py is user-owned and currently raises
        # AttributeError inside EventBus.emit (`StatusEvent` has no
        # `event_type`; emit_async references asyncio without importing
        # it), so ANY status emission crashes the constructor. A persona
        # boot must not be fatal because of an downstream TUI event:
        # swallow the transport failure, boot state is already applied.
        try:
            emit(
                "persona_booted",
                {
                    "persona": b.persona,
                    "domain": b.domain,
                    "source": b.source,
                    "temperature": b.temperature,
                    "system_prompt_chars": len(b.system_prompt),
                    "machine_rules": list(b.machine_rules),
                    "user_context_facts": len(b.user_context),
                },
            )
        except Exception:
            pass
    return b


def unboot(agent: Any) -> None:
    """Remove the persona's runtime state (system message, guard, temperature)."""
    ctx = agent.session.context
    while ctx and ctx[0].get("role") == "system":
        ctx.pop(0)
    agent.persona_guard = None
