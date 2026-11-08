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

"""The ADE CLI: `python3 -m core.ade` — deployment through APRIL's own tools.

The ADE must itself be an APRIL agent: an agent with the shell tool drives the
same commands a human would, and nothing here needs a model or a network.

    python3 -m core.ade deploy   --harness runs/.../harnesses/inv1 \
        --persona april --domain default --task demo/demo-0001 [--score 0.9]
    python3 -m core.ade boot     --persona april [--domain default]
    python3 -m core.ade view     --persona april [--library .ade/library]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..substrate.april import APRIL_SURFACE
from . import views
from .boot import boot as boot_persona
from .deploy import deploy

def _cmd_deploy(args: argparse.Namespace) -> int:
    row = deploy(
        Path(args.harness),
        surface=APRIL_SURFACE,
        persona=args.persona,
        domain=args.domain,
        task_id=args.task or "",
        run_dir=args.run_dir or "",
        score=float(args.score) if args.score is not None else None,
    )
    print(json.dumps(row, indent=2))
    return 0


def _cmd_boot(args: argparse.Namespace) -> int:
    b = boot_persona(args.persona, domain=args.domain, root=args.root or None)
    print(
        json.dumps(
            {
                "persona": b.persona,
                "domain": b.domain,
                "source": b.source,
                "temperature": b.temperature,
                "system_prompt_chars": len(b.system_prompt),
                "guardrail_chars": len(b.guardrails),
                "machine_rules": list(b.machine_rules),
                "user_context_facts": len(b.user_context),
            },
            indent=2,
        )
    )
    return 0


def _cmd_view(args: argparse.Namespace) -> int:
    print(
        json.dumps(
            views.persona_view(
                args.persona,
                domain=args.domain,
                library_root=Path(args.library) if args.library else None,
                root=args.root or None,
            ),
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m core.ade", description=__doc__)
    parser.add_argument(
        "--root", default="", help="ADE root override (default: APRIL_ADE_ROOT or .ade/)"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("deploy", help="deploy an adopted tree for a persona")
    p.add_argument("--harness", required=True, help="adopted harness directory")
    p.add_argument("--persona", required=True)
    p.add_argument("--domain", default="default")
    p.add_argument("--task", default="", help="task id the tree was adopted from")
    p.add_argument("--run-dir", default="")
    p.add_argument("--score", default=None, help="post-selection score, if any")
    p.set_defaults(fn=_cmd_deploy)

    p = sub.add_parser("boot", help="resolve a persona boot (dry, no model)")
    p.add_argument("--persona", required=True)
    p.add_argument("--domain", default="default")
    p.set_defaults(fn=_cmd_boot)

    p = sub.add_parser("view", help="persona view JSON for the TUI")
    p.add_argument("--persona", required=True)
    p.add_argument("--domain", default="default")
    p.add_argument("--library", default="", help="library root (library_root/<persona>/)")
    p.set_defaults(fn=_cmd_view)

    args = parser.parse_args(argv)
    if getattr(args, "root", ""):
        import os

        os.environ["APRIL_ADE_ROOT"] = str(args.root)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
