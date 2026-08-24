from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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
        },
    )
    finding = parse_finding(result.stdout)
    notebook.log(agent, "finding", finding.__dict__ if finding else None)
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
