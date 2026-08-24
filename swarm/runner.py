from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from . import safety
from .backends import run_agent
from .config import SwarmConfig
from .findings import Finding, parse_finding
from .missions import Mission, build_brief
from .notebook import Notebook
from .registry import Project

STOP = threading.Event()
MARKER = "swarm-orchestrator-agent"
FINDING_RETRY = """
The previous response did not contain a parseable FINDING block. Retry the same
mission and finish with exactly one complete machine-readable block containing
non-empty TITLE and CLAIM fields. Keep the claim labeled FORMAL, EMPIRICAL,
REPORTED, or SPECULATIVE.
""".strip()


class ProvenanceError(Exception):
    """Raised when an opt-in BUILD provenance commit cannot be made safely."""


@dataclass(frozen=True)
class GitSnapshot:
    root: Path
    project_dir: Path
    head: str


def _git(cwd: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise ProvenanceError(f"git unavailable: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise ProvenanceError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _provenance_snapshot(mission: Mission, config: SwarmConfig) -> GitSnapshot | None:
    if not config.commit_per_finding or mission.kind != "BUILD":
        return None

    project_dir = (Path(config.workdir).expanduser() / mission.project).resolve()
    safety.check_path(str(project_dir), write=True)
    root = Path(
        _git(project_dir, "rev-parse", "--show-toplevel").strip()
    ).resolve()
    safety.check_path(str(root), write=True)
    try:
        project_dir.relative_to(root)
    except ValueError as exc:
        raise ProvenanceError("BUILD project is outside its git worktree") from exc

    status = _git(root, "status", "--porcelain=v1", "-z")
    if status:
        raise ProvenanceError("refusing provenance commit: worktree is not clean")
    head = _git(root, "rev-parse", "HEAD").strip()
    if not head:
        raise ProvenanceError("refusing provenance commit: repository has no HEAD")
    return GitSnapshot(root=root, project_dir=project_dir, head=head)


def _changed_paths(root: Path) -> list[str]:
    raw = _git(root, "status", "--porcelain=v1", "-z")
    paths: list[str] = []
    entries = raw.split("\0")
    for entry in entries:
        if not entry:
            continue
        if len(entry) < 4:
            raise ProvenanceError("git returned a malformed status record")
        code, path = entry[:2], entry[3:]
        if "R" in code or "C" in code:
            raise ProvenanceError("refusing provenance commit for rename or copy")
        paths.append(path)
    return paths


def _commit_message(title: str) -> str:
    cleaned = "".join(char for char in " ".join(title.split()) if char.isprintable())
    return f"swarm: {cleaned or 'BUILD finding'}"[:72]


def _unstage_paths(root: Path, paths: list[str]) -> None:
    try:
        _git(root, "reset", "--", *paths)
    except ProvenanceError as exc:
        raise ProvenanceError(
            f"provenance commit failed and staged changes could not be cleared: {exc}"
        ) from exc


def _commit_provenance(snapshot: GitSnapshot, finding: Finding) -> str:
    current_head = _git(snapshot.root, "rev-parse", "HEAD").strip()
    if current_head != snapshot.head:
        raise ProvenanceError("refusing provenance commit: HEAD changed during BUILD")

    paths = _changed_paths(snapshot.root)
    if not paths:
        raise ProvenanceError("BUILD finding produced no git changes")
    safe_paths: list[str] = []
    for path in paths:
        candidate = (snapshot.root / path).resolve()
        try:
            candidate.relative_to(snapshot.project_dir)
        except ValueError as exc:
            raise ProvenanceError(
                "BUILD changed a path outside the target project"
            ) from exc
        safety.check_path(str(candidate), write=True)
        safe_paths.append(path)

    staged = True
    try:
        _git(snapshot.root, "add", "--", *safe_paths)
        if not _git(snapshot.root, "diff", "--cached", "--name-only", "-z"):
            raise ProvenanceError("BUILD finding produced no staged changes")
        _git(snapshot.root, "commit", "-m", _commit_message(finding.title))
    except ProvenanceError:
        if staged:
            _unstage_paths(snapshot.root, safe_paths)
        raise
    return _git(snapshot.root, "rev-parse", "HEAD").strip()


def _record_provenance(
    mission: Mission,
    finding: Finding | None,
    result_ok: bool,
    snapshot: GitSnapshot | None,
    agent: str,
    notebook: Notebook,
) -> None:
    if snapshot is None or not result_ok or finding is None:
        return
    try:
        commit = _commit_provenance(snapshot, finding)
    except (ProvenanceError, safety.SafetyViolation) as exc:
        notebook.log(agent, "provenance_failed", {"error": str(exc)})
        return
    notebook.log(
        agent,
        "provenance_commit",
        {"kind": mission.kind, "project": mission.project, "commit": commit},
    )


def install_signal_handlers() -> None:
    def handler(signum: int, frame: object) -> None:
        STOP.set()

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


def make_mission(index: int, projects: list[Project], config: SwarmConfig) -> Mission:
    kind = _MISSION_ROTATION[index % len(_MISSION_ROTATION)]
    project = projects[index % len(projects)].path
    partner = None
    if kind == "CONNECT" and len(projects) > 1:
        partner = projects[(index + 1) % len(projects)].path
    write = kind in ("DOCUMENT", "BUILD")
    if kind == "BUILD":
        allowed = sorted({p.path for p in projects} & set(config.build_allowlist))
        if not allowed:
            raise safety.SafetyViolation("no BUILD-allowlisted project available")
        project = allowed[index % len(allowed)]
        partner = None
        safety.check_build_allowed(project, config.build_allowlist)
    else:
        safety.check_path(project, write=write)
        if partner:
            safety.check_path(partner)
    brief = build_brief(kind, project, partner)
    return Mission(kind=kind, project=project, partner=partner, brief=brief)


_MISSION_ROTATION = ["EXPLORE", "CONNECT", "IDEATE", "EXPLORE", "DOCUMENT", "BUILD"]


def dispatch(
    mission: Mission,
    agent: str,
    notebook: Notebook,
    config: SwarmConfig,
) -> tuple[bool, Finding | None]:
    if STOP.is_set():
        return False, None
    safety.check_path(config.workdir, write=mission.writable)
    if mission.kind == "BUILD":
        safety.check_build_allowed(mission.project, config.build_allowlist)
        safety.check_path(mission.project, write=True)
    try:
        snapshot = _provenance_snapshot(mission, config)
    except (ProvenanceError, safety.SafetyViolation) as exc:
        notebook.log(agent, "provenance_blocked", {"error": str(exc)})
        return False, None
    auto = config.auto_approve and mission.writable
    notebook.log(
        agent,
        "dispatch",
        {
            "kind": mission.kind,
            "project": mission.project,
            "partner": mission.partner,
            "backend": config.backend,
            "auto_approve": auto,
            "brief": mission.brief,
        },
    )
    result = run_agent(
        backend=config.backend,
        brief=mission.brief,
        cwd=config.workdir,
        timeout_s=config.timeout_s,
        model=config.model,
        auto=auto,
    )
    notebook.log(
        agent,
        "result",
        {
            "returncode": result.returncode,
            "timed_out": result.timed_out,
            "stdout_chars": len(result.stdout),
            "attempt": 1,
        },
    )
    finding = parse_finding(result.stdout)
    notebook.log(
        agent,
        "finding",
        {**finding.__dict__, "attempt": 1} if finding else None,
    )
    if result.ok and finding is None and not STOP.is_set():
        notebook.log(
            agent,
            "retry",
            {"reason": "missing_or_malformed_finding", "attempt": 2},
        )
        retry_result = run_agent(
            backend=config.backend,
            brief=f"{mission.brief}\n\n{FINDING_RETRY}",
            cwd=config.workdir,
            timeout_s=config.timeout_s,
            model=config.model,
            auto=auto,
        )
        notebook.log(
            agent,
            "result",
            {
                "returncode": retry_result.returncode,
                "timed_out": retry_result.timed_out,
                "stdout_chars": len(retry_result.stdout),
                "attempt": 2,
            },
        )
        finding = parse_finding(retry_result.stdout)
        notebook.log(
            agent,
            "finding",
            {**finding.__dict__, "attempt": 2} if finding else None,
        )
        _record_provenance(
            mission,
            finding,
            retry_result.ok,
            snapshot,
            agent,
            notebook,
        )
        return retry_result.ok, finding
    _record_provenance(mission, finding, result.ok, snapshot, agent, notebook)
    return result.ok, finding


def reap_stale(run_root: Path) -> list[int]:
    """Kill leftover swarm agent processes from previous runs (pid files)."""
    reaped: list[int] = []
    if not run_root.exists():
        return reaped
    for pid_file in run_root.glob("*/pids.json"):
        try:
            pids = [int(p) for p in pid_file.read_text().split()]
        except (ValueError, OSError):
            continue
        for pid in pids:
            if _is_swarm_process(pid):
                try:
                    os.kill(pid, signal.SIGTERM)
                    reaped.append(pid)
                except OSError:
                    pass
    return reaped


def _is_swarm_process(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            return MARKER.encode() in fh.read()
    except OSError:
        pass
    try:
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return MARKER in out.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


class Swarm:
    def __init__(
        self,
        config: SwarmConfig,
        projects: list[Project],
        notebook: Notebook,
        dry_run: bool = False,
    ) -> None:
        self.config = config
        self.projects = projects
        self.notebook = notebook
        self.dry_run = dry_run
        self.mission_index = 0
        self.findings: list[Finding] = []

    def next_mission(self) -> Mission:
        guard = 0
        while guard < len(_MISSION_ROTATION) * len(self.projects) + 8:
            guard += 1
            try:
                mission = make_mission(self.mission_index, self.projects, self.config)
            except safety.SafetyViolation:
                self.mission_index += 1
                continue
            self.mission_index += 1
            return mission
        raise RuntimeError("no dispatchable mission: every candidate was denied")

    def wave(self, size: int) -> list[tuple[str, Mission]]:
        jobs: list[tuple[str, Mission]] = []
        target = min(size, len({project.path for project in self.projects}))
        seen_projects: set[str] = set()
        attempts = 0
        attempt_limit = (
            len(_MISSION_ROTATION) * max(len(self.projects), 1) + 8
        )
        while len(jobs) < target and attempts < attempt_limit:
            attempts += 1
            mission = self.next_mission()
            if mission.project in seen_projects:
                continue
            seen_projects.add(mission.project)
            slot = len(jobs)
            agent = f"agent-{slot + 1}"
            jobs.append((agent, mission))
        return jobs

    def run_wave(self) -> int:
        wave_id = time.strftime("%H%M%S")
        jobs = self.wave(self.config.parallel)
        collected = 0
        if self.dry_run:
            for agent, mission in jobs:
                print(
                    f"[dry-run] {agent}: {mission.kind} on {mission.project}"
                    + (f" <-> {mission.partner}" if mission.partner else "")
                )
                self.notebook.log(agent, "dispatch_dry_run", mission.brief)
            return 0
        with ThreadPoolExecutor(max_workers=self.config.parallel) as pool:
            futures = [
                (
                    agent,
                    pool.submit(
                        dispatch,
                        mission,
                        f"{agent}-w{wave_id}",
                        self.notebook,
                        self.config,
                    ),
                )
                for agent, mission in jobs
            ]
            for _, future in futures:
                ok, finding = future.result()
                if ok and finding is not None:
                    self.findings.append(finding)
                    collected += 1
        return collected

    def run_for_hours(self, hours: float, interval_min: float) -> int:
        deadline = time.monotonic() + hours * 3600.0
        total = 0
        while not STOP.is_set() and time.monotonic() < deadline:
            total += self.run_wave()
            remaining = deadline - time.monotonic()
            wait = min(interval_min * 60.0, max(remaining, 0.0))
            if wait > 0 and not STOP.is_set():
                STOP.wait(wait)
        return total
