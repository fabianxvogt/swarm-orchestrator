from __future__ import annotations

import json

import pytest

from swarm.notebook import Notebook
from swarm.orchestrator import main
from swarm.status import format_status, format_status_json, summarize_runs


def test_summarize_runs_groups_wave_events_and_counts_failures(tmp_path):
    run = tmp_path / "20260825-120000"
    notebook = Notebook(run)
    notebook.log("agent-1-w120001", "dispatch", {})
    notebook.log(
        "agent-1-w120001",
        "result",
        {"returncode": 0, "timed_out": False, "stdout_chars": 17},
    )
    notebook.log("agent-1-w120001", "finding", None)
    notebook.log(
        "agent-1-w120001",
        "retry",
        {"reason": "missing_or_malformed_finding", "attempt": 2},
    )
    notebook.log(
        "agent-1-w120001",
        "result",
        {"returncode": 0, "timed_out": False, "stdout_chars": 0},
    )
    notebook.log("agent-1-w120001", "finding", {"title": "one"})
    notebook.log("agent-2-w120001", "dispatch", {})
    notebook.log(
        "agent-2-w120001",
        "result",
        {"returncode": 1, "timed_out": False, "stdout_chars": 3},
    )
    notebook.log("agent-2-w120001", "finding", None)
    notebook.log("agent-1-w120002", "dispatch_dry_run", {})

    summary = summarize_runs(tmp_path)[0]

    assert summary.name == "20260825-120000"
    assert summary.dispatches == 3
    assert summary.retries == 1
    assert summary.findings == 1
    assert summary.failures == 1
    assert summary.contract_violations == 0
    assert summary.output_chars == 20
    assert summary.output_tokens_estimate == 5
    assert [(wave.name, wave.agents) for wave in summary.waves] == [
        ("120001", 2),
        ("120002", 1),
    ]


def test_status_skips_malformed_records_and_is_bounded(tmp_path):
    for name in ("20260825-120000", "20260825-130000"):
        run = tmp_path / name
        run.mkdir()
        (run / "agent-1-w120000.jsonl").write_text(
            '{"type":"dispatch","payload":{}}\nnot json\n',
            encoding="utf-8",
        )

    summaries = summarize_runs(tmp_path, limit=1)

    assert [summary.name for summary in summaries] == ["20260825-130000"]
    assert summaries[0].malformed_records == 1
    report = format_status(summaries, tmp_path)
    assert "warning: malformed JSONL records=1" in report
    assert "cost=unavailable" in report


def test_status_reports_non_object_finding_payload_without_counting_finding(
    tmp_path,
):
    run = tmp_path / "20260825-120000"
    notebook = Notebook(run)
    notebook.log("agent-1-w120001", "dispatch", {})
    notebook.log(
        "agent-1-w120001",
        "result",
        {"returncode": 0, "timed_out": False, "stdout_chars": 0},
    )
    notebook.log("agent-1-w120001", "finding", ["not", "a", "finding"])

    summary = summarize_runs(tmp_path)[0]

    assert summary.findings == 0
    assert summary.malformed_records == 1
    assert summary.contract_violations == 0


def test_status_reports_non_object_dispatch_payload_without_counting_dispatch(
    tmp_path,
):
    run = tmp_path / "20260825-120000"
    notebook = Notebook(run)
    notebook.log("agent-1-w120001", "dispatch", ["not", "a", "dispatch"])
    notebook.log(
        "agent-1-w120001",
        "result",
        {"returncode": 0, "timed_out": False, "stdout_chars": 0},
    )
    notebook.log("agent-1-w120001", "finding", {"title": "one"})

    summary = summarize_runs(tmp_path)[0]

    assert summary.dispatches == 0
    assert summary.findings == 1
    assert summary.malformed_records == 1
    assert summary.contract_violations == 0


