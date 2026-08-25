from __future__ import annotations

import math
import subprocess

import pytest

from swarm import safety
import swarm.runner as runner
from swarm.backends import BackendResult
from swarm.config import SwarmConfig
from swarm.missions import Mission
from swarm.notebook import Notebook
from swarm.registry import Project
from swarm.orchestrator import _publish

FINDING_OUTPUT = """===FINDING===
TITLE: Failed child finding
TYPE: idea
CLAIM: should not be published
"""


@pytest.mark.parametrize("returncode,timed_out", [(1, False), (-1, True)])
def test_failed_or_timed_out_child_finding_is_not_collected(
    monkeypatch, tmp_path, returncode, timed_out
):
    calls = []

    def fake_run_agent(**kwargs):
        calls.append(kwargs)
        return BackendResult(returncode, FINDING_OUTPUT, timed_out)

    monkeypatch.setattr(runner, "run_agent", fake_run_agent)
    swarm = runner.Swarm(
        SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path)),
        [Project(path="toy-projects/rule30", name="rule30")],
        Notebook(tmp_path / "run"),
    )

    assert swarm.run_wave() == 0
    assert swarm.findings == []
    assert len(calls) == 1


def test_dispatch_retries_once_when_finding_is_missing(monkeypatch, tmp_path):
    calls = []
    outputs = [
        BackendResult(0, "useful prose without the required block", False),
        BackendResult(
            0,
            "===FINDING===\nTITLE: recovered\nCLAIM: EMPIRICAL: retry works\n",
            False,
        ),
    ]

    def fake_run_agent(**kwargs):
        calls.append(kwargs)
        return outputs.pop(0)

    monkeypatch.setattr(runner, "run_agent", fake_run_agent)
    notebook = Notebook(tmp_path / "run")
    config = SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path))
    mission = Mission("EXPLORE", "toy-projects/rule30", None, "brief")

    ok, finding = runner.dispatch(mission, "agent-1", notebook, config)

    assert ok is True
    assert finding is not None
    assert finding.title == "recovered"
    assert len(calls) == 2
    assert "parseable FINDING block" in calls[1]["brief"]
    assert [entry["type"] for entry in notebook.entries("agent-1")] == [
        "dispatch",
        "result",
        "finding",
        "retry",
        "result",
        "finding",
    ]


def test_dispatch_retry_is_bounded_when_finding_stays_malformed(monkeypatch, tmp_path):
    calls = []

    def fake_run_agent(**kwargs):
        calls.append(kwargs)
        return BackendResult(0, "still no finding", False)

    monkeypatch.setattr(runner, "run_agent", fake_run_agent)
    notebook = Notebook(tmp_path / "run")
    config = SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path))
    mission = Mission("EXPLORE", "toy-projects/rule30", None, "brief")

    ok, finding = runner.dispatch(mission, "agent-1", notebook, config)

    assert ok is True
    assert finding is None
    assert len(calls) == 2
    retries = [
        entry for entry in notebook.entries("agent-1") if entry["type"] == "retry"
    ]
    assert len(retries) == 1
    assert retries[0]["payload"] == {
        "reason": "missing_or_malformed_finding",
        "attempt": 2,
    }


def test_dispatch_does_not_retry_parseable_finding(monkeypatch, tmp_path):
    calls = []

    def fake_run_agent(**kwargs):
        calls.append(kwargs)
        return BackendResult(
            0,
            "===FINDING===\nTITLE: direct\nCLAIM: EMPIRICAL: already complete\n",
            False,
        )

    monkeypatch.setattr(runner, "run_agent", fake_run_agent)
    config = SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path))
    mission = Mission("EXPLORE", "toy-projects/rule30", None, "brief")

    ok, finding = runner.dispatch(
        mission, "agent-1", Notebook(tmp_path / "run"), config
    )

    assert ok is True
    assert finding is not None
    assert len(calls) == 1


