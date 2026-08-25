"""Read-only summaries for swarm run notebooks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


_WAVE_RE = re.compile(r"-w(?P<wave>\d{6})$")
_RUN_RE = re.compile(
    r"^(?P<timestamp>\d{8}-\d{6})(?:-(?P<collision>\d+))?$"
)


@dataclass(frozen=True)
class WaveSummary:
    name: str
    agents: int = 0
    dispatches: int = 0
    retries: int = 0
    findings: int = 0
    failures: int = 0
    output_chars: int = 0
    malformed_records: int = 0
    contract_violations: int = 0

    @property
    def output_tokens_estimate(self) -> int:
        """Return a clearly approximate four-characters-per-token proxy."""
        return (self.output_chars + 3) // 4


@dataclass(frozen=True)
class RunSummary:
    name: str
    waves: tuple[WaveSummary, ...]

    @property
    def dispatches(self) -> int:
        return sum(wave.dispatches for wave in self.waves)

    @property
    def findings(self) -> int:
        return sum(wave.findings for wave in self.waves)

    @property
    def retries(self) -> int:
        return sum(wave.retries for wave in self.waves)

    @property
    def failures(self) -> int:
        return sum(wave.failures for wave in self.waves)

    @property
    def output_chars(self) -> int:
        return sum(wave.output_chars for wave in self.waves)

    @property
    def output_tokens_estimate(self) -> int:
        return sum(wave.output_tokens_estimate for wave in self.waves)

    @property
    def malformed_records(self) -> int:
        return sum(wave.malformed_records for wave in self.waves)

    @property
    def contract_violations(self) -> int:
        return sum(wave.contract_violations for wave in self.waves)


def summarize_runs(runs_dir: Path, limit: int = 10) -> list[RunSummary]:
    """Summarize at most ``limit`` newest run directories without mutating them."""
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be an integer")
    if limit < 1:
        raise ValueError("limit must be positive")
    if not runs_dir.is_dir():
        return []

    run_dirs = sorted(
        (path for path in runs_dir.iterdir() if path.is_dir()),
        key=_run_sort_key,
        reverse=True,
    )[:limit]
    return [_summarize_run(run_dir) for run_dir in run_dirs]


def format_status(summaries: list[RunSummary], runs_dir: Path) -> str:
    """Format a compact human-readable status report."""
    lines = [f"runs: {len(summaries)} (source: {runs_dir})"]
    if not summaries:
        lines.append("no run notebooks found")
        return "\n".join(lines)

    for summary in summaries:
        lines.append(
            f"run {summary.name}: waves={len(summary.waves)} "
            f"dispatches={summary.dispatches} findings={summary.findings} "
            f"retries={summary.retries} "
            f"failures={summary.failures} "
            f"contract_violations={summary.contract_violations} "
            f"output_tokens~{summary.output_tokens_estimate} "
            "cost=unavailable"
        )
        for wave in summary.waves:
            lines.append(
                f"  wave {wave.name}: agents={wave.agents} "
                f"dispatches={wave.dispatches} findings={wave.findings} "
                f"retries={wave.retries} "
                f"failures={wave.failures} "
                f"contract_violations={wave.contract_violations}"
            )
        if summary.malformed_records:
            lines.append(
                f"  warning: malformed JSONL records="
                f"{summary.malformed_records}"
            )
    return "\n".join(lines)


def format_status_json(summaries: list[RunSummary], runs_dir: Path) -> str:
    """Format the same bounded status data as a versioned JSON document."""
    return json.dumps(
        _status_payload(summaries, runs_dir),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _status_payload(summaries: list[RunSummary], runs_dir: Path) -> dict:
    runs = [_run_payload(summary) for summary in summaries]
    return {
        "schema_version": 1,
        "runs_dir": str(runs_dir),
        "runs": runs,
        "totals": {
            "runs": len(runs),
            "waves": sum(len(summary.waves) for summary in summaries),
            "dispatches": sum(summary.dispatches for summary in summaries),
            "retries": sum(summary.retries for summary in summaries),
            "findings": sum(summary.findings for summary in summaries),
            "failures": sum(summary.failures for summary in summaries),
            "contract_violations": sum(
                summary.contract_violations for summary in summaries
            ),
            "output_chars": sum(summary.output_chars for summary in summaries),
            "output_tokens_estimate": sum(
                summary.output_tokens_estimate for summary in summaries
            ),
            "malformed_records": sum(
                summary.malformed_records for summary in summaries
            ),
        },
        "cost": None,
        "cost_status": "unavailable",
    }


def _run_payload(summary: RunSummary) -> dict:
    return {
        "name": summary.name,
        "waves": [_wave_payload(wave) for wave in summary.waves],
        "totals": {
            "waves": len(summary.waves),
            "dispatches": summary.dispatches,
            "retries": summary.retries,
            "findings": summary.findings,
            "failures": summary.failures,
            "contract_violations": summary.contract_violations,
            "output_chars": summary.output_chars,
            "output_tokens_estimate": summary.output_tokens_estimate,
            "malformed_records": summary.malformed_records,
        },
    }


def _wave_payload(wave: WaveSummary) -> dict:
    return {
        "name": wave.name,
        "agents": wave.agents,
        "dispatches": wave.dispatches,
        "retries": wave.retries,
        "findings": wave.findings,
        "failures": wave.failures,
        "contract_violations": wave.contract_violations,
        "output_chars": wave.output_chars,
        "output_tokens_estimate": wave.output_tokens_estimate,
        "malformed_records": wave.malformed_records,
    }


def _summarize_run(run_dir: Path) -> RunSummary:
    counters: dict[str, dict[str, int]] = {}
    primary_projects: dict[str, list[str]] = {}
    for notebook in sorted(run_dir.glob("*.jsonl")):
        wave_name = _wave_name(notebook.stem)
        counter = counters.setdefault(
            wave_name,
            {
                "agents": 0,
                "dispatches": 0,
                "retries": 0,
                "findings": 0,
                "failures": 0,
                "output_chars": 0,
                "malformed_records": 0,
                "contract_violations": 0,
            },
        )
        counter["agents"] += 1
        events: list[dict] = []
        try:
            lines = notebook.read_text(encoding="utf-8").splitlines()
        except OSError:
            counter["malformed_records"] += 1
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                counter["malformed_records"] += 1
                continue
            if isinstance(event, dict):
                events.append(event)
                project = _primary_project(event)
                if project is not None:
                    primary_projects.setdefault(wave_name, []).append(project)
            _count_event(event, counter)
        counter["contract_violations"] += _contract_violations(events)

    for wave_name, projects in primary_projects.items():
        counters[wave_name]["contract_violations"] += (
            _duplicate_primary_project_count(projects)
        )

    waves = tuple(
        WaveSummary(name=name, **counters[name])
        for name in sorted(counters, key=_wave_sort_key)
    )
    return RunSummary(name=run_dir.name, waves=waves)


def _count_event(event: object, counter: dict[str, int]) -> None:
    if not isinstance(event, dict):
        counter["malformed_records"] += 1
        return
    event_type = event.get("type")
    payload = event.get("payload")
    if event_type == "dispatch":
        if not _valid_dispatch_payload(payload):
            counter["malformed_records"] += 1
            return
        counter["dispatches"] += 1
    elif event_type == "dispatch_dry_run":
        counter["dispatches"] += 1
    elif event_type == "retry":
        if not _valid_retry_payload(payload):
            counter["malformed_records"] += 1
            return
        counter["retries"] += 1
    elif event_type == "finding":
        if payload is None:
            return
        if not _valid_finding_payload(payload):
            counter["malformed_records"] += 1
            return
        counter["findings"] += 1
    elif event_type == "result":
        if not _valid_result_payload(payload):
            counter["malformed_records"] += 1
            return
        output_chars = payload.get("stdout_chars", 0)
        counter["output_chars"] += output_chars
        returncode = payload.get("returncode")
        if payload["timed_out"] or returncode != 0:
            counter["failures"] += 1


def _valid_retry_payload(payload: object) -> bool:
    """Return whether a retry record has the runner's required fields."""
    if not isinstance(payload, dict):
        return False
    reason = payload.get("reason")
    attempt = payload.get("attempt")
    return (
        isinstance(reason, str)
        and bool(reason.strip())
        and isinstance(attempt, int)
        and not isinstance(attempt, bool)
        and attempt >= 1
    )