def test_status_reports_non_object_retry_payload_without_counting_retry(tmp_path):
    run = tmp_path / "20260825-120000"
    notebook = Notebook(run)
    notebook.log("agent-1-w120001", "dispatch", {})
    notebook.log(
        "agent-1-w120001",
        "result",
        {"returncode": 0, "timed_out": False, "stdout_chars": 0},
    )
    notebook.log("agent-1-w120001", "finding", None)
    notebook.log("agent-1-w120001", "retry", ["not", "a", "retry"])
    notebook.log(
        "agent-1-w120001",
        "result",
        {"returncode": 0, "timed_out": False, "stdout_chars": 0},
    )
    notebook.log("agent-1-w120001", "finding", {"title": "recovered"})

    summary = summarize_runs(tmp_path)[0]

    assert summary.retries == 0
    assert summary.findings == 1
    assert summary.malformed_records == 1
    assert summary.contract_violations == 0


def test_summarize_runs_orders_numeric_collision_suffixes(tmp_path):
    for name in (
        "20260825-120000",
        "20260825-120000-2",
        "20260825-120000-10",
    ):
        (tmp_path / name).mkdir()

    summaries = summarize_runs(tmp_path)

    assert [summary.name for summary in summaries] == [
        "20260825-120000-10",
        "20260825-120000-2",
        "20260825-120000",
    ]


