from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Project:
    path: str
    name: str
    rating: float | None = None


TIER_A_HEADER = re.compile(r"^##\s+Tier A", re.IGNORECASE)
NEXT_HEADER = re.compile(r"^##\s+", re.IGNORECASE)
ROW = re.compile(r"^\|\s*`([^`]+)`")


def parse_inventory(text: str) -> list[Project]:
    projects: list[Project] = []
    in_tier_a = False
    for line in text.splitlines():
        if TIER_A_HEADER.match(line):
            in_tier_a = True
            continue
        if in_tier_a and NEXT_HEADER.match(line):
            break
        if not in_tier_a:
            continue
        match = ROW.match(line)
        if not match:
            continue
        path = match.group(1).strip().rstrip("/")
        if path:
            projects.append(Project(path=path, name=path.rsplit("/", 1)[-1]))
    return dedupe(projects)


def dedupe(projects: Iterable[Project]) -> list[Project]:
    seen: dict[str, Project] = {}
    for project in projects:
        seen.setdefault(project.path, project)
    return list(seen.values())


def load_registry(inventory_path: Path) -> list[Project]:
    return parse_inventory(inventory_path.read_text(encoding="utf-8"))


def apply_filters(
    projects: list[Project],
    override: list[str] | None = None,
    exclude: Iterable[str] = (),
) -> list[Project]:
    result = projects
    if override:
        known = {p.path: p for p in projects}
        result = [
            known.get(path, Project(path=path, name=path.rsplit("/", 1)[-1]))
            for path in override
        ]
    excluded = set(exclude)
    return [p for p in result if p.path not in excluded]
