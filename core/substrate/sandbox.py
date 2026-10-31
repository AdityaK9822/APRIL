"""Local, asynchronous, isolated Python execution sandbox."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

_PROXY_VARS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "FTP_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "ftp_proxy",
    "no_proxy",
)


@dataclass
class SandboxResult:
    """Result of a single sandboxed execution."""

    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    timed_out: bool = False
    error: str | None = None
    duration: float = 0.0
    workdir: str | None = None



    @property
    def exit_code(self) -> int | None:
        return self.returncode

    @property
    def success(self) -> bool:
        return (
            not self.timed_out
            and self.error is None
            and self.returncode == 0
        )

class Sandbox:
    """Runs Python code in an isolated per-call working directory."""

    def __init__(
        self,
        *,
        timeout: int = 30,
        max_output: int = 50_000,
        allow_network: bool = False,
        base_workdir: str | Path | None = None,
        max_output_bytes: int | None = None,
        workdir: str | Path | None = None,
        root: str | Path | None = None,
        cwd: str | Path | None = None,
        **_: object,
    ) -> None:
        if max_output_bytes is not None:
            max_output = max_output_bytes
        if base_workdir is None:
            base_workdir = workdir if workdir is not None else (root if root is not None else cwd)
        self.timeout = int(timeout)
        self.max_output = int(max_output)
        self.allow_network = bool(allow_network)
        self.base_workdir = Path(base_workdir) if base_workdir else None

    def _env(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        env = dict(os.environ)
        if not self.allow_network:
            for name in _PROXY_VARS:
                env.pop(name, None)
            env["NO_PROXY"] = "*"
            env["no_proxy"] = "*"
        env.setdefault("PYTHONUNBUFFERED", "1")
        if extra:
            env.update(extra)
        return env

    def _clip(self, text: str, limit: int | None = None) -> str:
        limit = self.max_output if limit is None else int(limit)
        if len(text) <= limit:
            return text
        return text[:limit] + f"\n... [output clipped to {limit} chars]"

    async def run_script(
        self,
        script: str,
        *,
        args: Sequence[str] | None = None,
        env: Mapping[str, str] | None = None,
        timeout: int | None = None,
        max_output: int | None = None,
        workdir: str | Path | None = None,
    ) -> SandboxResult:
        """Execute ``script`` (Python source) in an isolated working directory."""
        effective_timeout = self.timeout if timeout is None else int(timeout)
        effective_max = self.max_output if max_output is None else int(max_output)
        args = list(args or ())

        started = time.monotonic()
        if workdir is None:
            with tempfile.TemporaryDirectory(
                prefix="april-sandbox-", dir=self.base_workdir
            ) as td:
                workdir_path = Path(td)
                return await self._run(
                    workdir_path,
                    script,
                    args,
                    env,
                    effective_timeout,
                    effective_max,
                    started,
                )
        else:
            workdir_path = Path(workdir)
            workdir_path.mkdir(parents=True, exist_ok=True)
            return await self._run(
                workdir_path,
                script,
                args,
                env,
                effective_timeout,
                effective_max,
                started,
            )

    async def run_file(
        self,
        path: str | Path,
        *,
        args: Sequence[str] | None = None,
        env: Mapping[str, str] | None = None,
        timeout: int | None = None,
        max_output: int | None = None,
        workdir: str | Path | None = None,
    ) -> SandboxResult:
        """Execute an existing Python file in an isolated working directory."""
        path = Path(path)
        if not path.is_file():
            return SandboxResult(error=f"script file not found: {path}", workdir=str(path.parent))
        source = path.read_text(encoding="utf-8", errors="replace")
        # Place a copy so the original source tree is never executed in place.
        effective_workdir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="april-sandbox-", dir=self.base_workdir))
        effective_workdir.mkdir(parents=True, exist_ok=True)
        staged = effective_workdir / path.name
        staged.write_text(source, encoding="utf-8")
        return await self.run_script(
            source,
            args=args,
            env=env,
            timeout=timeout,
            max_output=max_output,
            workdir=effective_workdir,
        )

    async def _run(
        self,
        workdir: Path,
        script: str,
        args: list[str],
        env_override: Mapping[str, str] | None,
        timeout: int,
        max_output: int,
        started: float,
    ) -> SandboxResult:
        result = SandboxResult(workdir=str(workdir))
        script_path = workdir / "_sandbox_script.py"
        try:
            # Security: strip null bytes that can be used to bypass checks.
            safe_script = script.replace("\x00", "")
            script_path.write_text(safe_script, encoding="utf-8")
        except OSError as exc:
            result.error = f"failed to stage script: {exc}"
            result.duration = time.monotonic() - started
            return result

        env = self._env(env_override)
        proc = None
        try:
            preexec = None
            try:
                import resource as _resource  # noqa: F401

                def _apply_limits() -> None:
                    import resource

                    # Prevent runaway CPU/memory/disk use inside the sandbox.
                    try:
                        resource.setrlimit(resource.RLIMIT_CPU, (max(1, timeout), max(2, timeout + 1)))
                    except (ValueError, OSError):
                        pass
                    try:
                        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
                    except (ValueError, OSError):
                        pass
                    try:
                        resource.setrlimit(resource.RLIMIT_FSIZE, (max_output, max_output))
                    except (ValueError, OSError):
                        pass
                    os.chdir(str(workdir))

                preexec = _apply_limits
            except ImportError:
                preexec = None

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script_path),
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workdir),
                env=env,
                preexec_fn=preexec,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                try:
                    await proc.wait()
                except Exception:
                    pass
                result.timed_out = True
                result.error = f"timed out after {timeout} seconds"
                result.duration = time.monotonic() - started
                return result

            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")
            result.stdout = self._clip(stdout, max_output)
            result.stderr = self._clip(stderr, max_output)
            result.returncode = proc.returncode
            if proc.returncode != 0:
                result.error = stderr.strip() or f"process exited with code {proc.returncode}"
            result.duration = time.monotonic() - started
            return result
        except Exception as exc:  # pragma: no cover - defensive
            result.error = f"{type(exc).__name__}: {exc}"
            result.duration = time.monotonic() - started
            if proc is not None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            return result
