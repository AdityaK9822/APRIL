#!/usr/bin/env python3
"""Start the APRIL backend and web frontend with one command."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / ".venv" / "bin" / "python"
FRONTEND = ROOT / "web"


def main() -> int:
    if not BACKEND.exists():
        print("Backend venv was not found at .venv/bin/python.", file=sys.stderr)
        return 1
    if not (FRONTEND / "package.json").exists():
        print("Frontend was not found in web/package.json.", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env.setdefault("APRIL_API_PORT", "8000")

    backend = subprocess.Popen(
        [str(BACKEND), "-m", "core.api"],
        cwd=str(ROOT),
        env=env,
    )
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(FRONTEND),
    )

    print("APRIL dev services starting...")
    print("Backend:  http://127.0.0.1:8000")
    print("Frontend: check the Vite output for the URL")
    print("Press Ctrl+C to stop both.")

    try:
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        print("\nStopping services...")
        for process in (frontend, backend):
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
        for process in (frontend, backend):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
EOF