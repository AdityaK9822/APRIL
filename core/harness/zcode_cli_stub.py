#!/usr/bin/env python3
"""Offline stand-in for the zcode CLI binary: the PROCESS contract, no model.

The zcode adapter points APRIL_ZCODE_BIN here in offline self-checks (no model,
no network, no device). It honors the documented batch recipe exactly:

- the argument set the adapter sends: --prompt/--cwd/--mode/--disallowed-tools/
  --output-format/--no-color (unknown flags are a loud exit 2),
- refuses to run without per-sample isolation (ZCODE_DATA_BASE_DIR),
- writes the FORCED deliverable the prompt names under <cwd>/deliverables/,
- emits a small stream-json transcript on stdout (system/assistant/result),
- records prove-isolation state under <runHome>/.zcode/cli/agent_state.json.

It reads nothing else on disk on purpose: a stub that inspected the workspace
would be exercising a contract the real CLI does not have.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

_KNOWN_FLAGS = {
    "--prompt",
    "--cwd",
    "--mode",
    "--disallowed-tools",
    "--output-format",
    "--no-color",
}
# The forced output path the prompt names, e.g. `deliverables/device-write-plan.md`.
_FORCED_RX = re.compile(r"\bdeliverables/([A-Za-z0-9_][A-Za-z0-9._-]*)")


def die(msg: str, code: int) -> None:
    sys.stderr.write(f"zcode-stub: {msg}\n")
    raise SystemExit(code)


def parse_args(argv: list[str]) -> dict[str, str | list[str]]:
    out: dict[str, str | list[str]] = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a not in _KNOWN_FLAGS:
            die(f"unrecognized flag {a!r} (the adapter may only send the documented set)", 2)
        if a == "--no-color":
            out["--no-color"] = "1"
            i += 1
            continue
        if i + 1 >= len(argv):
            die(f"{a} needs a value", 2)
        out[a] = argv[i + 1]
        i += 2
    for required in ("--prompt", "--cwd", "--mode", "--output-format"):
        if required not in out:
            die(f"missing required flag {required}", 2)
    if out["--mode"] != "yolo":
        die(f"the batch recipe runs --mode yolo, got {out['--mode']!r}", 2)
    if out["--output-format"] != "stream-json":
        die(f"the batch recipe reads stream-json, got {out['--output-format']!r}", 2)
    return out


def forced_deliverable(prompt: str) -> str | None:
    """The forced output path the prompt names, e.g. `deliverables/x.md`."""
    m = _FORCED_RX.search(prompt)
    if not m:
        return None
    return None if ".." in m.group(0) else m.group(0)


def main() -> None:
    run_home = os.environ.get("ZCODE_DATA_BASE_DIR", "").strip()
    if not run_home:
        die("refusing to run without per-sample isolation (ZCODE_DATA_BASE_DIR)", 3)
    args = parse_args(sys.argv[1:])
    cwd = Path(str(args["--cwd"])).resolve()
    if not cwd.is_dir():
        die(f"--cwd {cwd} does not exist", 2)
    prompt = str(args["--prompt"])

    # The CLI keeps its own data under HOME==ZCODE_DATA_BASE_DIR; prove the isolation
    # landed by recording state where only a redirected HOME would produce it.
    state_dir = Path(run_home) / ".zcode" / "cli"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "agent_state.json").write_text(
        json.dumps(
            {
                "stub": "zcode_cli_stub/1",
                "cwd": str(cwd),
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()[:16],
                "home": run_home,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # stream-json transcript: a system line, an assistant line, then the result.
    rel = forced_deliverable(prompt)
    note = (
        f"deliverable forced at {rel}"
        if rel
        else "no forced deliverable named in the prompt"
    )
    print(json.dumps({"type": "system", "subtype": "init", "cwd": str(cwd), "mode": "yolo"}))
    for step in (
        "read input/ and the harness files in the workspace",
        "draft the deliverable per the task's stated shape",
    ):
        print(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": f"stub step: {step}"}]},
                }
            )
        )

    if rel:
        dest = (cwd / rel).resolve()
        if not str(dest).startswith(str(cwd)):
            die(f"forced deliverable {rel!r} escapes the workspace", 4)
        dest.parent.mkdir(parents=True, exist_ok=True)
        body = (
            f"# {rel.rsplit('/', 1)[-1].rsplit('.', 1)[0].replace('-', ' ').title()}\n\n"
            f"{note}.\n\n"
            "Written by the offline zcode stub: a forced-deliverable proof, not agent work.\n"
        )
        dest.write_text(body, encoding="utf-8")

    print(json.dumps({"type": "result", "result": f"stub run complete: {note}", "is_error": False}))


if __name__ == "__main__":
    main()