def _init_git_repo(path):
    path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=path, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=path, check=True
    )
    (path / "README.md").write_text("clean\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=path, check=True)


def test_build_finding_can_opt_in_to_a_local_provenance_commit(monkeypatch, tmp_path):
    project = tmp_path / "project"
    _init_git_repo(project)

    def fake_run_agent(**kwargs):
        (project / "change.txt").write_text("agent change\n", encoding="utf-8")
        return BackendResult(
            0,
            "===FINDING===\nTITLE: Safe build\nCLAIM: EMPIRICAL: it works\n",
            False,
        )

    monkeypatch.setattr(runner, "run_agent", fake_run_agent)
    notebook = Notebook(tmp_path / "run")
    config = SwarmConfig(
        parallel=5,
        backend="echo",
        workdir=str(tmp_path),
        build_allowlist=["project"],
        commit_per_finding=True,
    )

    ok, finding = runner.dispatch(
        Mission("BUILD", "project", None, "brief"),
        "agent-1",
        notebook,
        config,
    )

    assert ok is True
    assert finding is not None
    message = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert message == "swarm: Safe build"
    assert (project / "change.txt").read_text(encoding="utf-8") == "agent change\n"
    assert [entry["type"] for entry in notebook.entries("agent-1")][-1] == (
        "provenance_commit"
    )


def test_build_provenance_refuses_a_dirty_worktree_before_backend(monkeypatch, tmp_path):
    project = tmp_path / "project"
    _init_git_repo(project)
    (project / "user-change.txt").write_text("leave me alone\n", encoding="utf-8")
    called = False

    def fake_run_agent(**kwargs):
        nonlocal called
        called = True
        return BackendResult(0, "", False)

    monkeypatch.setattr(runner, "run_agent", fake_run_agent)
    config = SwarmConfig(
        parallel=5,
        backend="echo",
        workdir=str(tmp_path),
        build_allowlist=["project"],
        commit_per_finding=True,
    )

    ok, finding = runner.dispatch(
        Mission("BUILD", "project", None, "brief"),
        "agent-1",
        Notebook(tmp_path / "run"),
        config,
    )

    assert (ok, finding) == (False, None)
    assert called is False


def test_build_provenance_unstages_changes_when_commit_fails(monkeypatch, tmp_path):
    project = tmp_path / "project"
    _init_git_repo(project)

    def fake_run_agent(**kwargs):
        (project / "change.txt").write_text("agent change\n", encoding="utf-8")
        return BackendResult(
            0,
            "===FINDING===\nTITLE: Safe build\nCLAIM: EMPIRICAL: it works\n",
            False,
        )

    real_git = runner._git

    def fail_commit(cwd, *args):
        if args and args[0] == "commit":
            raise runner.ProvenanceError("simulated commit failure")
        return real_git(cwd, *args)

    monkeypatch.setattr(runner, "run_agent", fake_run_agent)
    monkeypatch.setattr(runner, "_git", fail_commit)
    config = SwarmConfig(
        parallel=5,
        backend="echo",
        workdir=str(tmp_path),
        build_allowlist=["project"],
        commit_per_finding=True,
    )

    ok, finding = runner.dispatch(
        Mission("BUILD", "project", None, "brief"),
        "agent-1",
        Notebook(tmp_path / "run"),
        config,
    )

    assert ok is True
    assert finding is not None
    assert (project / "change.txt").read_text(encoding="utf-8") == "agent change\n"
    assert subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=project, check=False
    ).returncode == 0


def test_wave_dispatches_at_most_one_primary_mission_per_project(tmp_path):
    swarm = runner.Swarm(
        SwarmConfig(parallel=8, backend="echo", workdir=str(tmp_path)),
        [
            Project(path="project-a", name="a"),
            Project(path="project-b", name="b"),
        ],
        Notebook(tmp_path / "run"),
    )

    jobs = swarm.wave(swarm.config.parallel)

    assert [mission.project for _, mission in jobs] == ["project-a", "project-b"]
    assert len({mission.project for _, mission in jobs}) == len(jobs)


def test_wave_deduplicates_lexical_project_aliases(tmp_path):
    swarm = runner.Swarm(
        SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path)),
        [
            Project(path="validation/project-1", name="project-1"),
            Project(path="validation//project-1", name="project-1"),
        ],
        Notebook(tmp_path / "run"),
    )

    jobs = swarm.wave(swarm.config.parallel)

    assert [mission.project for _, mission in jobs] == ["validation/project-1"]


def test_wave_skips_empty_project_identifiers(tmp_path):
    swarm = runner.Swarm(
        SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path)),
        [
            Project(path="", name="empty"),
            Project(path="project-a", name="a"),
        ],
        Notebook(tmp_path / "run"),
    )

    jobs = swarm.wave(swarm.config.parallel)

    assert [mission.project for _, mission in jobs] == ["project-a"]


def test_wave_returns_empty_when_all_projects_are_safety_denied(tmp_path):
    swarm = runner.Swarm(
        SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path)),
        [Project(path="service-account/project", name="denied")],
        Notebook(tmp_path / "run"),
    )

    assert swarm.wave(swarm.config.parallel) == []


