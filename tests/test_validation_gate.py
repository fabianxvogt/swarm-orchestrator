from __future__ import annotations

from swarm import orchestrator
from swarm.notebook import Notebook
from swarm.status import summarize_runs


def test_local_echo_cli_validation_gate(monkeypatch, tmp_path, capsys):
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    project_paths = [f"validation/project-{index}" for index in range(5)]
    for project_path in project_paths:
        (workdir / project_path).mkdir(parents=True)

    inventory = tmp_path / "PROJECT_INVENTORY.md"
    inventory.write_text(
        "## Tier A\n"
        + "\n".join(f"| `{path}` |" for path in project_paths)
        + "\n## Tier B\n",
        encoding="utf-8",
    )
    config = tmp_path / "swarm.yaml"
    config.write_text(
        f"backend: echo\n"
        f"parallel: 5\n"
        f"timeout_s: 5\n"
        f"workdir: {workdir}\n"
        "exclude: []\n"
        "projects:\n"
        + "\n".join(f"  - {path}" for path in project_paths)
        + "\n",
        encoding="utf-8",
    )
    runs_dir = tmp_path / "runs"
    monkeypatch.setattr(orchestrator, "INVENTORY", inventory)
    monkeypatch.setattr(orchestrator, "RUNS_DIR", runs_dir)

    assert orchestrator.main(["run", "--once", "--config", str(config)]) == 0
    assert "wave complete: 0 finding(s) parsed" in capsys.readouterr().out

    summaries = summarize_runs(runs_dir)
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.dispatches == 5
    assert summary.retries == 5
    assert summary.findings == 0
    assert summary.failures == 0
    assert summary.malformed_records == 0
    assert summary.contract_violations == 0
    assert summary.output_chars > 0
    run_dir = runs_dir / summary.name
    assert len(list(run_dir.glob("*.jsonl"))) == 5
    dispatches = [
        event
        for event in Notebook(run_dir).entries()
        if event["type"] == "dispatch"
    ]
    projects = [event["payload"]["project"] for event in dispatches]
    assert len(projects) == len(set(projects)) == 5
