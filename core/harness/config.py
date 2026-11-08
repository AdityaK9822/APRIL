from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSPORT_ATTEMPTS = 2
PHASE_WIDTH = 2
PROPOSER_CONCURRENCY = 2
VERTEX_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
VERTEX_REGION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
PROPOSER_MODEL_BY_CHANNEL = {}
# The opencode channel stays off until a real checkout exists (no
# scripts/setup_benchmark.py in P0), so the fallback default is the channel that
# can actually run: claude_cli.
DEFAULT_PROPOSER_CHANNEL = "claude_cli"
# bun launcher binary for the opencode channel (P0: config surface only).
BUN = os.environ.get("APRIL_BUN", "bun")
# A pinned OpenCode checkout mounted here enables the opencode channel; empty
# leaves the channel off, and every call fails as a ProposerError.
OPENCODE_DIR = os.environ.get("APRIL_OPENCODE_DIR", "")
# The zcode substrate's CLI binary: an absolute path to the SEA build or a name
# on PATH. Read at SPAWN time by the zcode adapter (APRIL_ZCODE_BIN override,
# this value as the fallback) so offline self-checks can point each invocation
# at the process-boundary stub without a config reload.
ZCODE_BIN = os.environ.get("APRIL_ZCODE_BIN", "zcode")
