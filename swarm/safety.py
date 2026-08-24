from __future__ import annotations

import re
from pathlib import Path
from re import Pattern


class SafetyViolation(Exception):
    pass


DENY_PATTERNS: list[Pattern[str]] = [
    re.compile(r"sokra", re.IGNORECASE),
    re.compile(r"(^|[/\\\s])\.env([/\s.\"']|$)", re.IGNORECASE),
    re.compile(r"service[_ -]?account", re.IGNORECASE),
    re.compile(r"context-engines/context-ai", re.IGNORECASE),
]

WRITE_DENY_PATTERNS: list[Pattern[str]] = DENY_PATTERNS + [
    re.compile(r"apps/coding-agent", re.IGNORECASE),
    re.compile(r"^learning/", re.IGNORECASE),
]


def _match(path_or_text: str, patterns: list[Pattern[str]]) -> str | None:
    for pattern in patterns:
        if pattern.search(path_or_text):
            return pattern.pattern
    return None


def check_path(path: str, write: bool = False) -> None:
    """Raise SafetyViolation if a path or its resolved target is forbidden."""
    patterns = WRITE_DENY_PATTERNS if write else DENY_PATTERNS
    candidates = (path, str(Path(path).expanduser().resolve(strict=False)))
    for candidate in candidates:
        hit = _match(candidate, patterns)
        if hit:
            raise SafetyViolation(f"denied path (pattern {hit!r}): {path}")


def check_task(text: str, cwd: str | None = None) -> None:
    """Validate a full mission brief + working directory before dispatch."""
    check_path(cwd or "")
    check_text(text)


def check_text(text: str) -> None:
    hit = _match(text, DENY_PATTERNS)
    if hit:
        raise SafetyViolation(f"denied content (pattern {hit!r})")


def check_build_allowed(project: str, allowlist: list[str]) -> None:
    if project not in allowlist:
        raise SafetyViolation(f"project {project!r} is not in the BUILD allowlist")
