from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_BUILD_ALLOWLIST = [
    "toy-projects/GameOfLife",
    "toy-projects/CellularAutomata",
    "apps/kotcumber",
    "apps/orchestrator",
]

DEFAULT_EXCLUDE = ["apps/orchestrator", "research/context-engines"]


@dataclass
class SwarmConfig:
    parallel: int = 8
    interval_min: int = 20

    def __post_init__(self) -> None:
        if not 5 <= self.parallel <= 10:
            raise ValueError("parallel must be between 5 and 10 in experimental mode")
        if not math.isfinite(self.interval_min) or self.interval_min < 0:
            raise ValueError("interval_min must be finite and non-negative")
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        if self.backend not in {"opencode", "claude", "echo"}:
            raise ValueError(f"unsupported backend: {self.backend!r}")

    timeout_s: int = 900
    backend: str = "opencode"
    model: str | None = None
    auto_approve: bool = False
    commit_per_finding: bool = False
    workdir: str = "/Users/fabian/Development"
    projects: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE))
    build_allowlist: list[str] = field(
        default_factory=lambda: list(DEFAULT_BUILD_ALLOWLIST)
    )


def _parse_scalar(raw: str) -> Any:
    text = raw.strip()
    if not text:
        return None
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        return [item.strip().strip("'\"") for item in inner.split(",")] if inner else []
    if (text.startswith("'") and text.endswith("'")) or (
        text.startswith('"') and text.endswith('"')
    ):
        return text[1:-1]
    if text.lower() in ("true", "yes"):
        return True
    if text.lower() in ("false", "no"):
        return False
    try:
        return int(text)
    except ValueError:
        return text


def parse_yaml_subset(text: str) -> dict[str, Any]:
    """Parse the minimal YAML subset this project needs: flat keys, lists of
    scalars or single-level mappings, comments, blank lines."""
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[Any] = []
    pending_map: dict[str, Any] | None = None

    def push_pending() -> None:
        nonlocal pending_map
        if pending_map is not None:
            current_list.append(pending_map)
            pending_map = None

    def flush() -> None:
        nonlocal current_key, current_list, pending_map
        push_pending()
        if current_key is not None:
            result[current_key] = current_list
        current_key = None
        current_list = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indented = line[:1] in (" ", "\t")
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            has_map_field = ":" in item and not item.startswith(("'", '"'))
            push_pending()
            if has_map_field:
                key, _, value = item.partition(":")
                pending_map = {key.strip(): _parse_scalar(value)}
            else:
                current_list.append(_parse_scalar(item))
            continue
        if indented and pending_map is not None:
            key, _, value = stripped.partition(":")
            pending_map[key.strip()] = _parse_scalar(value)
            continue
        flush()
        if ":" not in stripped:
            raise ValueError(f"cannot parse config line: {line!r}")
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if value:
            result[key] = _parse_scalar(value)
            current_key = None
        else:
            current_key = key
            current_list = []
            pending_map = None
    flush()
    return result


def load_config(path: Path) -> SwarmConfig:
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            data: dict[str, Any] = json.loads(text)
        else:
            data = parse_yaml_subset(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid config {path}: {exc}") from exc
    return config_from_mapping(data)


def _normalize_projects(entries: Any) -> list[str]:
    out: list[str] = []
    for entry in entries or []:
        if isinstance(entry, dict):
            path = str(entry.get("path", "")).strip()
            if path:
                out.append(path)
        elif isinstance(entry, str):
            out.append(entry)
    return out


def config_from_mapping(data: dict[str, Any]) -> SwarmConfig:
    data = dict(data)
    if "projects" in data:
        data["projects"] = _normalize_projects(data["projects"])
    known = {
        "parallel",
        "interval_min",
        "timeout_s",
        "backend",
        "model",
        "auto_approve",
        "commit_per_finding",
        "workdir",
        "projects",
        "exclude",
        "build_allowlist",
    }
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}")
    return SwarmConfig(**data)
