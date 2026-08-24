from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class Finding:
    title: str
    type: str
    projects: list[str]
    claim: str
    experiment: str | None

    @property
    def is_connection(self) -> bool:
        return self.type == "connection"


FINDING_BLOCK = re.compile(r"===FINDING===\s*\n(.+)", re.DOTALL)
FIELD = {
    "TITLE": "title",
    "TYPE": "type",
    "PROJECTS": "projects",
    "CLAIM": "claim",
    "EXPERIMENT": "experiment",
}
CLAIM_LABEL = re.compile(r"^(FORMAL|EMPIRICAL|REPORTED|SPECULATIVE)\s*:", re.I)


def rate_finding(finding: Finding) -> int:
    """Return a deterministic 0–5 publication quality rating.

    Ratings are used to choose the strongest copy when agents emit the same
    finding. They are not a minimum-quality gate, so a unique finding keeps
    the pre-existing publication behavior.
    """
    score = 0
    if _normalize(finding.title):
        score += 1
    if _normalize(finding.claim):
        score += 1
    if CLAIM_LABEL.match(finding.claim.strip()):
        score += 1
    if _normalize(finding.experiment or ""):
        score += 1
    required_projects = 2 if finding.is_connection else 1
    if len(_project_names(finding)) >= required_projects:
        score += 1
    return score


def finding_fingerprint(finding: Finding) -> tuple[str, str, str, tuple[str, ...]]:
    """Return a whitespace/case-normalized identity for one finding.

    Project order is ignored because connection agents can report the same
    link from opposite directions. Punctuation and wording remain significant
    to avoid collapsing distinct hypotheses through fuzzy matching.
    """
    return (
        _normalize(finding.type) or "note",
        _normalize(finding.title),
        _normalize(finding.claim),
        tuple(sorted(_project_names(finding))),
    )


def prepare_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Deduplicate findings, retaining the highest-rated copy per identity."""
    selected: dict[tuple[str, str, str, tuple[str, ...]], Finding] = {}
    for finding in findings:
        key = finding_fingerprint(finding)
        previous = selected.get(key)
        if previous is None or rate_finding(finding) > rate_finding(previous):
            selected[key] = finding
    return list(selected.values())


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _project_names(finding: Finding) -> set[str]:
    return {_normalize(project) for project in finding.projects if _normalize(project)}


def parse_finding(output: str) -> Finding | None:
    match = FINDING_BLOCK.search(output)
    if not match:
        return None
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        key = key.strip().upper()
        value = value.strip()
        if key in FIELD and value and not value.startswith("<"):
            fields[FIELD[key]] = value.strip()
    if "title" not in fields or "claim" not in fields:
        return None
    return Finding(
        title=fields["title"],
        type=fields.get("type", "note").lower(),
        projects=[
            p.strip() for p in fields.get("projects", "").split(",") if p.strip()
        ],
        claim=fields["claim"],
        experiment=fields.get("experiment"),
    )


def append_to_inbox(finding: Finding, inbox_path: Path, origin: str = "agent") -> str:
    today = time.strftime("%Y-%m-%d")
    lines = [
        f"\n## {finding.title} ({today}, {origin})",
    ]
    lines.append(f"- Claim/hypothesis: {finding.claim}")
    if finding.experiment:
        lines.append(
            "- Why interesting: see smallest falsifiable experiment below (swarm-found)"
        )
        lines.append(f"- Smallest experiment: {finding.experiment}")
    else:
        lines.append("- Why interesting: swarm-found observation")
    if finding.projects:
        lines.append(f"- Connects to: {', '.join(finding.projects)}")
    entry = "\n".join(lines) + "\n"
    with inbox_path.open("a", encoding="utf-8") as fh:
        fh.write(entry)
    return entry


def append_to_connections(finding: Finding, connections_path: Path) -> str:
    if len(finding.projects) < 2:
        raise ValueError("a connection needs at least two projects")
    number = _next_connection_number(connections_path)
    row = (
        f"| C{number} | {finding.title} | {' ↔ '.join(finding.projects)} "
        f"| {finding.claim} | proposed |\n"
    )
    text = connections_path.read_text(encoding="utf-8") if connections_path.exists() else ""
    insert_at = _last_table_row_end(text)
    updated = text[:insert_at] + row + text[insert_at:]
    connections_path.write_text(updated, encoding="utf-8")
    return row


def _next_connection_number(connections_path: Path) -> int:
    if not connections_path.exists():
        return 1
    numbers = re.findall(r"^\|\s*C(\d+)\s*\|", connections_path.read_text(encoding="utf-8"), re.M)
    return max((int(n) for n in numbers), default=0) + 1


def _last_table_row_end(text: str) -> int:
    last = 0
    for match in re.finditer(r"^\|.*\n", text, re.M):
        last = match.end()
    return last