def _valid_dispatch_payload(payload: object) -> bool:
    """Return whether a runtime dispatch has its required project field."""
    if not isinstance(payload, dict):
        return False
    project = payload.get("project")
    return isinstance(project, str) and bool(project.strip())


def _valid_result_payload(payload: object) -> bool:
    """Return whether a result has the runner's stable summary fields."""
    if not isinstance(payload, dict):
        return False
    returncode = payload.get("returncode")
    timed_out = payload.get("timed_out")
    stdout_chars = payload.get("stdout_chars")
    return (
        isinstance(returncode, int)
        and not isinstance(returncode, bool)
        and isinstance(timed_out, bool)
        and isinstance(stdout_chars, int)
        and not isinstance(stdout_chars, bool)
        and stdout_chars >= 0
    )


def _valid_finding_payload(payload: object) -> bool:
    """Return whether a non-null finding has the parser's required fields."""
    if not isinstance(payload, dict):
        return False
    title = payload.get("title")
    claim = payload.get("claim")
    return (
        isinstance(title, str)
        and bool(title.strip())
        and isinstance(claim, str)
        and bool(claim.strip())
    )


def _valid_finding_event(event: dict) -> bool:
    """Return whether an event is a valid runner finding record."""
    return event.get("type") == "finding" and (
        event.get("payload") is None
        or _valid_finding_payload(event.get("payload"))
    )


def _attempt_matches(payload: object, expected: int) -> bool:
    """Return whether optional runner attempt metadata matches its pair."""
    if not isinstance(payload, dict) or "attempt" not in payload:
        return True
    attempt = payload["attempt"]
    return (
        isinstance(attempt, int)
        and not isinstance(attempt, bool)
        and attempt == expected
    )


