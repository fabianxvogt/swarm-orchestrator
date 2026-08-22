from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

MISSION_TYPES = ["EXPLORE", "CONNECT", "IDEATE", "DOCUMENT", "BUILD"]
WRITE_TYPES = {"DOCUMENT", "BUILD"}
READ_TYPES = {"EXPLORE", "CONNECT", "IDEATE"}

SAFETY_PREAMBLE = """You are one subagent in a long-running swarm tending Fabian's dev
portfolio at /Users/fabian/Development. Hard rules, no exceptions:
- NEVER read, write, list, or cd into any path matching Sokra* (case-insensitive).
- NEVER open .env files, service-account keys, or anything under
  research/context-engines/context-ai.
- Stay strictly read-only unless the mission explicitly authorizes small writes.
- Label claims FORMAL / EMPIRICAL / REPORTED / SPECULATIVE. Prefer falsifiable,
  small, verifiable steps over grand rewrites.
"""

FINDING_FOOTER = """
Finish your reply with exactly one machine-readable block:

===FINDING===
TITLE: <one line>
TYPE: idea | connection | note
PROJECTS: <comma-separated repo paths you touched or linked>
CLAIM: <the finding or hypothesis, one line, with claim label>
EXPERIMENT: <smallest falsifiable experiment, one line; omit for note>
"""


@dataclass(frozen=True)
class Mission:
    kind: str
    project: str
    partner: str | None
    brief: str

    @property
    def writable(self) -> bool:
        return self.kind in WRITE_TYPES


def build_brief(kind: str, project: str, partner: str | None = None) -> str:
    if kind not in MISSION_TYPES:
        raise ValueError(f"unknown mission type: {kind}")
    body = _BODIES[kind](project, partner)
    return f"{SAFETY_PREAMBLE}\nMission type: {kind}\n\n{body}{FINDING_FOOTER}"


def _explore(project: str, partner: str | None) -> str:
    return (
        f"Deep-dive the project `{project}` (read its README.md, ROADMAP.md and skim "
        f"docs/ plus key source files). Produce a status snapshot: what it is, what is "
        f"solid, what is stale or broken, and the single most interesting unsolved "
        f"question it could attack next."
    )


def _connect(project: str, partner: str | None) -> str:
    target = partner or "another portfolio project"
    return (
        f"Hunt for a concrete, evidence-backed connection between `{project}` and "
        f"`{target}` (shared abstractions, reusable methods, mirrored problems). "
        f"Cite specific files/functions as evidence. Only report a connection if it "
        f"would survive a skeptical reviewer."
    )


def _ideate(project: str, partner: str | None) -> str:
    return (
        f"Invent one new falsifiable experiment inspired by `{project}`, aimed at an "
        f"unsolved or under-explored problem. State claim, why it matters, and the "
        f"smallest experiment that could refute it."
    )


def _document(project: str, partner: str | None) -> str:
    return (
        f"You MAY make small writes inside `{project}` only. Review its README.md and "
        f"ROADMAP.md against the actual code. Fix factual drift, add a missing "
        f"quickstart, and move completed ROADMAP items to Done. Keep edits minimal and "
        f"do not commit."
    )


def _build(project: str, partner: str | None) -> str:
    return (
        f"You MAY make one small verifiable increment inside `{project}` only: a test, "
        f"a bug fix, or a tiny feature with a passing check. Do not refactor, do not "
        f"commit, keep the diff under ~100 lines."
    )


_BODIES = {
    "EXPLORE": _explore,
    "CONNECT": _connect,
    "IDEATE": _ideate,
    "DOCUMENT": _document,
    "BUILD": _build,
}
