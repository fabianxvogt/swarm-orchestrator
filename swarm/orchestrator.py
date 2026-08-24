from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import safety
from .config import SwarmConfig, load_config
from .findings import Finding, append_to_connections, append_to_inbox, prepare_findings
from .notebook import Notebook
from .registry import apply_filters, load_registry
from .runner import Swarm, install_signal_handlers, reap_stale
from .status import format_status, format_status_json, summarize_runs

PORTFOLIO_ROOT = Path("/Users/fabian/Development")
INVENTORY = PORTFOLIO_ROOT / "docs" / "PROJECT_INVENTORY.md"
INBOX = PORTFOLIO_ROOT / "ideas" / "INBOX.md"
CONNECTIONS = PORTFOLIO_ROOT / "ideas" / "CONNECTIONS.md"
RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="swarm",
        description="Orchestrate parallel AI coding-agent subagents across the dev portfolio.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="dispatch missions (loop or single wave)")
    run.add_argument(
        "--hours",
        type=float,
        default=0.0,
        help="time budget in hours; 0 means a single wave",
    )
    run.add_argument(
        "--parallel",
        type=int,
        default=None,
        help="number of parallel subagents (default from config, else 8)",
    )
    run.add_argument(
        "--interval-min",
        type=float,
        default=None,
        help="minutes to sleep between waves (default from config)",
    )
    run.add_argument(
        "--timeout-s",
        type=int,
        default=None,
        help="per-agent timeout in seconds (default from config)",
    )
    run.add_argument("--backend", choices=["opencode", "claude", "echo"], default=None)
    run.add_argument("--model", default=None, help="provider/model for the backend")
    run.add_argument(
        "--auto",
        action="store_true",
        help="allow write missions (DOCUMENT/BUILD) to auto-approve permissions",
    )
    run.add_argument(
        "--once", action="store_true", help="run exactly one wave and exit"
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="print mission briefs without spawning agents",
    )
    run.add_argument(
        "--config", type=Path, default=None, help="YAML/JSON config override"
    )
    status = sub.add_parser("status", help="summarize recent run notebooks")
    status.add_argument(
        "--runs-dir",
        type=Path,
        default=RUNS_DIR,
        help="run notebook directory (default: package runs/)",
    )
    status.add_argument(
        "--limit",
        type=int,
        default=10,
        help="maximum number of newest runs to inspect (default: 10)",
    )
    status.add_argument(
        "--json",
        action="store_true",
        help="emit a versioned JSON document instead of human-readable text",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        try:
            summaries = summarize_runs(args.runs_dir, args.limit)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        formatter = format_status_json if args.json else format_status
        print(formatter(summaries, args.runs_dir))
        return 0

    config = _effective_config(args)
    projects = apply_filters(
        load_registry(INVENTORY), config.projects or None, config.exclude
    )
    if not projects:
        print("error: no projects resolved", file=sys.stderr)
        return 2

    install_signal_handlers()
    reaped = reap_stale(RUNS_DIR)
    if reaped:
        print(f"reaped stale processes: {reaped}")

    run_dir = RUNS_DIR / time.strftime("%Y%m%d-%H%M%S")
    suffix = 1
    while run_dir.exists():
        suffix += 1
        run_dir = RUNS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{suffix}"
    notebook = Notebook(run_dir)
    swarm = Swarm(config, projects, notebook, dry_run=args.dry_run)

    print(
        f"swarm: {len(projects)} projects, backend={config.backend}, "
        f"parallel={config.parallel}, run_dir={run_dir}"
    )
    try:
        if args.once or args.hours <= 0:
            collected = swarm.run_wave()
            print(f"wave complete: {collected} finding(s) parsed")
        else:
            collected = swarm.run_for_hours(args.hours, config.interval_min)
            print(f"time budget expired: {collected} finding(s) collected")
    except KeyboardInterrupt:
        print("\nshutdown requested; exiting after current wave")

    if not args.dry_run:
        _publish(swarm.findings)
        print(f"notebook: {len(notebook.entries())} events in {run_dir}")
    return 0


def _effective_config(args: argparse.Namespace) -> SwarmConfig:
    config = load_config(args.config) if args.config else SwarmConfig()
    if args.parallel is not None:
        if not 5 <= args.parallel <= 10:
            raise SystemExit("error: --parallel must be between 5 and 10")
        config.parallel = args.parallel
    if args.interval_min is not None:
        config.interval_min = args.interval_min
    if args.timeout_s is not None:
        config.timeout_s = args.timeout_s
    if args.backend is not None:
        config.backend = args.backend
    if args.model is not None:
        config.model = args.model
    if args.auto:
        config.auto_approve = True
    return config


def _publish(findings: list[Finding]) -> None:
    for finding in prepare_findings(findings):
        try:
            if finding.is_connection:
                append_to_connections(finding, CONNECTIONS)
                print(f"connection recorded: {finding.title}")
            else:
                append_to_inbox(finding, INBOX)
                print(f"idea recorded: {finding.title}")
        except (safety.SafetyViolation, OSError, ValueError) as exc:
            print(
                f"warning: could not record finding {finding.title!r}: {exc}",
                file=sys.stderr,
            )


if __name__ == "__main__":
    sys.exit(main())
