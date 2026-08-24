"""Read-only summaries for swarm run notebooks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


_WAVE_RE = re.compile(r"-w(?P<wave>\d{6})$")


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


def summarize_runs(runs_dir: Path, limit: int = 10) -> list[RunSummary]:
    """Summarize at most ``limit`` newest run directories without mutating them."""
    if limit < 1:
        raise ValueError("limit must be positive")
    if not runs_dir.is_dir():
        return []

    run_dirs = sorted(
        (path for path in runs_dir.iterdir() if path.is_dir()),
        key=lambda path: path.name,
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
            f"output_tokens~{summary.output_tokens_estimate} "
            "cost=unavailable"
        )
        for wave in summary.waves:
            lines.append(
                f"  wave {wave.name}: agents={wave.agents} "
                f"dispatches={wave.dispatches} findings={wave.findings} "
                f"retries={wave.retries} "
                f"failures={wave.failures}"
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
        "output_chars": wave.output_chars,
        "output_tokens_estimate": wave.output_tokens_estimate,
        "malformed_records": wave.malformed_records,
    }


def _summarize_run(run_dir: Path) -> RunSummary:
    counters: dict[str, dict[str, int]] = {}
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
            },
        )
        counter["agents"] += 1
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
            _count_event(event, counter)

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
    if event_type in {"dispatch", "dispatch_dry_run"}:
        counter["dispatches"] += 1
    elif event_type == "retry":
        counter["retries"] += 1
    elif event_type == "finding" and payload is not None:
        counter["findings"] += 1
    elif event_type == "result":
        if not isinstance(payload, dict):
            counter["malformed_records"] += 1
            return
        output_chars = payload.get("stdout_chars", 0)
        if isinstance(output_chars, int) and output_chars >= 0:
            counter["output_chars"] += output_chars
        returncode = payload.get("returncode")
        if payload.get("timed_out") or (
            isinstance(returncode, int) and returncode != 0
        ):
            counter["failures"] += 1


def _wave_name(stem: str) -> str:
    match = _WAVE_RE.search(stem)
    return match.group("wave") if match else "unassigned"


def _wave_sort_key(name: str) -> tuple[int, str]:
    return (0 if name == "unassigned" else 1, name)