@pytest.mark.parametrize(
    ("generated_project", "expected_projects"),
    [("", []), ("project-a", ["project-a"])],
)
def test_wave_bounds_repeated_invalid_or_duplicate_mission_generation(
    monkeypatch, tmp_path, generated_project, expected_projects
):
    swarm = runner.Swarm(
        SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path)),
        [
            Project(path="project-a", name="a"),
            Project(path="project-b", name="b"),
        ],
        Notebook(tmp_path / "run"),
    )
    calls = []

    def invalid_mission():
        calls.append(1)
        return Mission("EXPLORE", generated_project, None, "brief")

    monkeypatch.setattr(swarm, "next_mission", invalid_mission)

    jobs = swarm.wave(swarm.config.parallel)

    assert [mission.project for _, mission in jobs] == expected_projects
    assert len(calls) == len(runner._MISSION_ROTATION) * 2 + 8


def test_run_for_hours_stops_after_an_empty_wave(monkeypatch, tmp_path):
    swarm = runner.Swarm(
        SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path)),
        [Project(path="", name="empty")],
        Notebook(tmp_path / "run"),
    )

    calls = []
    real_run_wave = swarm.run_wave

    def counted_run_wave():
        calls.append(1)
        return real_run_wave()

    monkeypatch.setattr(swarm, "run_wave", counted_run_wave)

    assert swarm.run_for_hours(1.0, 0.0) == 0
    assert len(calls) == 1


def test_run_for_hours_accounts_for_completed_wave_before_stop(
    monkeypatch, tmp_path
):
    calls = []

    def completed_dispatch(*args, **kwargs):
        calls.append(1)
        runner.STOP.set()
        return True, runner.Finding(
            "completed", "idea", [], "EMPIRICAL: completed", None
        )

    monkeypatch.setattr(runner, "dispatch", completed_dispatch)
    swarm = runner.Swarm(
        SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path)),
        [Project(path="project", name="project")],
        Notebook(tmp_path / "run"),
    )

    runner.STOP.clear()
    try:
        assert swarm.run_for_hours(1.0, 20.0) == 1
        assert calls == [1]
        assert swarm.findings[0].title == "completed"
    finally:
        runner.STOP.clear()


def test_run_for_hours_stop_during_interval_wait_prevents_next_wave(
    monkeypatch, tmp_path
):
    class StopDuringWait:
        def __init__(self):
            self.stopped = False
            self.waits = []

        def is_set(self):
            return self.stopped

        def wait(self, timeout):
            self.waits.append(timeout)
            self.stopped = True
            return True

    stop = StopDuringWait()
    monkeypatch.setattr(runner, "STOP", stop)
    swarm = runner.Swarm(
        SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path)),
        [Project(path="project", name="project")],
        Notebook(tmp_path / "run"),
    )
    calls = []

    def completed_wave():
        calls.append(1)
        swarm._last_wave_had_jobs = True
        return 3

    monkeypatch.setattr(swarm, "run_wave", completed_wave)

    assert swarm.run_for_hours(1.0, 0.01) == 3
    assert calls == [1]
    assert stop.waits == [pytest.approx(0.6)]


@pytest.mark.parametrize("dry_run", [False, True])
def test_run_wave_does_not_start_after_stop(monkeypatch, tmp_path, capsys, dry_run):
    dispatches = []

    def unexpected_dispatch(*args, **kwargs):
        dispatches.append((args, kwargs))
        raise AssertionError("a stopped run must not dispatch a new wave")

    monkeypatch.setattr(runner, "dispatch", unexpected_dispatch)
    swarm = runner.Swarm(
        SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path)),
        [Project(path="project", name="project")],
        Notebook(tmp_path / "run"),
        dry_run=dry_run,
    )

    runner.STOP.set()
    try:
        assert swarm.run_wave() == 0
        assert swarm.mission_index == 0
        assert swarm._last_wave_had_jobs is False
        assert dispatches == []
        assert swarm.notebook.entries() == []
        assert capsys.readouterr().out == ""
    finally:
        runner.STOP.clear()


@pytest.mark.parametrize("dry_run", [False, True])
def test_run_wave_aborts_if_stop_arrives_during_assembly(
    monkeypatch, tmp_path, capsys, dry_run
):
    dispatches = []

    def unexpected_dispatch(*args, **kwargs):
        dispatches.append((args, kwargs))
        raise AssertionError("a canceled wave must not dispatch")

    monkeypatch.setattr(runner, "dispatch", unexpected_dispatch)
    swarm = runner.Swarm(
        SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path)),
        [Project(path="project", name="project")],
        Notebook(tmp_path / "run"),
        dry_run=dry_run,
    )

    def stop_during_assembly(_size):
        swarm.mission_index += 1
        runner.STOP.set()
        return [("agent-1", Mission("EXPLORE", "project", None, "brief"))]

    monkeypatch.setattr(swarm, "wave", stop_during_assembly)
    runner.STOP.clear()
    try:
        assert swarm.run_wave() == 0
        assert swarm.mission_index == 0
        assert swarm._last_wave_had_jobs is False
        assert dispatches == []
        assert swarm.notebook.entries() == []
        assert capsys.readouterr().out == ""
    finally:
        runner.STOP.clear()


