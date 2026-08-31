from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Mapping, Optional


class TokenAccountingError(RuntimeError):
    """Raised when a result cannot satisfy an exact pilot token budget."""


@dataclass(frozen=True)
class TokenUsage:
    """Complete token accounting supplied by a backend or deterministic fixture."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    source: str
    complete: bool = True

    def __post_init__(self) -> None:
        for name in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens + output_tokens")
        if type(self.source) is not str or self.source not in {
            "provider",
            "echo-fixture",
        }:
            raise ValueError("source must be 'provider' or 'echo-fixture'")
        if self.complete is not True:
            raise ValueError("complete must be true")

    @classmethod
    def from_payload(cls, payload: object) -> TokenUsage:
        """Parse a strict serialized receipt without accepting missing/extra fields."""
        if not isinstance(payload, Mapping):
            raise ValueError("token usage payload must be a mapping")
        expected = {
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "source",
            "complete",
        }
        if set(payload) != expected:
            raise ValueError("token usage payload has missing or unexpected fields")
        return cls(
            input_tokens=payload["input_tokens"],
            output_tokens=payload["output_tokens"],
            total_tokens=payload["total_tokens"],
            source=payload["source"],
            complete=payload["complete"],
        )

    def as_payload(self) -> dict[str, object]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "source": self.source,
            "complete": self.complete,
        }


@dataclass(frozen=True)
class BackendResult:
    returncode: int
    stdout: str
    timed_out: bool
    usage: TokenUsage | None = None

    @property
    def ok(self) -> bool:
        return not self.timed_out and self.returncode == 0


def require_pilot_token_usage(
    result: BackendResult, max_total_tokens: int
) -> TokenUsage:
    """Admit only a successful result with exact provider token usage."""
    return _require_token_usage(result, max_total_tokens, source="provider")


def require_fixture_token_usage(
    result: BackendResult, max_total_tokens: int
) -> TokenUsage:
    """Admit deterministic echo units to a fixture-only preflight."""
    return _require_token_usage(result, max_total_tokens, source="echo-fixture")


def _require_token_usage(
    result: BackendResult, max_total_tokens: int, source: str
) -> TokenUsage:
    if type(max_total_tokens) is not int or max_total_tokens < 0:
        raise ValueError("max_total_tokens must be a non-negative integer")
    if not result.ok:
        raise TokenAccountingError("backend result was not successful")
    usage = result.usage
    if usage is None:
        raise TokenAccountingError("exact token usage is unavailable")
    if type(usage) is not TokenUsage:
        raise TokenAccountingError("token usage has an invalid type")
    try:
        validated = TokenUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            source=usage.source,
            complete=usage.complete,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise TokenAccountingError("token usage is invalid") from exc
    if validated.source != source:
        raise TokenAccountingError(
            f"{validated.source!r} usage cannot satisfy {source!r} accounting"
        )
    if validated.total_tokens > max_total_tokens:
        raise TokenAccountingError(
            f"token budget exceeded: {validated.total_tokens} > {max_total_tokens}"
        )
    return validated


def _echo_fixture_usage(brief: str, stdout: str) -> TokenUsage:
    """Count UTF-8 bytes as deterministic fixture units, never provider tokens."""
    input_tokens = len(brief.encode("utf-8"))
    output_tokens = len(stdout.encode("utf-8"))
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        source="echo-fixture",
    )


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
        usage = _echo_fixture_usage(brief, proc.stdout) if backend == "echo" else None
        return BackendResult(
            proc.returncode,
            proc.stdout,
            timed_out=False,
            usage=usage,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return BackendResult(-1, stdout or "", timed_out=True)
