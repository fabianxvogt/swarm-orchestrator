from __future__ import annotations

import subprocess
from typing import Optional


class BackendResult:
    def __init__(self, returncode: int, stdout: str, timed_out: bool) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.timed_out = timed_out

    @property
    def ok(self) -> bool:
        return not self.timed_out and self.returncode == 0


def build_command(backend: str, brief: str, model: str | None, auto: bool) -> list[str]:
    if backend == "opencode":
        cmd = ["/opt/homebrew/bin/opencode", "run"]
        if model:
            cmd += ["--model", model]
        if auto:
            cmd += ["--auto"]
        return cmd + [brief]
    if backend == "claude":
        cmd = ["claude", "-p", brief]
        if model:
            cmd += ["--model", model]
        return cmd
    if backend == "echo":
        return ["/bin/echo", "ECHO BACKEND OUTPUT", brief]
    raise ValueError(f"unknown backend: {backend}")


def run_agent(
    backend: str,
    brief: str,
    cwd: str,
    timeout_s: int,
    model: str | None = None,
    auto: bool = False,
) -> BackendResult:
    cmd = build_command(backend, brief, model, auto)
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return BackendResult(proc.returncode, proc.stdout, timed_out=False)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return BackendResult(-1, stdout or "", timed_out=True)
