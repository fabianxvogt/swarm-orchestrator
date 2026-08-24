# Agent wave — 2026-08-25 bounded run status

## Summary

Implemented the next roadmap item: a read-only `swarm status` command. It
inspects at most the newest ten run directories by default and reports each
run’s wave-level dispatch, parsed-finding, failed-result, and approximate
output-token counts. It also reports malformed JSONL records as warnings and
never creates or modifies a notebook.

The command accepts `--runs-dir` for isolated inspection and `--limit` for a
smaller bounded scan. It exits with status 2 for a non-positive limit. A dollar
cost is deliberately shown as unavailable because the notebook currently
records no provider pricing or token usage.

## Changed paths

- `swarm/status.py` — immutable run and wave summaries plus defensive JSONL
  parsing and formatting.
- `swarm/orchestrator.py` — `status` subcommand and bounded options.
- `tests/test_status.py` — wave grouping, failure counting, malformed-record
  tolerance, output proxy, CLI isolation, and limit validation.
- `README.md` — status quickstart.
- `ROADMAP.md` — marks the status item done with its evidence boundary.

## Evidence

- **EMPIRICAL:** two synthetic wave notebooks produce separate wave summaries;
  a nonzero result is counted as one failure and a nonempty finding payload as
  one parsed finding.
- **EMPIRICAL:** malformed JSONL is skipped and surfaced as a warning rather
  than aborting the status report.
- **EMPIRICAL:** `swarm status --runs-dir <temporary-dir>` succeeds without
  loading the portfolio inventory or dispatching a backend.
- **EMPIRICAL:** `pytest -q -p no:cacheprovider tests/test_status.py` passed:
  **6 passed**.
- **EMPIRICAL:** `git diff --check` passed.

## Limitations

The status command summarizes recorded notebook events; it does not infer
missing or unrecorded runs. Wave identity is read from the existing
`agent-*-wHHMMSS.jsonl` filename convention, with legacy files grouped as
`unassigned`. The output-token count is a rough four-characters-per-token
proxy, not provider billing data, and exact cost remains unavailable.

## Classification

**INCREMENTAL.** This is a small, bounded observability improvement with
focused regression coverage and no novelty or breakthrough claim.
