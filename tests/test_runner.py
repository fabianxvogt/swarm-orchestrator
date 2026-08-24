from __future__ import annotations

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
    def fake_run_agent(**kwargs):
        return BackendResult(returncode, FINDING_OUTPUT, timed_out)

    monkeypatch.setattr(runner, "run_agent", fake_run_agent)
    swarm = runner.Swarm(
        SwarmConfig(parallel=5, backend="echo", workdir=str(tmp_path)),
        [Project(path="toy-projects/rule30", name="rule30")],
        Notebook(tmp_path / "run"),
    )

    assert swarm.run_wave() == 0
    assert swarm.findings == []


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
