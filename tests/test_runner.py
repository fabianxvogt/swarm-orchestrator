from __future__ import annotations

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
