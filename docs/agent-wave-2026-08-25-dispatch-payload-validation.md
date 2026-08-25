# Agent wave — 2026-08-25 dispatch payload validation

## Summary

Closed two status-reporting input gaps: a JSON-valid runtime `dispatch` event
whose payload was not an object, or whose required `project` field was missing,
blank, or wrongly typed, was previously counted as a dispatch. Status now
reports those records as malformed and excludes them from dispatch totals.
Dry-run dispatches remain compatible with their existing string brief payload.

## Changed paths

- `swarm/status.py` — validate runtime dispatch payload shape and required
  project field.
- `tests/test_status.py` — regressions for non-object and invalid-project
  dispatch payloads.
- `ROADMAP.md` / `docs/README.md` — evidence and navigation.

## Evidence

- **EMPIRICAL:** a malformed runtime dispatch payload increments
  `malformed_records` and does not inflate `dispatches`.
- **EMPIRICAL:** a runtime dispatch with a missing, blank, non-string, or
  boolean `project` increments `malformed_records` and does not inflate
  `dispatches` or the duplicate-project check.
- **EMPIRICAL:** the complete focused and full test suites pass.
- **EMPIRICAL:** no provider, workflow, run notebook, dependency, or generated
  artifact is required.

## Boundary and classification

This validates the runner's required runtime `project` field only; other
optional dispatch metadata remains outside this check. It does not change the
separate dry-run payload contract.

**INCREMENTAL.** Narrow defensive status validation with local regression
evidence; no dispatch or provider behavior changed.