def test_wave_keeps_distinct_lexical_project_identifiers(tmp_path):
    swarm = runner.Swarm(
        SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path)),
        [
            Project(path="validation/project-1", name="project-1"),
            Project(path="validation/project_1", name="project_1"),
        ],
        Notebook(tmp_path / "run"),
    )

    jobs = swarm.wave(swarm.config.parallel)

    assert [mission.project for _, mission in jobs] == [
        "validation/project-1",
        "validation/project_1",
    ]


@pytest.mark.parametrize(
    ("hours", "interval_min", "message"),
    [
        (-1.0, 20.0, "hours"),
        (math.nan, 20.0, "hours"),
        (math.inf, 20.0, "hours"),
        (-math.inf, 20.0, "hours"),
        (0.0, -1.0, "interval_min"),
        (0.0, math.nan, "interval_min"),
        (0.0, math.inf, "interval_min"),
        (0.0, -math.inf, "interval_min"),
    ],
)
def test_run_for_hours_rejects_invalid_direct_durations_before_wave(
    monkeypatch, tmp_path, hours, interval_min, message
):
    swarm = runner.Swarm(
        SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path)),
        [Project(path="project", name="project")],
        Notebook(tmp_path / "run"),
    )
    called = False

    def unexpected_wave():
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr(swarm, "run_wave", unexpected_wave)

    with pytest.raises(ValueError, match=message):
        swarm.run_for_hours(hours, interval_min)

    assert called is False


def test_dispatch_rejects_denied_workdir_before_backend(monkeypatch, tmp_path):
    called = False

    def fake_run_agent(**kwargs):
        nonlocal called
        called = True
        return BackendResult(0, "", False)

    monkeypatch.setattr(runner, "run_agent", fake_run_agent)
    config = SwarmConfig(
        parallel=5,
        backend="echo",
        workdir="/tmp/.env",
    )

    with pytest.raises(safety.SafetyViolation):
        runner.dispatch(
            Mission("EXPLORE", "toy-projects/rule30", None, "safe brief"),
            "agent-1",
            Notebook(tmp_path / "run"),
            config,
        )

    assert called is False


def test_dispatch_rejects_denied_mission_text_before_backend(monkeypatch, tmp_path):
    called = False

    def fake_run_agent(**kwargs):
        nonlocal called
        called = True
        return BackendResult(0, "", False)

    monkeypatch.setattr(runner, "run_agent", fake_run_agent)
    config = SwarmConfig(
        parallel=5,
        backend="echo",
        workdir=str(tmp_path),
    )

    with pytest.raises(safety.SafetyViolation):
        runner.dispatch(
            Mission(
                "EXPLORE",
                "toy-projects/rule30",
                None,
                "please inspect .env/private-data",
            ),
            "agent-1",
            Notebook(tmp_path / "run"),
            config,
        )

    assert called is False


def test_wave_rejects_symlinked_denied_workdir_before_any_dispatch(
    monkeypatch, tmp_path
):
    denied_target = tmp_path / "Sokra-target"
    denied_target.mkdir()
    workdir_alias = tmp_path / "safe-workdir"
    workdir_alias.symlink_to(denied_target, target_is_directory=True)
    calls = []

    def fake_run_agent(**kwargs):
        calls.append(kwargs)
        return BackendResult(0, "", False)

    monkeypatch.setattr(runner, "run_agent", fake_run_agent)
    notebook = Notebook(tmp_path / "run")
    swarm = runner.Swarm(
        SwarmConfig(
            parallel=5,
            backend="echo",
            workdir=str(workdir_alias),
        ),
        [
            Project(path="project-a", name="a"),
            Project(path="project-b", name="b"),
        ],
        notebook,
    )

    with pytest.raises(safety.SafetyViolation, match="denied path"):
        swarm.run_wave()

    assert calls == []
    assert notebook.entries() == []


def test_publication_deduplicates_before_writing(monkeypatch):
    published = []

    def fake_append(finding, path):
        published.append(finding)

    monkeypatch.setattr("swarm.orchestrator.append_to_inbox", fake_append)
    first = runner.Finding("Echo", "idea", ["p"], "EMPIRICAL: claim", None)
    duplicate = runner.Finding(
        " echo ", "idea", ["p"], " empirical: claim ", "run it"
    )

    _publish([first, duplicate])

    assert published == [duplicate]