def _attempts_are_coherent(events: list[dict]) -> bool:
    """Check the runner's bounded attempt numbering when metadata is present."""
    result_indexes = [
        index
        for index, event in enumerate(events)
        if event.get("type") == "result"
        and _valid_result_payload(event.get("payload"))
    ]
    for expected, result_index in enumerate(result_indexes, start=1):
        result = events[result_index]
        if not _attempt_matches(result.get("payload"), expected):
            return False
        finding_index = result_index + 1
        if finding_index >= len(events):
            continue
        finding = events[finding_index]
        finding_payload = finding.get("payload")
        if (
            finding.get("type") == "finding"
            and finding_payload is not None
            and _valid_finding_payload(finding_payload)
            and not _attempt_matches(finding_payload, expected)
        ):
            return False

    for event in events:
        if (
            event.get("type") == "retry"
            and _valid_retry_payload(event.get("payload"))
            and not _attempt_matches(event.get("payload"), 2)
        ):
            return False
    return True


def _primary_project(event: dict) -> str | None:
    if event.get("type") != "dispatch":
        return None
    payload = event.get("payload")
    if not _valid_dispatch_payload(payload):
        return None
    return payload["project"]


def _duplicate_primary_project_count(projects: list[str]) -> int:
    seen: set[str] = set()
    duplicates = 0
    for project in projects:
        if project in seen:
            duplicates += 1
        else:
            seen.add(project)
    return duplicates


def _contract_violations(events: list[dict]) -> int:
    """Count runner protocol breaks in one agent notebook.

    A dry-run notebook intentionally has no backend result. Runtime notebooks
    must contain one dispatch, a result for that dispatch, and a finding record
    after each result. Retries are bounded and cannot follow a failed result.
    Wave-level duplicate primary projects are counted by ``_summarize_run``.
    This is deliberately structural: it reports notebook completeness without
    judging provider output quality.
    """
    if not events:
        return 0

    dry_run_dispatches = [
        event for event in events if event.get("type") == "dispatch_dry_run"
    ]
    if dry_run_dispatches:
        return 0 if len(events) == len(dry_run_dispatches) else 1

    dispatches = [event for event in events if event.get("type") == "dispatch"]
    results = [
        event
        for event in events
        if event.get("type") == "result"
        and _valid_result_payload(event.get("payload"))
    ]
    retries = [
        event
        for event in events
        if event.get("type") == "retry"
        and _valid_retry_payload(event.get("payload"))
    ]
    if not dispatches and not results and not retries:
        if all(event.get("type") == "provenance_blocked" for event in events):
            return 0
        return 1
    violations = 0

    if len(dispatches) != 1:
        violations += 1
    if not results:
        violations += 1
    if len(results) > 2:
        violations += 1
    if len(retries) > 1:
        violations += 1
    if len(results) > 1 and not retries:
        violations += 1
    if retries and len(results) < 2:
        violations += 1

    if retries and results:
        first_payload = results[0].get("payload")
        if isinstance(first_payload, dict):
            first_failed = first_payload.get("timed_out") or (
                isinstance(first_payload.get("returncode"), int)
                and first_payload["returncode"] != 0
            )
            if first_failed:
                violations += 1
        valid_result_indexes = [
            index
            for index, event in enumerate(events)
            if event.get("type") == "result"
            and _valid_result_payload(event.get("payload"))
        ]
        if valid_result_indexes:
            first_finding_index = valid_result_indexes[0] + 1
            if first_finding_index < len(events):
                first_finding = events[first_finding_index]
                if (
                    first_finding.get("type") == "finding"
                    and first_finding.get("payload") is not None
                    and _valid_finding_payload(first_finding.get("payload"))
                ):
                    violations += 1
        result_indexes = [
            index
            for index, event in enumerate(events)
            if event.get("type") == "result"
        ]
        retry_indexes = [
            index
            for index, event in enumerate(events)
            if event.get("type") == "retry"
            and _valid_retry_payload(event.get("payload"))
        ]
        if len(result_indexes) >= 2 and not (
            result_indexes[0] < retry_indexes[0] < result_indexes[1]
        ):
            violations += 1

    if not _attempts_are_coherent(events):
        violations += 1

    for index, event in enumerate(events):
        if event.get("type") == "finding":
            previous = events[index - 1] if index else None
            if previous is None or previous.get("type") != "result":
                violations += 1
        if event.get("type") != "result":
            continue
        if index + 1 >= len(events) or not _valid_finding_event(events[index + 1]):
            violations += 1

    return violations


def _wave_name(stem: str) -> str:
    match = _WAVE_RE.search(stem)
    return match.group("wave") if match else "unassigned"


def _run_sort_key(path: Path) -> tuple[int, str, int, str]:
    """Order generated run names by timestamp and numeric collision suffix."""
    match = _RUN_RE.fullmatch(path.name)
    if match:
        collision = int(match.group("collision") or 0)
        return (1, match.group("timestamp"), collision, path.name)
    return (0, path.name, 0, path.name)


def _wave_sort_key(name: str) -> tuple[int, str]:
    return (0 if name == "unassigned" else 1, name)
