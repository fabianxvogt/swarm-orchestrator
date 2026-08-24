# Agent wave — 2026-08-25 status JSON output

## Summary

Added an opt-in `swarm status --json` mode for bounded, read-only notebook
inspection. The default human-readable status output is unchanged. JSON output
contains a `schema_version`, source directory, per-run and per-wave counters,
aggregate totals, and explicit `cost: null` / `cost_status: "unavailable"`
metadata so consumers do not mistake the approximate token proxy for billing
data.

## Changed paths

- `swarm/status.py` — versioned JSON serialization for existing summaries.
- `swarm/orchestrator.py` — `status --json` CLI option.
- `tests/test_status.py` — payload shape, totals, empty output, and CLI parsing.
- `README.md` — JSON quickstart and observability boundary.
- `ROADMAP.md` — records the completed increment.

## Evidence

- **EMPIRICAL:** JSON output parses with the standard-library `json` module and
  preserves run, wave, malformed-record, and approximate token counters.
- **EMPIRICAL:** an empty or missing runs directory returns valid JSON with an
  empty run list and zero totals.
- **EMPIRICAL:** the default text formatter remains a separate code path, so
  existing human-readable output is not changed by the new flag.

## Limitations

The schema reports only data already recorded in bounded notebook scans. It
does not add provider token accounting, exact cost, timestamps, or provenance
for individual backend calls. `schema_version` is currently `1`; future
incompatible payload changes should increment it.

## Classification

**INCREMENTAL.** This is a small compatibility and observability improvement;
it makes existing status data script-friendly without changing dispatch,
publication, or notebook behavior.