def test_status_cli_does_not_require_portfolio_inventory(tmp_path, capsys):
    run = tmp_path / "20260825-120000"
    run.mkdir()
    (run / "agent-1-w120000.jsonl").write_text(
        json.dumps({"type": "dispatch_dry_run", "payload": "brief"}) + "\n",
        encoding="utf-8",
    )

    assert main(["status", "--runs-dir", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "dispatches=1" in output
    assert "contract_violations=0" in output


def test_status_json_has_versioned_run_and_wave_totals(tmp_path):
    run = tmp_path / "20260825-120000"
    notebook = Notebook(run)
    notebook.log("agent-1-w120001", "dispatch", {})
    notebook.log(
        "agent-1-w120001",
        "result",
        {"returncode": 0, "timed_out": False, "stdout_chars": 8},
    )
    notebook.log("agent-1-w120001", "finding", {"title": "one"})

    payload = json.loads(format_status_json(summarize_runs(tmp_path), tmp_path))

    assert payload["schema_version"] == 1
    assert payload["runs_dir"] == str(tmp_path)
    assert payload["cost"] is None
    assert payload["cost_status"] == "unavailable"
    assert payload["totals"] == {
        "runs": 1,
        "waves": 1,
        "dispatches": 1,
        "retries": 0,
        "findings": 1,
        "failures": 0,
        "contract_violations": 0,
        "output_chars": 8,
        "output_tokens_estimate": 2,
        "malformed_records": 0,
    }
    assert payload["runs"][0]["totals"] == {
        "waves": 1,
        "dispatches": 1,
        "retries": 0,
        "findings": 1,
        "failures": 0,
        "contract_violations": 0,
        "output_chars": 8,
        "output_tokens_estimate": 2,
        "malformed_records": 0,
    }
    assert payload["runs"][0]["waves"][0] == {
        "name": "120001",
        "agents": 1,
        "dispatches": 1,
        "retries": 0,
        "findings": 1,
        "failures": 0,
        "contract_violations": 0,
        "output_chars": 8,
        "output_tokens_estimate": 2,
        "malformed_records": 0,
    }


def test_status_cli_json_mode_is_machine_readable(tmp_path, capsys):
    assert main(["status", "--runs-dir", str(tmp_path), "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["schema_version"] == 1
    assert payload["runs"] == []
    assert payload["totals"]["runs"] == 0


def test_status_reports_retry_events_without_changing_dispatch_count(tmp_path):
    run = tmp_path / "20260825-120000"
    notebook = Notebook(run)
    notebook.log("agent-1-w120001", "dispatch", {})
    notebook.log(
        "agent-1-w120001",
        "result",
        {"returncode": 0, "timed_out": False, "stdout_chars": 0},
    )
    notebook.log("agent-1-w120001", "finding", None)
    notebook.log(
        "agent-1-w120001",
        "retry",
        {"reason": "missing_or_malformed_finding", "attempt": 2},
    )
    notebook.log(
        "agent-1-w120001",
        "result",
        {"returncode": 0, "timed_out": False, "stdout_chars": 0},
    )
    notebook.log("agent-1-w120001", "finding", None)

    summary = summarize_runs(tmp_path)[0]
    payload = json.loads(format_status_json([summary], tmp_path))

    assert summary.dispatches == 1
    assert summary.retries == 1
    assert summary.findings == 0
    assert payload["totals"]["retries"] == 1
    assert payload["totals"]["contract_violations"] == 0
    assert payload["runs"][0]["waves"][0]["retries"] == 1


def test_status_reports_incomplete_and_invalid_retry_notebooks(tmp_path):
    run = tmp_path / "20260825-120000"
    incomplete = Notebook(run)
    incomplete.log("agent-1-w120001", "dispatch", {})

    failed_retry = Notebook(run)
    failed_retry.log("agent-2-w120001", "dispatch", {})
    failed_retry.log(
        "agent-2-w120001",
        "result",
        {"returncode": 1, "timed_out": False, "stdout_chars": 0},
    )
    failed_retry.log("agent-2-w120001", "finding", None)
    failed_retry.log(
        "agent-2-w120001",
        "retry",
        {"reason": "missing_or_malformed_finding", "attempt": 2},
    )
    failed_retry.log(
        "agent-2-w120001",
        "result",
        {"returncode": 1, "timed_out": False, "stdout_chars": 0},
    )
    failed_retry.log("agent-2-w120001", "finding", None)

    summary = summarize_runs(tmp_path)[0]

    assert summary.dispatches == 2
    assert summary.failures == 2
    assert summary.contract_violations == 2
    report = format_status([summary], tmp_path)
    assert "contract_violations=2" in report


def test_status_flags_duplicate_primary_projects_in_one_wave(tmp_path):
    run = tmp_path / "20260825-120000"
    for agent in ("agent-1-w120001", "agent-2-w120001"):
        notebook = Notebook(run)
        notebook.log(
            agent,
            "dispatch",
            {"project": "validation/project-1"},
        )
        notebook.log(
            agent,
            "result",
            {"returncode": 0, "timed_out": False, "stdout_chars": 0},
        )
        notebook.log(agent, "finding", None)

    summary = summarize_runs(tmp_path)[0]

    assert summary.dispatches == 2
    assert summary.contract_violations == 1
    payload = json.loads(format_status_json([summary], tmp_path))
    assert payload["runs"][0]["waves"][0]["contract_violations"] == 1


def test_status_exempts_safety_blocked_notebook_without_backend_result(tmp_path):
    run = tmp_path / "20260825-120000"
    notebook = Notebook(run)
    notebook.log("agent-1-w120001", "provenance_blocked", {"error": "dirty"})

    summary = summarize_runs(tmp_path)[0]

    assert summary.dispatches == 0
    assert summary.contract_violations == 0


def test_status_rejects_non_positive_limit(tmp_path, capsys):
    assert main(["status", "--runs-dir", str(tmp_path), "--limit", "0"]) == 2
    assert "limit must be positive" in capsys.readouterr().err


@pytest.mark.parametrize("limit", [0, -1])
def test_summarize_runs_rejects_non_positive_limit(tmp_path, limit):
    with pytest.raises(ValueError, match="limit must be positive"):
        summarize_runs(tmp_path, limit=limit)


@pytest.mark.parametrize("limit", [True, 1.5, "1", None])
def test_summarize_runs_rejects_non_integer_limit(tmp_path, limit):
    with pytest.raises(ValueError, match="limit must be an integer"):
        summarize_runs(tmp_path, limit=limit)
