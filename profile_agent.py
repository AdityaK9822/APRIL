#!/usr/bin/env python3
"""
APRIL Performance Profiler

Answers one question with data: where does the agent's wall time go?

Profiles live agent runs (local model via Ollama) under cProfile and reports:

1. Total wall time and time per run
2. The share of time spent inside the LLM call (`chat.completions.create`)
3. Hot spots ranked by cumulative time: everything
4. The same ranking restricted to APRIL's own code (core/, tools/)

Reading the result: if the ranking is dominated by the LLM call, the agent
is I/O-bound and runtime language is irrelevant; anything crowding the top
of the list above it is genuine Python overhead worth optimizing first.

Usage:
    python profile_agent.py                       # 3 runs with a default prompt
    python profile_agent.py --runs 5 --prompt "List the files in this project"

Requires a reachable LLM endpoint (OPENAI_API_BASE_URL in .env, e.g. `ollama serve`).
"""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile APRIL agent wall time")
    parser.add_argument(
        "--runs", type=int, default=3,
        help="number of agent runs to profile (default: 3)"
    )
    parser.add_argument(
        "--prompt",
        default="What tools do you have available? Answer in one short sentence.",
        help="prompt sent on every run"
    )
    return parser.parse_args()


def fmt(seconds: float) -> str:
    """Human-readable duration"""
    if seconds >= 1.0:
        return f"{seconds:.3f}s"
    if seconds >= 0.001:
        return f"{seconds * 1000:.1f}ms"
    return f"{seconds * 1_000_000:.0f}us"


def llm_wait_seconds(stats: pstats.Stats) -> float:
    """
    Cumulative seconds attributable to the LLM call entry point

    openai's Completions.create() only returns once the response is fully
    received, so its cumulative time is the LLM wait. The SDK has several
    create() variants; take the largest cumulative value.
    """
    best = 0.0
    for (filename, _, funcname), (_cc, _nc, _tt, ct, _callers) in stats.stats.items():
        if "openai" in filename and funcname == "create":
            best = max(best, ct)
    return best


def print_section(title: str) -> None:
    bar = "=" * 72
    print(f"\n{bar}\n{title}\n{bar}")


def main() -> int:
    args = parse_args()

    # Imported inside main so --help works without importing the full core
    from core.config import AgentConfig
    from core.agent import AgentRuntime

    config = AgentConfig.from_env()
    runtime = AgentRuntime(config)

    print(f"Profiling {args.runs} run(s) of the agent loop")
    print(f"  model : {config.model}")
    print(f"  prompt: {args.prompt!r}")

    profiler = cProfile.Profile()
    profiler.enable()
    started = time.perf_counter()
    failure = None
    try:
        for i in range(args.runs):
            response = runtime.run(args.prompt)
            print(f"  run {i + 1}/{args.runs}: responded with {len(response)} chars")
    except Exception as exc:  # keep the profile even on failure; diagnose below
        failure = exc
    wall = time.perf_counter() - started
    profiler.disable()

    per_run = wall / args.runs
    print_section(f"wall time: {fmt(wall)} total | {fmt(per_run)} per run ({args.runs} runs)")

    if failure is not None:
        print(f"Run failed with: {type(failure).__name__}: {failure}")
        print("If this is a connection error, start the LLM server (e.g. `ollama serve`) and retry.")
        print("The partial profile below is still valid for what did run.\n")

    ps = pstats.Stats(profiler)
    llm_wait = llm_wait_seconds(ps)
    share = f"{llm_wait / wall:.0%}" if wall > 0 else "0%"
    print(f"LLM wait (cumulative inside openai create()): {fmt(llm_wait)} = {share} of wall time")

    print_section("Top functions by cumulative time (all code)")
    text = io.StringIO()
    pstats.Stats(profiler, stream=text).sort_stats("cumulative").print_stats(25)
    print(text.getvalue())

    print_section("Top APRIL functions by cumulative time (core/, tools/)")
    agent_code = io.StringIO()
    pstats.Stats(profiler, stream=agent_code).sort_stats("cumulative").print_stats("core|tools", 20)
    print(agent_code.getvalue())

    print_section("How to read this")
    print(f"""\
The top cumulative entry should be the LLM 'create' call: the agent is
waiting on the model, not on Python.

{share} of wall time is LLM wait. A rewrite in any language leaves that
number untouched.

Look just below the LLM entry for Python-side hot spots. If none of APRIL's
own functions accumulate meaningful time there, no native module (Rust or
otherwise) would buy anything measurable.""")
    return 1 if failure is not None else 0


if __name__ == "__main__":
    sys.exit(main())
